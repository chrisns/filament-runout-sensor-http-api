"""
Integration tests for dual sensor simultaneous reading.

These tests validate the ability to monitor two filament sensors
simultaneously with accurate state tracking and timing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

# These imports will fail initially - that's expected for TDD
try:
    from src.services.sensor_monitor import SensorMonitor
    from src.services.mcp2221_manager import MCP2221Manager
    from src.models.sensor_reading import SensorReading, DualSensorState
    from src.lib.mcp2221_sensor.dual_monitor import DualSensorMonitor
except ImportError:
    # Expected failure - modules don't exist yet
    SensorMonitor = None
    MCP2221Manager = None
    SensorReading = None
    DualSensorState = None
    DualSensorMonitor = None


@pytest.mark.integration
class TestDualSensors:
    """Test simultaneous monitoring of two filament sensors."""

    @pytest.fixture
    def sensor_config(self):
        """Configuration for dual sensor setup."""
        return {
            "sensor1": {
                "name": "Extruder 1",
                "movement_pin": 0,
                "runout_pin": 1,
                "mm_per_pulse": 2.88,
                "debounce_ms": 50,
                "enabled": True
            },
            "sensor2": {
                "name": "Extruder 2",
                "movement_pin": 2,
                "runout_pin": 3,
                "mm_per_pulse": 2.88,
                "debounce_ms": 50,
                "enabled": True
            },
            "polling_interval_ms": 100,
            "max_history_entries": 1000
        }

    @pytest.fixture
    def mock_hardware(self):
        """Mock hardware interface for testing."""
        hardware = MagicMock()
        hardware.is_connected.return_value = True
        hardware.read_gpio_states.return_value = {
            "GP0": 1,  # Sensor 1 movement
            "GP1": 1,  # Sensor 1 filament present
            "GP2": 1,  # Sensor 2 movement
            "GP3": 1   # Sensor 2 filament present
        }
        return hardware

    def test_dual_sensor_initialization(self, sensor_config, mock_hardware):
        """Test initialization of dual sensor monitoring system."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            assert monitor.sensor1_config == sensor_config["sensor1"]
            assert monitor.sensor2_config == sensor_config["sensor2"]
            assert monitor.polling_interval == 0.1  # 100ms
            assert monitor.is_monitoring is False

    def test_simultaneous_sensor_reading(self, sensor_config, mock_hardware):
        """Test reading both sensors simultaneously."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Read both sensors at once
            dual_state = monitor.read_sensors()

            # Verify both sensors were read
            assert isinstance(dual_state, DualSensorState)
            assert dual_state.sensor1 is not None
            assert dual_state.sensor2 is not None
            assert dual_state.timestamp > 0

    def test_sensor_state_synchronization(self, sensor_config, mock_hardware):
        """Test that sensor readings are properly synchronized."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Take multiple readings rapidly
            readings = []
            for _ in range(10):
                state = monitor.read_sensors()
                readings.append(state)
                time.sleep(0.01)  # 10ms between readings

            # Verify timestamps are sequential and close together
            for i in range(1, len(readings)):
                time_diff = readings[i].timestamp - readings[i-1].timestamp
                assert 0.005 < time_diff < 0.02  # Between 5ms and 20ms

    def test_independent_sensor_configuration(self, sensor_config, mock_hardware):
        """Test that sensors can be configured independently."""
        # Different configurations for each sensor
        sensor_config["sensor1"]["mm_per_pulse"] = 2.88
        sensor_config["sensor2"]["mm_per_pulse"] = 1.44  # Different value
        sensor_config["sensor1"]["debounce_ms"] = 50
        sensor_config["sensor2"]["debounce_ms"] = 100  # Different debounce

        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Verify independent configuration
            assert monitor.sensor1_config["mm_per_pulse"] == 2.88
            assert monitor.sensor2_config["mm_per_pulse"] == 1.44
            assert monitor.sensor1_config["debounce_ms"] == 50
            assert monitor.sensor2_config["debounce_ms"] == 100

    def test_concurrent_sensor_monitoring(self, sensor_config, mock_hardware):
        """Test concurrent monitoring of both sensors."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            readings_collected = []
            monitoring_duration = 0.5  # 500ms

            def collect_readings():
                """Collect sensor readings for testing."""
                start_time = time.time()
                while time.time() - start_time < monitoring_duration:
                    state = monitor.read_sensors()
                    readings_collected.append(state)
                    time.sleep(0.05)  # 50ms between readings

            # Start monitoring in background thread
            monitor_thread = threading.Thread(target=collect_readings)
            monitor_thread.start()
            monitor_thread.join()

            # Verify we collected multiple readings
            assert len(readings_collected) >= 8  # Should get ~10 readings in 500ms

            # Verify all readings have both sensors
            for reading in readings_collected:
                assert reading.sensor1 is not None
                assert reading.sensor2 is not None

    def test_sensor_failure_isolation(self, sensor_config, mock_hardware):
        """Test that failure of one sensor doesn't affect the other."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            # Simulate sensor 1 pin failure (returns None for GP0 and GP1)
            mock_hardware.read_gpio_states.return_value = {
                "GP0": None,  # Sensor 1 movement - failed
                "GP1": None,  # Sensor 1 runout - failed
                "GP2": 1,     # Sensor 2 movement - working
                "GP3": 0      # Sensor 2 runout - working
            }
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            state = monitor.read_sensors()

            # Sensor 1 should be marked as failed/unavailable
            assert state.sensor1.is_error is True
            # Sensor 2 should continue working normally
            assert state.sensor2.is_error is False
            assert state.sensor2.movement_detected is True
            assert state.sensor2.filament_present is False

    def test_asymmetric_sensor_activity(self, sensor_config, mock_hardware):
        """Test sensors with different activity patterns."""
        activity_pattern = [
            # (GP0, GP1, GP2, GP3) - Movement and runout for each sensor
            (1, 1, 0, 1),  # Sensor 1 active, Sensor 2 idle
            (0, 1, 1, 1),  # Sensor 1 idle, Sensor 2 active
            (1, 1, 1, 1),  # Both sensors active
            (0, 1, 0, 1),  # Both sensors idle (filament present)
            (0, 0, 0, 0),  # Both sensors - no filament
        ]

        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            results = []
            for gp0, gp1, gp2, gp3 in activity_pattern:
                mock_hardware.read_gpio_states.return_value = {
                    "GP0": gp0, "GP1": gp1, "GP2": gp2, "GP3": gp3
                }

                state = monitor.read_sensors()
                results.append((
                    state.sensor1.movement_detected,
                    state.sensor1.filament_present,
                    state.sensor2.movement_detected,
                    state.sensor2.filament_present
                ))

            # Verify activity patterns were captured correctly
            expected = [
                (True, True, False, True),   # S1 active, S2 idle
                (False, True, True, True),   # S1 idle, S2 active
                (True, True, True, True),    # Both active
                (False, True, False, True),  # Both idle
                (False, False, False, False) # No filament
            ]
            assert results == expected

    def test_sensor_timing_accuracy(self, sensor_config, mock_hardware):
        """Test timing accuracy of dual sensor readings."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Measure timing accuracy
            start_time = time.perf_counter()
            readings = []

            for _ in range(20):
                reading_start = time.perf_counter()
                state = monitor.read_sensors()
                reading_end = time.perf_counter()

                readings.append({
                    'state': state,
                    'duration': reading_end - reading_start,
                    'timestamp': reading_start
                })

            total_time = time.perf_counter() - start_time

            # Verify reading speed (should be < 10ms per reading)
            for reading in readings:
                assert reading['duration'] < 0.01  # Less than 10ms per reading

            # Verify consistent timing between readings
            avg_duration = sum(r['duration'] for r in readings) / len(readings)
            assert avg_duration < 0.005  # Average less than 5ms

    def test_high_frequency_monitoring(self, sensor_config, mock_hardware):
        """Test high-frequency monitoring performance."""
        # Set very fast polling interval
        sensor_config["polling_interval_ms"] = 10  # 10ms = 100Hz

        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Monitor for 1 second at high frequency
            readings = []
            start_time = time.time()

            while time.time() - start_time < 1.0:
                state = monitor.read_sensors()
                readings.append(state)
                time.sleep(0.01)  # 10ms polling interval

            # Should collect ~100 readings in 1 second
            assert len(readings) >= 80  # Allow some tolerance
            assert len(readings) <= 120

            # Verify no readings were dropped or corrupted
            for reading in readings:
                assert reading.sensor1 is not None
                assert reading.sensor2 is not None
                assert reading.timestamp > 0

    def test_memory_usage_during_monitoring(self, sensor_config, mock_hardware):
        """Test memory usage during extended monitoring."""
        import psutil
        import os

        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Measure initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Run monitoring for extended period
            readings = []
            for _ in range(1000):  # 1000 readings
                state = monitor.read_sensors()
                readings.append(state)

            # Measure final memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (< 10MB for 1000 readings)
            assert memory_increase < 10

    def test_sensor_data_consistency(self, sensor_config, mock_hardware):
        """Test data consistency across multiple readings."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            # Set consistent GPIO states
            mock_hardware.read_gpio_states.return_value = {
                "GP0": 1, "GP1": 1, "GP2": 0, "GP3": 1
            }
            mock_manager.return_value = mock_hardware

            # This will fail initially - DualSensorMonitor doesn't exist
            monitor = DualSensorMonitor(sensor_config)

            # Take multiple readings with same hardware state
            readings = []
            for _ in range(10):
                state = monitor.read_sensors()
                readings.append(state)

            # All readings should be consistent (same GPIO state)
            for reading in readings:
                assert reading.sensor1.movement_detected is True
                assert reading.sensor1.filament_present is True
                assert reading.sensor2.movement_detected is False
                assert reading.sensor2.filament_present is True