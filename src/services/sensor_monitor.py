"""SensorMonitor service for polling filament sensors and managing readings."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import threading
import weakref

import structlog

from ..models import (
    SystemStatus,
    SensorConfiguration,
    SensorReading,
    AlertEvent,
    AlertType,
    AlertSeverity
)
from ..lib.mcp2221_sensor import MCP2221Connection, PulseDetector


logger = structlog.get_logger(__name__)


class SensorMonitor:
    """Main sensor monitoring service for polling and managing sensor readings."""

    def __init__(self,
                 system_status: Optional[SystemStatus] = None,
                 hardware_connection: Optional[MCP2221Connection] = None):
        """Initialize the sensor monitor."""
        self.system_status = system_status or SystemStatus.get_instance()
        self.hardware_connection = hardware_connection

        # Monitoring state
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

        # Sensor pulse detectors
        self.pulse_detectors: Dict[int, PulseDetector] = {}

        # Monitoring configuration
        self.polling_interval_ms = 100  # Default
        self.movement_timeout_ms = 5000  # Default
        self.runout_debounce_ms = 500  # Default

        # Callback for external notifications (like WebSocket)
        self.update_callbacks: weakref.WeakSet = weakref.WeakSet()

        # Performance tracking
        self.last_poll_duration_ms = 0.0
        self.poll_count = 0
        self.error_count = 0

    def add_update_callback(self, callback: Callable[[SensorReading], None]) -> None:
        """Add callback to be notified of sensor updates."""
        self.update_callbacks.add(callback)

    def remove_update_callback(self, callback: Callable[[SensorReading], None]) -> None:
        """Remove update callback."""
        self.update_callbacks.discard(callback)

    async def start_monitoring(self, configuration: SensorConfiguration) -> None:
        """Start the sensor monitoring service."""
        with self._lock:
            if self.is_running:
                logger.warning("Sensor monitor already running")
                return

            logger.info("Starting sensor monitor")

            # Update configuration
            self.polling_interval_ms = configuration.polling.polling_interval_ms
            self.movement_timeout_ms = configuration.detection.movement_timeout_ms
            self.runout_debounce_ms = configuration.detection.runout_debounce_ms

            # Initialize hardware connection if not provided
            if self.hardware_connection is None:
                try:
                    self.hardware_connection = MCP2221Connection()
                    await self._async_hardware_connect()
                except Exception as e:
                    logger.error("Failed to initialize hardware connection", error=str(e))
                    self.system_status.update_hardware_status(False)
                    self.system_status.add_alert(AlertEvent.create_hardware_error(
                        f"Failed to connect to MCP2221A: {str(e)}"
                    ))
                    return

            # Initialize pulse detectors for enabled sensors
            await self._initialize_pulse_detectors(configuration)

            # Start monitoring task
            self.is_running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())

            # Update system status
            self.system_status.update_hardware_status(True)
            self.system_status.add_alert(AlertEvent(
                alert_type=AlertType.SYSTEM_STARTED,
                severity=AlertSeverity.INFO,
                message="Sensor monitoring started"
            ))

            logger.info("Sensor monitor started",
                       polling_interval_ms=self.polling_interval_ms,
                       enabled_sensors=len(self.pulse_detectors))

    async def stop_monitoring(self) -> None:
        """Stop the sensor monitoring service."""
        with self._lock:
            if not self.is_running:
                logger.warning("Sensor monitor not running")
                return

            logger.info("Stopping sensor monitor")

            self.is_running = False

            # Cancel monitoring task
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            # Clean up pulse detectors
            self.pulse_detectors.clear()

            # Update system status
            self.system_status.add_alert(AlertEvent(
                alert_type=AlertType.SYSTEM_STOPPED,
                severity=AlertSeverity.INFO,
                message="Sensor monitoring stopped"
            ))

            logger.info("Sensor monitor stopped")

    async def update_configuration(self, configuration: SensorConfiguration) -> None:
        """Update monitoring configuration dynamically."""
        logger.info("Updating sensor monitor configuration")

        # Update polling interval
        old_interval = self.polling_interval_ms
        self.polling_interval_ms = configuration.polling.polling_interval_ms
        self.movement_timeout_ms = configuration.detection.movement_timeout_ms
        self.runout_debounce_ms = configuration.detection.runout_debounce_ms

        # Reinitialize pulse detectors if sensor configuration changed
        await self._initialize_pulse_detectors(configuration)

        # Log configuration change
        self.system_status.add_alert(AlertEvent.create_configuration_change(
            f"Monitoring configuration updated: polling interval {old_interval}ms → {self.polling_interval_ms}ms",
            {
                "old_polling_ms": old_interval,
                "new_polling_ms": self.polling_interval_ms,
                "movement_timeout_ms": self.movement_timeout_ms,
                "runout_debounce_ms": self.runout_debounce_ms
            }
        ))

    async def get_current_readings(self) -> Dict[int, Optional[SensorReading]]:
        """Get current sensor readings."""
        return {
            sensor_id: self.system_status.get_sensor_reading(sensor_id)
            for sensor_id in [1, 2]
        }

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring performance statistics."""
        return {
            "is_running": self.is_running,
            "polling_interval_ms": self.polling_interval_ms,
            "last_poll_duration_ms": self.last_poll_duration_ms,
            "poll_count": self.poll_count,
            "error_count": self.error_count,
            "enabled_sensors": len(self.pulse_detectors),
            "hardware_connected": self.system_status.health.hardware_connected
        }

    async def _async_hardware_connect(self) -> None:
        """Connect to hardware in async context."""
        def connect():
            return self.hardware_connection.connect()

        # Run hardware connection in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, connect)

    async def _initialize_pulse_detectors(self, configuration: SensorConfiguration) -> None:
        """Initialize pulse detectors for enabled sensors."""
        self.pulse_detectors.clear()

        for sensor_config in configuration.sensors:
            if sensor_config.enabled:
                try:
                    # Create pulse detector
                    detector = PulseDetector(
                        sensor_id=sensor_config.id,
                        mm_per_pulse=configuration.calibration.mm_per_pulse,
                        movement_timeout_ms=self.movement_timeout_ms,
                        runout_debounce_ms=self.runout_debounce_ms
                    )

                    self.pulse_detectors[sensor_config.id] = detector

                    logger.info("Initialized pulse detector",
                               sensor_id=sensor_config.id,
                               sensor_name=sensor_config.name)

                except Exception as e:
                    logger.error("Failed to initialize pulse detector",
                               sensor_id=sensor_config.id,
                               error=str(e))

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Sensor monitor loop started")

        while self.is_running:
            try:
                start_time = datetime.now()

                # Poll all sensors
                await self._poll_sensors()

                # Track performance
                poll_duration = (datetime.now() - start_time).total_seconds() * 1000
                self.last_poll_duration_ms = poll_duration
                self.poll_count += 1

                # Update performance metrics
                self.system_status.metrics.performance.update_polling_metrics(
                    poll_duration_ms=poll_duration,
                    sensor_count=len(self.pulse_detectors)
                )

                # Sleep until next poll
                sleep_ms = max(1, self.polling_interval_ms - poll_duration)
                await asyncio.sleep(sleep_ms / 1000.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_count += 1
                logger.error("Error in monitoring loop", error=str(e))

                # Add error alert
                self.system_status.add_alert(AlertEvent.create_hardware_error(
                    f"Sensor monitoring error: {str(e)}"
                ))

                # Back off on errors
                await asyncio.sleep(1.0)

        logger.info("Sensor monitor loop stopped")

    async def _poll_sensors(self) -> None:
        """Poll all enabled sensors for readings."""
        if not self.hardware_connection or not self.hardware_connection.is_connected:
            # Try to reconnect
            await self._check_hardware_connection()
            return

        # Read GPIO states
        gpio_states = await self._read_gpio_states()

        # Process readings for each sensor
        for sensor_id, detector in self.pulse_detectors.items():
            try:
                # Update pulse detector with GPIO states
                reading = await self._process_sensor_reading(sensor_id, detector, gpio_states)

                if reading:
                    # Update system status
                    self.system_status.update_sensor_reading(reading)

                    # Update session metrics
                    await self._update_session_metrics(reading)

                    # Check for alerts
                    await self._check_sensor_alerts(reading)

                    # Notify callbacks
                    await self._notify_callbacks(reading)

            except Exception as e:
                logger.error("Error processing sensor reading",
                           sensor_id=sensor_id,
                           error=str(e))

    async def _read_gpio_states(self) -> Dict[str, bool]:
        """Read current GPIO states from hardware."""
        try:
            def read_gpio():
                return self.hardware_connection.read_gpio_states()

            loop = asyncio.get_event_loop()
            gpio_states = await loop.run_in_executor(None, read_gpio)
            return gpio_states

        except Exception as e:
            logger.error("Failed to read GPIO states", error=str(e))
            return {}

    async def _process_sensor_reading(self,
                                    sensor_id: int,
                                    detector: PulseDetector,
                                    gpio_states: Dict[str, bool]) -> Optional[SensorReading]:
        """Process GPIO states into sensor reading."""
        try:
            # Determine GPIO pins for this sensor
            movement_pin = f"GP{(sensor_id - 1) * 2}"      # GP0 for sensor 1, GP2 for sensor 2
            runout_pin = f"GP{(sensor_id - 1) * 2 + 1}"    # GP1 for sensor 1, GP3 for sensor 2

            # Get pin states
            movement_state = gpio_states.get(movement_pin, False)
            runout_state = gpio_states.get(runout_pin, False)

            # Update detector
            reading = detector.process_gpio_states(movement_state, not runout_state)  # Invert runout logic

            if reading:
                # Add GPIO state for debugging
                reading.raw_gpio_state = {
                    movement_pin: movement_state,
                    runout_pin: runout_state
                }

            return reading

        except Exception as e:
            logger.error("Error processing sensor reading",
                       sensor_id=sensor_id,
                       error=str(e))
            return None

    async def _update_session_metrics(self, reading: SensorReading) -> None:
        """Update session metrics with new reading."""
        try:
            sensor_metrics = getattr(self.system_status.metrics, f"sensor{reading.sensor_id}")
            sensor_metrics.update_from_reading(reading)
        except Exception as e:
            logger.error("Error updating session metrics", error=str(e))

    async def _check_sensor_alerts(self, reading: SensorReading) -> None:
        """Check for sensor-related alerts."""
        try:
            current_time = datetime.now()

            # Check for runout condition
            if not reading.has_filament:
                self.system_status.add_alert(AlertEvent.create_filament_runout(
                    sensor_id=reading.sensor_id,
                    message=f"Filament runout detected on sensor {reading.sensor_id}"
                ))

            # Check for movement after long inactivity
            sensor_metrics = getattr(self.system_status.metrics, f"sensor{reading.sensor_id}")
            if (reading.is_moving and
                sensor_metrics.last_movement and
                current_time - sensor_metrics.last_movement > timedelta(minutes=10)):

                self.system_status.add_alert(AlertEvent(
                    alert_type=AlertType.SENSOR_MOVEMENT,
                    severity=AlertSeverity.INFO,
                    message=f"Sensor {reading.sensor_id} movement resumed after inactivity",
                    sensor_id=reading.sensor_id
                ))

        except Exception as e:
            logger.error("Error checking sensor alerts", error=str(e))

    async def _notify_callbacks(self, reading: SensorReading) -> None:
        """Notify registered callbacks of sensor updates."""
        try:
            # Create a copy of the weak set to avoid modification during iteration
            callbacks = list(self.update_callbacks)

            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(reading)
                    else:
                        callback(reading)
                except Exception as e:
                    logger.warning("Error in update callback", error=str(e))

        except Exception as e:
            logger.error("Error notifying callbacks", error=str(e))

    async def _check_hardware_connection(self) -> None:
        """Check and attempt to restore hardware connection."""
        try:
            if self.hardware_connection:
                was_connected = self.hardware_connection.is_connected

                # Try to reconnect
                def reconnect():
                    return self.hardware_connection.connect()

                loop = asyncio.get_event_loop()
                is_connected = await loop.run_in_executor(None, reconnect)

                # Update status if connection state changed
                if was_connected != is_connected:
                    self.system_status.update_hardware_status(is_connected)

                    if is_connected:
                        logger.info("Hardware connection restored")
                    else:
                        logger.warning("Hardware connection lost")

        except Exception as e:
            logger.error("Error checking hardware connection", error=str(e))
            self.system_status.update_hardware_status(False)


# Export the main component
__all__ = ["SensorMonitor"]