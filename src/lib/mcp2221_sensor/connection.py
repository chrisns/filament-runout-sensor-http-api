"""
Connection Management for MCP2221A USB Device.

Provides connection retry logic with exponential backoff, connection health
monitoring, and graceful recovery from USB disconnection events.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class ConnectionAttempt:
    """Individual connection attempt record."""
    attempt_number: int
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class ConnectionStats:
    """Connection statistics and health metrics."""
    total_attempts: int = 0
    successful_connections: int = 0
    failed_attempts: int = 0
    current_uptime: Optional[timedelta] = None
    last_successful_connection: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_connection_time_ms: float = 0.0
    recent_attempts: list = None

    def __post_init__(self):
        if self.recent_attempts is None:
            self.recent_attempts = []

    @property
    def success_rate(self) -> float:
        """Calculate connection success rate."""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_connections / self.total_attempts

    @property
    def is_stable(self) -> bool:
        """Check if connection is considered stable."""
        if self.current_uptime is None:
            return False
        return self.current_uptime.total_seconds() > 30.0  # 30 seconds


class ConnectionManager:
    """
    Connection manager with exponential backoff and health monitoring.

    Manages MCP2221A USB device connection with automatic retry logic,
    exponential backoff, and connection health monitoring.
    """

    def __init__(
        self,
        device_connector: Callable[[], bool],
        health_checker: Callable[[], bool],
        initial_retry_delay: float = 0.1,
        max_retry_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        max_retry_attempts: int = 10
    ):
        """
        Initialize connection manager.

        Args:
            device_connector: Function that attempts device connection
            health_checker: Function that checks connection health
            initial_retry_delay: Initial retry delay in seconds
            max_retry_delay: Maximum retry delay in seconds
            backoff_multiplier: Backoff multiplier for exponential backoff
            max_retry_attempts: Maximum number of retry attempts
        """
        self.device_connector = device_connector
        self.health_checker = health_checker

        # Retry configuration
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_retry_attempts = max_retry_attempts

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._connection_time: Optional[datetime] = None
        self._retry_count = 0
        self._current_retry_delay = initial_retry_delay

        # Statistics and monitoring
        self._stats = ConnectionStats()
        self._lock = threading.RLock()

        # Event callbacks
        self._state_change_callbacks: list[Callable[[ConnectionState], None]] = []
        self._connection_callbacks: list[Callable[[bool], None]] = []

        # Background monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()

        logger.info("ConnectionManager initialized")

    def connect(self) -> bool:
        """
        Attempt to establish connection with retry logic.

        Returns:
            bool: True if connection successful
        """
        with self._lock:
            if self._state == ConnectionState.CONNECTED:
                return True

            self._set_state(ConnectionState.CONNECTING)
            self._retry_count = 0
            self._current_retry_delay = self.initial_retry_delay

            return self._attempt_connection_with_retries()

    def _attempt_connection_with_retries(self) -> bool:
        """Attempt connection with exponential backoff."""
        while self._retry_count < self.max_retry_attempts:
            attempt_start = datetime.now()

            try:
                logger.info(f"Connection attempt {self._retry_count + 1}/{self.max_retry_attempts}")

                # Attempt connection
                success = self.device_connector()
                duration = (datetime.now() - attempt_start).total_seconds() * 1000

                # Record attempt
                attempt = ConnectionAttempt(
                    attempt_number=self._retry_count + 1,
                    timestamp=attempt_start,
                    success=success,
                    duration_ms=duration
                )

                self._record_attempt(attempt)

                if success:
                    self._connection_successful()
                    return True
                else:
                    attempt.error_message = "Connection failed"
                    self._connection_failed(attempt.error_message)

            except Exception as e:
                duration = (datetime.now() - attempt_start).total_seconds() * 1000
                error_msg = str(e)

                attempt = ConnectionAttempt(
                    attempt_number=self._retry_count + 1,
                    timestamp=attempt_start,
                    success=False,
                    duration_ms=duration,
                    error_message=error_msg
                )

                self._record_attempt(attempt)
                self._connection_failed(error_msg)

            # Prepare for next retry
            self._retry_count += 1

            if self._retry_count < self.max_retry_attempts:
                logger.warning(f"Connection failed, retrying in {self._current_retry_delay:.1f}s...")
                time.sleep(self._current_retry_delay)

                # Exponential backoff
                self._current_retry_delay = min(
                    self._current_retry_delay * self.backoff_multiplier,
                    self.max_retry_delay
                )

        # All retry attempts exhausted
        self._set_state(ConnectionState.FAILED)
        logger.error(f"Connection failed after {self.max_retry_attempts} attempts")
        return False

    def _connection_successful(self) -> None:
        """Handle successful connection."""
        self._connection_time = datetime.now()
        self._stats.last_successful_connection = self._connection_time
        self._retry_count = 0
        self._current_retry_delay = self.initial_retry_delay

        self._set_state(ConnectionState.CONNECTED)
        self._trigger_connection_callbacks(True)

        # Start connection monitoring
        self._start_monitoring()

        logger.info("Connection established successfully")

    def _connection_failed(self, error_message: str) -> None:
        """Handle connection failure."""
        self._stats.last_failure = datetime.now()
        self._trigger_connection_callbacks(False)

        logger.warning(f"Connection attempt failed: {error_message}")

    def disconnect(self) -> None:
        """Disconnect from device."""
        with self._lock:
            if self._state == ConnectionState.DISCONNECTED:
                return

            self._stop_monitoring_thread()
            self._connection_time = None
            self._set_state(ConnectionState.DISCONNECTED)

            logger.info("Disconnected from device")

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to device.

        Returns:
            bool: True if reconnection successful
        """
        logger.info("Attempting reconnection...")

        with self._lock:
            self._set_state(ConnectionState.RECONNECTING)
            self._stop_monitoring_thread()

            # Reset retry parameters for reconnection
            self._retry_count = 0
            self._current_retry_delay = self.initial_retry_delay

            return self._attempt_connection_with_retries()

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._state == ConnectionState.CONNECTED

    def get_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def get_uptime(self) -> Optional[timedelta]:
        """Get current connection uptime."""
        if self._connection_time and self._state == ConnectionState.CONNECTED:
            return datetime.now() - self._connection_time
        return None

    def get_stats(self) -> ConnectionStats:
        """Get connection statistics."""
        with self._lock:
            stats = ConnectionStats(
                total_attempts=self._stats.total_attempts,
                successful_connections=self._stats.successful_connections,
                failed_attempts=self._stats.failed_attempts,
                last_successful_connection=self._stats.last_successful_connection,
                last_failure=self._stats.last_failure,
                average_connection_time_ms=self._stats.average_connection_time_ms,
                recent_attempts=self._stats.recent_attempts.copy()
            )
            stats.current_uptime = self.get_uptime()
            return stats

    def _record_attempt(self, attempt: ConnectionAttempt) -> None:
        """Record connection attempt in statistics."""
        self._stats.total_attempts += 1
        self._stats.recent_attempts.append(attempt)

        # Keep only recent attempts (last 20)
        if len(self._stats.recent_attempts) > 20:
            self._stats.recent_attempts.pop(0)

        if attempt.success:
            self._stats.successful_connections += 1
        else:
            self._stats.failed_attempts += 1

        # Update average connection time
        if attempt.duration_ms is not None:
            successful_attempts = [a for a in self._stats.recent_attempts if a.success and a.duration_ms]
            if successful_attempts:
                total_time = sum(a.duration_ms for a in successful_attempts)
                self._stats.average_connection_time_ms = total_time / len(successful_attempts)

    def _set_state(self, new_state: ConnectionState) -> None:
        """Set connection state and trigger callbacks."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state

            logger.debug(f"Connection state: {old_state.value} -> {new_state.value}")
            self._trigger_state_callbacks(new_state)

    def _start_monitoring(self) -> None:
        """Start background connection monitoring."""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitoring.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_connection,
                daemon=True,
                name="ConnectionMonitor"
            )
            self._monitor_thread.start()
            logger.debug("Connection monitoring started")

    def _stop_monitoring_thread(self) -> None:
        """Stop background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._stop_monitoring.set()
            self._monitor_thread.join(timeout=5.0)
            logger.debug("Connection monitoring stopped")

    def _monitor_connection(self) -> None:
        """Background connection health monitoring."""
        check_interval = 5.0  # Check every 5 seconds

        while not self._stop_monitoring.wait(check_interval):
            try:
                if self._state == ConnectionState.CONNECTED:
                    # Check connection health
                    if not self.health_checker():
                        logger.warning("Connection health check failed, attempting reconnection")
                        threading.Thread(target=self.reconnect, daemon=True).start()
                        break

            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")

        logger.debug("Connection monitoring thread terminated")

    def register_state_callback(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register callback for state changes."""
        self._state_change_callbacks.append(callback)
        logger.debug("State change callback registered")

    def register_connection_callback(self, callback: Callable[[bool], None]) -> None:
        """Register callback for connection events."""
        self._connection_callbacks.append(callback)
        logger.debug("Connection event callback registered")

    def _trigger_state_callbacks(self, state: ConnectionState) -> None:
        """Trigger state change callbacks."""
        for callback in self._state_change_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def _trigger_connection_callbacks(self, connected: bool) -> None:
        """Trigger connection event callbacks."""
        for callback in self._connection_callbacks:
            try:
                callback(connected)
            except Exception as e:
                logger.error(f"Error in connection callback: {e}")

    def __str__(self) -> str:
        """String representation of connection manager."""
        uptime = self.get_uptime()
        uptime_str = f"{uptime.total_seconds():.1f}s" if uptime else "N/A"

        return (
            f"ConnectionManager(state={self._state.value}, "
            f"uptime={uptime_str}, success_rate={self._stats.success_rate:.2%})"
        )

    def __del__(self) -> None:
        """Cleanup on destruction."""
        try:
            self._stop_monitoring_thread()
        except:
            pass


# Utility functions for common connection patterns
def create_mcp2221_connection_manager(
    mcp2221_manager,
    retry_delay: float = 0.5,
    max_delay: float = 30.0,
    max_attempts: int = 5
) -> ConnectionManager:
    """
    Create a connection manager for MCP2221A device.

    Args:
        mcp2221_manager: MCP2221Manager instance
        retry_delay: Initial retry delay in seconds
        max_delay: Maximum retry delay in seconds
        max_attempts: Maximum retry attempts

    Returns:
        Configured ConnectionManager instance
    """
    def connector() -> bool:
        return mcp2221_manager.detect_device()

    def health_checker() -> bool:
        return mcp2221_manager.is_connected()

    manager = ConnectionManager(
        device_connector=connector,
        health_checker=health_checker,
        initial_retry_delay=retry_delay,
        max_retry_delay=max_delay,
        max_retry_attempts=max_attempts
    )

    logger.info("MCP2221A connection manager created")
    return manager


# Public API exports
__all__ = [
    'ConnectionManager',
    'ConnectionState',
    'ConnectionAttempt',
    'ConnectionStats',
    'create_mcp2221_connection_manager'
]