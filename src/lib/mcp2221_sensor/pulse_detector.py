"""
Pulse Detection Module for Filament Sensor Monitoring.

Provides edge detection and debouncing logic for movement sensors connected
to MCP2221A GPIO pins. Implements falling edge detection with configurable
debouncing to prevent false triggers from electrical noise.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PulseEvent:
    """Individual pulse detection event."""
    pin: int
    timestamp: datetime
    previous_state: bool
    current_state: bool
    debounced: bool = True

    def __post_init__(self):
        """Validate pulse event data."""
        if self.pin not in range(4):
            raise ValueError(f"Invalid pin number: {self.pin}")

    @property
    def is_falling_edge(self) -> bool:
        """Check if this is a falling edge (high to low transition)."""
        return self.previous_state and not self.current_state

    @property
    def is_rising_edge(self) -> bool:
        """Check if this is a rising edge (low to high transition)."""
        return not self.previous_state and self.current_state


@dataclass
class PulseStats:
    """Pulse detection statistics for a pin."""
    pin: int
    total_pulses: int = 0
    debounced_pulses: int = 0
    last_pulse_time: Optional[datetime] = None
    pulse_rate_hz: float = 0.0
    recent_pulses: deque = field(default_factory=lambda: deque(maxlen=10))

    def add_pulse(self, pulse_time: datetime, debounced: bool = True) -> None:
        """Add a pulse to statistics."""
        self.total_pulses += 1
        if debounced:
            self.debounced_pulses += 1

        self.last_pulse_time = pulse_time
        self.recent_pulses.append(pulse_time)

        # Calculate pulse rate from recent pulses
        if len(self.recent_pulses) >= 2:
            time_span = (self.recent_pulses[-1] - self.recent_pulses[0]).total_seconds()
            if time_span > 0:
                self.pulse_rate_hz = (len(self.recent_pulses) - 1) / time_span
            else:
                self.pulse_rate_hz = 0.0

    @property
    def time_since_last_pulse(self) -> Optional[timedelta]:
        """Time since last pulse."""
        if self.last_pulse_time:
            return datetime.now() - self.last_pulse_time
        return None


class PulseDetector:
    """
    Edge detection and debouncing for GPIO pulse monitoring.

    Implements falling edge detection with configurable debouncing to filter
    out electrical noise and false triggers from filament sensors.
    """

    def __init__(self, debounce_ms: int = 2):
        """
        Initialize pulse detector.

        Args:
            debounce_ms: Debounce time in milliseconds (default 2ms)
        """
        self.debounce_ms = debounce_ms
        self.debounce_seconds = debounce_ms / 1000.0

        # Pin state tracking
        self._pin_states: Dict[int, bool] = {}
        self._last_change_time: Dict[int, datetime] = {}
        self._pulse_stats: Dict[int, PulseStats] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Event callbacks
        self._pulse_callbacks: Dict[int, Callable[[PulseEvent], None]] = {}
        self._edge_callbacks: Dict[int, Callable[[PulseEvent], None]] = {}

        logger.info(f"PulseDetector initialized with {debounce_ms}ms debouncing")

    def register_pin(self, pin: int, initial_state: bool = True) -> None:
        """
        Register a pin for pulse detection.

        Args:
            pin: GPIO pin number (0-3)
            initial_state: Initial pin state (default True for pull-up)
        """
        if pin not in range(4):
            raise ValueError(f"Invalid pin number: {pin}")

        with self._lock:
            self._pin_states[pin] = initial_state
            self._last_change_time[pin] = datetime.now()
            self._pulse_stats[pin] = PulseStats(pin=pin)

        logger.debug(f"Pin {pin} registered with initial state: {initial_state}")

    def update_pin_state(self, pin: int, new_state: bool) -> Optional[PulseEvent]:
        """
        Update pin state and detect edges.

        Args:
            pin: GPIO pin number
            new_state: New pin state

        Returns:
            PulseEvent if edge detected and debounced, None otherwise
        """
        if pin not in self._pin_states:
            logger.warning(f"Pin {pin} not registered, ignoring state update")
            return None

        with self._lock:
            current_time = datetime.now()
            previous_state = self._pin_states[pin]

            # Check for state change
            if new_state == previous_state:
                return None

            # Check debouncing
            time_since_last_change = (current_time - self._last_change_time[pin]).total_seconds()
            is_debounced = time_since_last_change >= self.debounce_seconds

            # Create pulse event
            pulse_event = PulseEvent(
                pin=pin,
                timestamp=current_time,
                previous_state=previous_state,
                current_state=new_state,
                debounced=is_debounced
            )

            # Update pin state and timing
            self._pin_states[pin] = new_state
            self._last_change_time[pin] = current_time

            # Update statistics for debounced falling edges (pulses)
            if is_debounced and pulse_event.is_falling_edge:
                self._pulse_stats[pin].add_pulse(current_time, debounced=True)

            # Trigger callbacks
            if is_debounced:
                self._trigger_edge_callbacks(pulse_event)
                if pulse_event.is_falling_edge:
                    self._trigger_pulse_callbacks(pulse_event)

            logger.debug(
                f"Pin {pin}: {previous_state} -> {new_state}, "
                f"debounced={is_debounced}, falling_edge={pulse_event.is_falling_edge}"
            )

            return pulse_event if is_debounced else None

    def update_all_pins(self, pin_states: Dict[str, int]) -> Dict[int, Optional[PulseEvent]]:
        """
        Update multiple pin states simultaneously.

        Args:
            pin_states: Dictionary of pin states {"GP0": 1, "GP1": 0, ...}

        Returns:
            Dict mapping pin numbers to pulse events (None if no event)
        """
        events = {}

        # Convert GPIO names to pin numbers
        pin_mapping = {
            "GP0": 0,
            "GP1": 1,
            "GP2": 2,
            "GP3": 3
        }

        for gpio_name, state in pin_states.items():
            if gpio_name in pin_mapping:
                pin = pin_mapping[gpio_name]
                events[pin] = self.update_pin_state(pin, bool(state))

        return events

    def register_pulse_callback(self, pin: int, callback: Callable[[PulseEvent], None]) -> None:
        """
        Register callback for pulse events (falling edges).

        Args:
            pin: GPIO pin number
            callback: Function to call when pulse detected
        """
        self._pulse_callbacks[pin] = callback
        logger.debug(f"Pulse callback registered for pin {pin}")

    def register_edge_callback(self, pin: int, callback: Callable[[PulseEvent], None]) -> None:
        """
        Register callback for any edge events.

        Args:
            pin: GPIO pin number
            callback: Function to call when edge detected
        """
        self._edge_callbacks[pin] = callback
        logger.debug(f"Edge callback registered for pin {pin}")

    def _trigger_pulse_callbacks(self, event: PulseEvent) -> None:
        """Trigger pulse callbacks for an event."""
        callback = self._pulse_callbacks.get(event.pin)
        if callback:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in pulse callback for pin {event.pin}: {e}")

    def _trigger_edge_callbacks(self, event: PulseEvent) -> None:
        """Trigger edge callbacks for an event."""
        callback = self._edge_callbacks.get(event.pin)
        if callback:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in edge callback for pin {event.pin}: {e}")

    def get_pulse_count(self, pin: int) -> int:
        """Get total debounced pulse count for a pin."""
        with self._lock:
            if pin in self._pulse_stats:
                return self._pulse_stats[pin].debounced_pulses
            return 0

    def get_pulse_rate(self, pin: int) -> float:
        """Get current pulse rate in Hz for a pin."""
        with self._lock:
            if pin in self._pulse_stats:
                return self._pulse_stats[pin].pulse_rate_hz
            return 0.0

    def get_pin_state(self, pin: int) -> Optional[bool]:
        """Get current state of a pin."""
        with self._lock:
            return self._pin_states.get(pin)

    def get_time_since_last_pulse(self, pin: int) -> Optional[timedelta]:
        """Get time since last pulse on a pin."""
        with self._lock:
            if pin in self._pulse_stats:
                return self._pulse_stats[pin].time_since_last_pulse
            return None

    def get_statistics(self, pin: int) -> Optional[PulseStats]:
        """Get detailed statistics for a pin."""
        with self._lock:
            return self._pulse_stats.get(pin)

    def get_all_statistics(self) -> Dict[int, PulseStats]:
        """Get statistics for all registered pins."""
        with self._lock:
            return self._pulse_stats.copy()

    def reset_pin_statistics(self, pin: int) -> None:
        """Reset pulse statistics for a pin."""
        with self._lock:
            if pin in self._pulse_stats:
                self._pulse_stats[pin] = PulseStats(pin=pin)
                logger.info(f"Statistics reset for pin {pin}")

    def reset_all_statistics(self) -> None:
        """Reset pulse statistics for all pins."""
        with self._lock:
            for pin in self._pulse_stats:
                self._pulse_stats[pin] = PulseStats(pin=pin)
            logger.info("All pin statistics reset")

    @property
    def debounce_time_ms(self) -> int:
        """Get current debounce time in milliseconds."""
        return self.debounce_ms

    @debounce_time_ms.setter
    def debounce_time_ms(self, value: int) -> None:
        """Set debounce time in milliseconds."""
        if value < 0:
            raise ValueError("Debounce time cannot be negative")

        self.debounce_ms = value
        self.debounce_seconds = value / 1000.0
        logger.info(f"Debounce time updated to {value}ms")

    def __str__(self) -> str:
        """String representation of detector state."""
        with self._lock:
            registered_pins = list(self._pin_states.keys())
            total_pulses = sum(stats.debounced_pulses for stats in self._pulse_stats.values())

            return (
                f"PulseDetector(debounce={self.debounce_ms}ms, "
                f"pins={registered_pins}, total_pulses={total_pulses})"
            )


# Utility functions for common use cases
def create_sensor_pulse_detector(
    movement_pins: list[int],
    debounce_ms: int = 2
) -> PulseDetector:
    """
    Create a pulse detector configured for filament sensors.

    Args:
        movement_pins: List of GPIO pins used for movement detection
        debounce_ms: Debounce time in milliseconds

    Returns:
        Configured PulseDetector instance
    """
    detector = PulseDetector(debounce_ms=debounce_ms)

    for pin in movement_pins:
        detector.register_pin(pin, initial_state=True)  # Pull-up default

    logger.info(f"Sensor pulse detector created for pins {movement_pins}")
    return detector


# Public API exports
__all__ = [
    'PulseDetector',
    'PulseEvent',
    'PulseStats',
    'create_sensor_pulse_detector'
]