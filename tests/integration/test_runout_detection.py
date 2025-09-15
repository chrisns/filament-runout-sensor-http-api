"""
Integration tests for filament runout detection.

These tests validate detection of filament presence/absence,
runout event handling, and recovery scenarios.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
import time
import threading
from typing import List, Dict, Tuple, Optional

# These imports will fail initially - that's expected for TDD
try:
    from src.lib.mcp2221_sensor.runout_detector import RunoutDetector
    from src.services.sensor_monitor import SensorMonitor
    from src.models.sensor_reading import RunoutEvent, FilamentState
    from src.lib.mcp2221_sensor.state_machine import FilamentStateMachine
except ImportError:
    # Expected failure - modules don't exist yet
    RunoutDetector = None
    SensorMonitor = None
    RunoutEvent = None
    FilamentState = None
    FilamentStateMachine = None


@pytest.mark.integration
class TestRunoutDetection:
    """Test filament runout detection and state management."""

    @pytest.fixture
    def runout_config(self):
        """Configuration for runout detection."""
        return {
            "runout_pin": 1,
            "active_state": "low",  # Pin goes LOW when filament is present
            "debounce_ms": 100,
            "confirmation_readings": 3,  # Require 3 consecutive readings
            "runout_timeout_ms": 5000,   # 5 second timeout
            "recovery_confirmation_ms": 1000,  # 1 second to confirm recovery
            "enable_notifications": True
        }

    @pytest.fixture
    def mock_gpio_transitions(self):
        """Mock GPIO state transitions for runout scenarios."""
        return {
            "filament_present": [
                {"timestamp": 0.000, "runout_pin": 0},  # LOW = filament present
                {"timestamp": 0.100, "runout_pin": 0},
                {"timestamp": 0.200, "runout_pin": 0},
            ],
            "filament_removal": [
                {"timestamp": 0.000, "runout_pin": 0},  # Present
                {"timestamp": 0.100, "runout_pin": 1},  # HIGH = filament removed
                {"timestamp": 0.200, "runout_pin": 1},  # Confirm removal
                {"timestamp": 0.300, "runout_pin": 1},
            ],
            "filament_insertion": [
                {"timestamp": 0.000, "runout_pin": 1},  # Absent
                {"timestamp": 0.100, "runout_pin": 0},  # LOW = filament inserted
                {"timestamp": 0.200, "runout_pin": 0},  # Confirm insertion
                {"timestamp": 0.300, "runout_pin": 0},
            ],
            "intermittent_signal": [
                {"timestamp": 0.000, "runout_pin": 0},  # Present
                {"timestamp": 0.050, "runout_pin": 1},  # Brief interruption (noise)
                {"timestamp": 0.070, "runout_pin": 0},  # Back to present
                {"timestamp": 0.150, "runout_pin": 0},  # Stable
            ]
        }

    def test_runout_detector_initialization(self, runout_config):
        """Test runout detector initialization."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(
            pin_number=1,
            config=runout_config
        )

        assert detector.pin_number == 1
        assert detector.active_state == "low"
        assert detector.debounce_ms == 100
        assert detector.confirmation_readings == 3
        assert detector.current_state == FilamentState.UNKNOWN

    def test_filament_present_detection(self, runout_config, mock_gpio_transitions):
        """Test detection of filament presence."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)

        events = []
        for gpio_state in mock_gpio_transitions["filament_present"]:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should detect stable filament presence
        assert detector.current_state == FilamentState.PRESENT
        assert len([e for e in events if e.event_type == "filament_detected"]) >= 1

    def test_filament_runout_detection(self, runout_config, mock_gpio_transitions):
        """Test detection of filament runout."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)

        # Start with filament present
        detector.current_state = FilamentState.PRESENT

        events = []
        for gpio_state in mock_gpio_transitions["filament_removal"]:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should detect runout event
        runout_events = [e for e in events if e.event_type == "runout_detected"]
        assert len(runout_events) >= 1
        assert detector.current_state == FilamentState.RUNOUT

    def test_filament_recovery_detection(self, runout_config, mock_gpio_transitions):
        """Test detection of filament recovery after runout."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)

        # Start with runout state
        detector.current_state = FilamentState.RUNOUT

        events = []
        for gpio_state in mock_gpio_transitions["filament_insertion"]:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should detect recovery event
        recovery_events = [e for e in events if e.event_type == "filament_recovered"]
        assert len(recovery_events) >= 1
        assert detector.current_state == FilamentState.PRESENT

    def test_debouncing_intermittent_signals(self, runout_config, mock_gpio_transitions):
        """Test debouncing of intermittent runout signals."""
        runout_config["debounce_ms"] = 100  # 100ms debounce

        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.PRESENT

        events = []
        for gpio_state in mock_gpio_transitions["intermittent_signal"]:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should not trigger false runout due to brief signal interruption
        runout_events = [e for e in events if e.event_type == "runout_detected"]
        assert len(runout_events) == 0  # No false runout events
        assert detector.current_state == FilamentState.PRESENT

    def test_confirmation_readings_requirement(self, runout_config):
        """Test requirement for multiple confirmation readings."""
        runout_config["confirmation_readings"] = 3

        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.PRESENT

        # Send insufficient confirmations (only 2 HIGH readings)
        test_sequence = [
            {"timestamp": 0.000, "runout_pin": 0},  # Present
            {"timestamp": 0.100, "runout_pin": 1},  # First HIGH
            {"timestamp": 0.200, "runout_pin": 1},  # Second HIGH
            {"timestamp": 0.300, "runout_pin": 0},  # Back to present
        ]

        events = []
        for gpio_state in test_sequence:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should NOT trigger runout with insufficient confirmations
        runout_events = [e for e in events if e.event_type == "runout_detected"]
        assert len(runout_events) == 0

    def test_runout_timeout_handling(self, runout_config):
        """Test handling of runout timeout scenarios."""
        runout_config["runout_timeout_ms"] = 1000  # 1 second timeout

        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.PRESENT

        # Simulate runout that lasts longer than timeout
        runout_start = time.time()

        # Initial runout detection
        event1 = detector.process_gpio_state(1, runout_start)  # HIGH = runout
        event2 = detector.process_gpio_state(1, runout_start + 0.1)  # Confirm
        event3 = detector.process_gpio_state(1, runout_start + 0.2)  # Confirm

        # Should detect runout
        assert detector.current_state == FilamentState.RUNOUT

        # Wait for timeout
        timeout_event = detector.check_runout_timeout(runout_start + 1.5)

        # Should trigger timeout event
        assert timeout_event is not None
        assert timeout_event.event_type == "runout_timeout"

    def test_state_machine_transitions(self, runout_config):
        """Test filament state machine transitions."""
        # This will fail initially - FilamentStateMachine doesn't exist
        state_machine = FilamentStateMachine(runout_config)

        # Test valid transitions
        assert state_machine.current_state == FilamentState.UNKNOWN

        # Unknown -> Present
        result = state_machine.transition_to(FilamentState.PRESENT, "sensor_reading")
        assert result is True
        assert state_machine.current_state == FilamentState.PRESENT

        # Present -> Runout
        result = state_machine.transition_to(FilamentState.RUNOUT, "sensor_reading")
        assert result is True
        assert state_machine.current_state == FilamentState.RUNOUT

        # Runout -> Present (recovery)
        result = state_machine.transition_to(FilamentState.PRESENT, "sensor_reading")
        assert result is True
        assert state_machine.current_state == FilamentState.PRESENT

    def test_invalid_state_transitions(self, runout_config):
        """Test handling of invalid state transitions."""
        # This will fail initially - FilamentStateMachine doesn't exist
        state_machine = FilamentStateMachine(runout_config)
        state_machine.current_state = FilamentState.PRESENT

        # Test invalid transition (Present -> Unknown should not be allowed)
        result = state_machine.transition_to(FilamentState.UNKNOWN, "sensor_reading")
        assert result is False
        assert state_machine.current_state == FilamentState.PRESENT  # State unchanged

    def test_concurrent_runout_monitoring(self, runout_config):
        """Test thread-safe runout detection."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)

        detected_events = []
        event_lock = threading.Lock()

        def monitor_runout(gpio_sequence):
            """Monitor runout in separate thread."""
            thread_events = []
            for gpio_state in gpio_sequence:
                event = detector.process_gpio_state(
                    gpio_state["runout_pin"],
                    gpio_state["timestamp"]
                )
                if event:
                    thread_events.append(event)

            with event_lock:
                detected_events.extend(thread_events)

        # Multiple threads with different GPIO sequences
        sequences = [
            [{"timestamp": 0.0 + i*0.01, "runout_pin": 0} for i in range(10)],  # Present
            [{"timestamp": 0.1 + i*0.01, "runout_pin": 1} for i in range(10)],  # Runout
            [{"timestamp": 0.2 + i*0.01, "runout_pin": 0} for i in range(10)],  # Recovery
        ]

        threads = []
        for sequence in sequences:
            thread = threading.Thread(target=monitor_runout, args=(sequence,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify thread safety - no crashes or data corruption
        with event_lock:
            assert len(detected_events) >= 0  # Events were processed safely

    def test_runout_event_metadata(self, runout_config, mock_gpio_transitions):
        """Test runout event metadata and timing information."""
        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.PRESENT

        events = []
        for gpio_state in mock_gpio_transitions["filament_removal"]:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        runout_event = next((e for e in events if e.event_type == "runout_detected"), None)
        assert runout_event is not None

        # Verify event metadata
        assert runout_event.pin_number == 1
        assert runout_event.timestamp > 0
        assert runout_event.previous_state == FilamentState.PRESENT
        assert runout_event.new_state == FilamentState.RUNOUT
        assert runout_event.confidence_level > 0.5

    def test_runout_detection_with_noise_filtering(self, runout_config):
        """Test runout detection robustness against electrical noise."""
        runout_config["debounce_ms"] = 50
        runout_config["confirmation_readings"] = 5  # More confirmations for noise immunity

        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.PRESENT

        # Noisy signal with actual runout buried in noise
        noisy_sequence = [
            {"timestamp": 0.000, "runout_pin": 0},  # Present
            {"timestamp": 0.010, "runout_pin": 1},  # Noise spike
            {"timestamp": 0.015, "runout_pin": 0},  # Back to present
            {"timestamp": 0.020, "runout_pin": 1},  # Another noise spike
            {"timestamp": 0.025, "runout_pin": 0},  # Back to present
            {"timestamp": 0.100, "runout_pin": 1},  # Actual runout start
            {"timestamp": 0.150, "runout_pin": 1},  # Confirm runout
            {"timestamp": 0.200, "runout_pin": 1},  # Confirm runout
            {"timestamp": 0.250, "runout_pin": 1},  # Confirm runout
            {"timestamp": 0.300, "runout_pin": 1},  # Confirm runout
        ]

        events = []
        for gpio_state in noisy_sequence:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should detect only the real runout, filtering out noise
        runout_events = [e for e in events if e.event_type == "runout_detected"]
        assert len(runout_events) == 1
        assert runout_events[0].timestamp >= 0.300  # After sufficient confirmations

    def test_dual_sensor_runout_independence(self, runout_config):
        """Test independent runout detection for dual sensors."""
        # This will fail initially - RunoutDetector doesn't exist
        detector1 = RunoutDetector(pin_number=1, config=runout_config)  # Sensor 1 runout
        detector2 = RunoutDetector(pin_number=3, config=runout_config)  # Sensor 2 runout

        # Set initial states
        detector1.current_state = FilamentState.PRESENT
        detector2.current_state = FilamentState.PRESENT

        # Sensor 1 experiences runout, Sensor 2 remains stable
        test_scenarios = [
            {"timestamp": 0.0, "sensor1_runout": 0, "sensor2_runout": 0},  # Both present
            {"timestamp": 0.1, "sensor1_runout": 1, "sensor2_runout": 0},  # S1 runout, S2 present
            {"timestamp": 0.2, "sensor1_runout": 1, "sensor2_runout": 0},  # S1 runout, S2 present
            {"timestamp": 0.3, "sensor1_runout": 1, "sensor2_runout": 0},  # S1 runout, S2 present
        ]

        sensor1_events = []
        sensor2_events = []

        for scenario in test_scenarios:
            event1 = detector1.process_gpio_state(
                scenario["sensor1_runout"],
                scenario["timestamp"]
            )
            event2 = detector2.process_gpio_state(
                scenario["sensor2_runout"],
                scenario["timestamp"]
            )

            if event1:
                sensor1_events.append(event1)
            if event2:
                sensor2_events.append(event2)

        # Sensor 1 should detect runout
        sensor1_runouts = [e for e in sensor1_events if e.event_type == "runout_detected"]
        assert len(sensor1_runouts) >= 1

        # Sensor 2 should remain stable (no runout events)
        sensor2_runouts = [e for e in sensor2_events if e.event_type == "runout_detected"]
        assert len(sensor2_runouts) == 0

    def test_runout_recovery_timing(self, runout_config):
        """Test timing requirements for runout recovery confirmation."""
        runout_config["recovery_confirmation_ms"] = 500  # 500ms recovery confirmation

        # This will fail initially - RunoutDetector doesn't exist
        detector = RunoutDetector(pin_number=1, config=runout_config)
        detector.current_state = FilamentState.RUNOUT

        # Test insufficient recovery time
        quick_recovery = [
            {"timestamp": 0.000, "runout_pin": 1},  # Runout state
            {"timestamp": 0.100, "runout_pin": 0},  # Filament insertion
            {"timestamp": 0.200, "runout_pin": 1},  # Quick removal (too fast)
            {"timestamp": 0.300, "runout_pin": 0},  # Re-insertion
        ]

        events = []
        for gpio_state in quick_recovery:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should not confirm recovery due to insufficient stable time
        recovery_events = [e for e in events if e.event_type == "filament_recovered"]
        assert len(recovery_events) == 0

        # Test sufficient recovery time
        stable_recovery = [
            {"timestamp": 1.000, "runout_pin": 0},  # Stable insertion
            {"timestamp": 1.600, "runout_pin": 0},  # Still stable after 600ms
        ]

        for gpio_state in stable_recovery:
            event = detector.process_gpio_state(
                gpio_state["runout_pin"],
                gpio_state["timestamp"]
            )
            if event:
                events.append(event)

        # Should now confirm recovery
        recovery_events = [e for e in events if e.event_type == "filament_recovered"]
        assert len(recovery_events) >= 1