"""
Integration tests for pulse detection and debouncing.

These tests validate edge detection, pulse counting, debouncing logic,
and accurate filament movement calculation from sensor pulses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
import time
import threading
from typing import List, Dict, Tuple

# These imports will fail initially - that's expected for TDD
try:
    from src.lib.mcp2221_sensor.pulse_detector import PulseDetector
    from src.lib.mcp2221_sensor.debouncer import SignalDebouncer
    from src.services.sensor_monitor import SensorMonitor
    from src.models.sensor_reading import PulseEvent, MovementCalculation
except ImportError:
    # Expected failure - modules don't exist yet
    PulseDetector = None
    SignalDebouncer = None
    SensorMonitor = None
    PulseEvent = None
    MovementCalculation = None


@pytest.mark.integration
class TestPulseDetection:
    """Test pulse detection and debouncing for filament movement."""

    @pytest.fixture
    def pulse_config(self):
        """Configuration for pulse detection."""
        return {
            "mm_per_pulse": 2.88,
            "debounce_ms": 50,
            "edge_detection": "falling",
            "pullup_enabled": True,
            "max_pulse_frequency_hz": 1000,
            "min_pulse_width_ms": 1
        }

    @pytest.fixture
    def mock_gpio_sequence(self):
        """Mock GPIO sequence simulating sensor pulses."""
        # Sequence: High -> Low -> High (one complete pulse)
        return [
            {"timestamp": 0.000, "value": 1},    # Initial high
            {"timestamp": 0.010, "value": 0},    # Falling edge (pulse start)
            {"timestamp": 0.015, "value": 1},    # Rising edge (pulse end)
            {"timestamp": 0.020, "value": 1},    # Stay high
            {"timestamp": 0.030, "value": 0},    # Second pulse falling
            {"timestamp": 0.035, "value": 1},    # Second pulse rising
            {"timestamp": 0.040, "value": 1},    # Stay high
        ]

    def test_pulse_detector_initialization(self, pulse_config):
        """Test pulse detector initialization."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(
            pin_number=0,
            config=pulse_config
        )

        assert detector.pin_number == 0
        assert detector.mm_per_pulse == 2.88
        assert detector.debounce_ms == 50
        assert detector.edge_detection == "falling"
        assert detector.pulse_count == 0
        assert detector.total_movement_mm == 0.0

    def test_falling_edge_detection(self, pulse_config, mock_gpio_sequence):
        """Test detection of falling edge pulses."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        pulse_events = []
        for gpio_state in mock_gpio_sequence:
            event = detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if event:
                pulse_events.append(event)

        # Should detect 2 falling edges
        assert len(pulse_events) == 2
        assert pulse_events[0].timestamp == 0.010
        assert pulse_events[1].timestamp == 0.030
        assert detector.pulse_count == 2

    def test_rising_edge_detection(self, pulse_config, mock_gpio_sequence):
        """Test detection of rising edge pulses."""
        pulse_config["edge_detection"] = "rising"

        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        pulse_events = []
        for gpio_state in mock_gpio_sequence:
            event = detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if event:
                pulse_events.append(event)

        # Should detect 2 rising edges
        assert len(pulse_events) == 2
        assert pulse_events[0].timestamp == 0.015
        assert pulse_events[1].timestamp == 0.035
        assert detector.pulse_count == 2

    def test_signal_debouncing(self, pulse_config):
        """Test signal debouncing to filter noise."""
        pulse_config["debounce_ms"] = 20  # 20ms debounce

        # Noisy signal sequence with rapid transitions
        noisy_sequence = [
            {"timestamp": 0.000, "value": 1},
            {"timestamp": 0.005, "value": 0},  # Falling edge
            {"timestamp": 0.008, "value": 1},  # Noise - too fast
            {"timestamp": 0.010, "value": 0},  # Noise - too fast
            {"timestamp": 0.012, "value": 1},  # Noise - too fast
            {"timestamp": 0.030, "value": 0},  # Valid falling edge (after debounce)
            {"timestamp": 0.055, "value": 1},  # Valid rising edge
        ]

        # This will fail initially - SignalDebouncer doesn't exist
        debouncer = SignalDebouncer(debounce_ms=20)

        debounced_events = []
        for gpio_state in noisy_sequence:
            debounced = debouncer.process_signal(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if debounced is not None:
                debounced_events.append(debounced)

        # Should filter out noise and only pass valid transitions
        assert len(debounced_events) >= 2  # At least 2 valid transitions

        # Verify debouncing timing
        time_between_events = debounced_events[1]["timestamp"] - debounced_events[0]["timestamp"]
        assert time_between_events >= 0.020  # At least 20ms apart

    def test_movement_calculation(self, pulse_config, mock_gpio_sequence):
        """Test accurate movement calculation from pulses."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Process all GPIO states
        for gpio_state in mock_gpio_sequence:
            detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )

        # Calculate movement
        movement = detector.calculate_movement()

        # 2 pulses × 2.88 mm/pulse = 5.76 mm
        assert movement.pulse_count == 2
        assert movement.total_mm == pytest.approx(5.76, rel=1e-2)
        assert movement.average_pulse_frequency > 0

    def test_pulse_frequency_calculation(self, pulse_config):
        """Test pulse frequency calculation."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Generate pulses at known frequency (10 Hz = 100ms period)
        pulse_times = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]  # 5 pulses over 0.5s = 10 Hz

        for i, timestamp in enumerate(pulse_times):
            # Simulate falling edge
            detector.process_gpio_state(0, timestamp)
            # Simulate rising edge
            detector.process_gpio_state(1, timestamp + 0.01)

        movement = detector.calculate_movement()

        # Should detect ~10 Hz frequency
        assert movement.average_pulse_frequency == pytest.approx(10.0, rel=0.1)

    def test_high_frequency_pulse_handling(self, pulse_config):
        """Test handling of high-frequency pulses."""
        pulse_config["max_pulse_frequency_hz"] = 500  # 500 Hz max

        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Generate pulses at 1000 Hz (too fast)
        high_freq_pulses = []
        for i in range(20):
            timestamp = i * 0.001  # 1ms intervals = 1000 Hz
            high_freq_pulses.extend([
                {"timestamp": timestamp, "value": 0},
                {"timestamp": timestamp + 0.0005, "value": 1}
            ])

        pulse_count = 0
        for gpio_state in high_freq_pulses:
            event = detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if event:
                pulse_count += 1

        # Should reject pulses above maximum frequency
        assert pulse_count < 10  # Much less than the 20 attempted pulses

    def test_pulse_width_validation(self, pulse_config):
        """Test minimum pulse width validation."""
        pulse_config["min_pulse_width_ms"] = 5  # 5ms minimum width

        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Test pulses with different widths
        pulse_sequences = [
            # Valid pulse (10ms width)
            [{"timestamp": 0.000, "value": 1},
             {"timestamp": 0.010, "value": 0},  # Falling edge
             {"timestamp": 0.020, "value": 1}], # Rising edge (10ms width)

            # Invalid pulse (2ms width - too narrow)
            [{"timestamp": 0.030, "value": 1},
             {"timestamp": 0.040, "value": 0},  # Falling edge
             {"timestamp": 0.042, "value": 1}], # Rising edge (2ms width)
        ]

        valid_pulses = 0
        for sequence in pulse_sequences:
            for gpio_state in sequence:
                event = detector.process_gpio_state(
                    gpio_state["value"],
                    gpio_state["timestamp"]
                )
                if event and event.is_valid:
                    valid_pulses += 1

        # Only the first pulse should be valid
        assert valid_pulses == 1

    def test_concurrent_pulse_detection(self, pulse_config):
        """Test thread-safe pulse detection."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        def pulse_generator(start_time, pulse_count):
            """Generate pulses in a thread."""
            results = []
            for i in range(pulse_count):
                timestamp = start_time + (i * 0.01)  # 10ms intervals

                # Falling edge
                event1 = detector.process_gpio_state(0, timestamp)
                if event1:
                    results.append(event1)

                # Rising edge
                event2 = detector.process_gpio_state(1, timestamp + 0.005)
                if event2:
                    results.append(event2)

            return results

        # Start multiple threads generating pulses
        threads = []
        thread_results = []

        for i in range(3):
            thread = threading.Thread(
                target=lambda: thread_results.append(
                    pulse_generator(i * 0.1, 5)
                )
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify thread safety - no crashes or data corruption
        total_events = sum(len(results) for results in thread_results)
        assert total_events > 0
        assert detector.pulse_count >= 0

    def test_pulse_direction_detection(self, pulse_config):
        """Test detection of filament direction (forward/reverse)."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Simulate forward movement pattern
        forward_sequence = [
            {"timestamp": 0.000, "value": 1},
            {"timestamp": 0.010, "value": 0},  # Forward pulse
            {"timestamp": 0.015, "value": 1},
            {"timestamp": 0.025, "value": 0},  # Forward pulse
            {"timestamp": 0.030, "value": 1},
        ]

        forward_events = []
        for gpio_state in forward_sequence:
            event = detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if event:
                forward_events.append(event)

        # All events should be forward direction
        for event in forward_events:
            assert event.direction == "forward"

        # Calculate forward movement
        movement = detector.calculate_movement()
        assert movement.total_mm > 0  # Positive movement

    def test_pulse_detection_accuracy(self, pulse_config):
        """Test accuracy of pulse detection under various conditions."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Test with known pulse pattern
        expected_pulses = 10
        pulse_interval = 0.02  # 20ms = 50 Hz

        for i in range(expected_pulses):
            timestamp = i * pulse_interval

            # Generate clean pulse
            detector.process_gpio_state(1, timestamp)         # High
            detector.process_gpio_state(0, timestamp + 0.001) # Low (falling edge)
            detector.process_gpio_state(1, timestamp + 0.010) # High (rising edge)

        # Verify accuracy
        assert detector.pulse_count == expected_pulses

        movement = detector.calculate_movement()
        expected_movement = expected_pulses * pulse_config["mm_per_pulse"]
        assert movement.total_mm == pytest.approx(expected_movement, rel=1e-6)

    def test_pulse_detection_with_noise(self, pulse_config):
        """Test pulse detection robustness against electrical noise."""
        pulse_config["debounce_ms"] = 10  # 10ms debounce for noise filtering

        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Noisy signal with genuine pulses mixed with noise
        noisy_signal = [
            {"timestamp": 0.000, "value": 1},   # Start high
            {"timestamp": 0.002, "value": 0},   # Noise glitch
            {"timestamp": 0.003, "value": 1},   # Return high (noise)
            {"timestamp": 0.020, "value": 0},   # Real falling edge
            {"timestamp": 0.022, "value": 1},   # Noise during low
            {"timestamp": 0.024, "value": 0},   # Return low (noise)
            {"timestamp": 0.030, "value": 1},   # Real rising edge
            {"timestamp": 0.045, "value": 0},   # Another real pulse
            {"timestamp": 0.055, "value": 1},   # End pulse
        ]

        genuine_pulses = 0
        for gpio_state in noisy_signal:
            event = detector.process_gpio_state(
                gpio_state["value"],
                gpio_state["timestamp"]
            )
            if event and event.is_valid:
                genuine_pulses += 1

        # Should detect only genuine pulses, filtering out noise
        assert genuine_pulses == 2  # Two real pulse events

    def test_movement_speed_calculation(self, pulse_config):
        """Test calculation of filament movement speed."""
        # This will fail initially - PulseDetector doesn't exist
        detector = PulseDetector(pin_number=0, config=pulse_config)

        # Generate pulses at consistent rate
        pulse_rate_hz = 20  # 20 pulses per second
        pulse_interval = 1.0 / pulse_rate_hz  # 50ms

        for i in range(5):  # 5 pulses over 0.2 seconds
            timestamp = i * pulse_interval
            detector.process_gpio_state(0, timestamp)      # Falling edge
            detector.process_gpio_state(1, timestamp + 0.001)  # Rising edge

        movement = detector.calculate_movement()

        # Calculate expected speed: 20 Hz × 2.88 mm/pulse = 57.6 mm/s
        expected_speed_mm_s = pulse_rate_hz * pulse_config["mm_per_pulse"]

        assert movement.speed_mm_per_second == pytest.approx(expected_speed_mm_s, rel=0.1)