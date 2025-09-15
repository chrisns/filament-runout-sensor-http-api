"""
Integration tests for MCP2221A USB device detection and GPIO configuration.

These tests validate the hardware interface layer and ensure proper device
communication and GPIO pin configuration for filament sensor monitoring.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from typing import Dict, Any

# These imports will fail initially - that's expected for TDD
try:
    from src.services.mcp2221_manager import MCP2221Manager
    from src.models.configuration import SensorConfiguration
    from src.lib.mcp2221_sensor.hardware import HardwareInterface
except ImportError:
    # Expected failure - modules don't exist yet
    MCP2221Manager = None
    SensorConfiguration = None
    HardwareInterface = None


@pytest.mark.integration
class TestMCP2221Connection:
    """Test MCP2221A USB device detection and configuration."""

    @pytest.fixture
    def mock_device(self):
        """Mock MCP2221A device for testing."""
        device = MagicMock()
        device.VID = 0x04D8
        device.PID = 0x00DD
        device.is_connected.return_value = True
        device.GPIO_0_function = 0  # GPIO function
        device.GPIO_1_function = 0
        device.GPIO_2_function = 0
        device.GPIO_3_function = 0
        return device

    @pytest.fixture
    def sensor_config(self):
        """Default sensor configuration for testing."""
        return {
            "sensor1": {
                "movement_pin": 0,
                "runout_pin": 1,
                "mm_per_pulse": 2.88,
                "debounce_ms": 50
            },
            "sensor2": {
                "movement_pin": 2,
                "runout_pin": 3,
                "mm_per_pulse": 2.88,
                "debounce_ms": 50
            },
            "polling_interval_ms": 100
        }

    def test_detect_mcp2221_device(self, mock_device):
        """Test MCP2221A USB device detection."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()

            # Test device detection
            assert manager.detect_device() is True
            assert manager.device_info["VID"] == 0x04D8
            assert manager.device_info["PID"] == 0x00DD
            assert manager.is_connected() is True

    def test_device_connection_failure(self):
        """Test handling when MCP2221A is not connected."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.side_effect = Exception("Device not found")

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()

            # Test connection failure handling
            assert manager.detect_device() is False
            assert manager.is_connected() is False

            with pytest.raises(ConnectionError):
                manager.configure_gpio({})

    def test_gpio_pin_configuration(self, mock_device, sensor_config):
        """Test GPIO pin configuration for sensor inputs."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()

            # Configure GPIO pins for sensors
            manager.configure_gpio(sensor_config)

            # Verify all pins configured as inputs
            assert mock_device.set_pin_function.call_count == 4

            # Check specific pin configurations
            mock_device.set_pin_function.assert_any_call(gp0="GPIO_IN")
            mock_device.set_pin_function.assert_any_call(gp1="GPIO_IN")
            mock_device.set_pin_function.assert_any_call(gp2="GPIO_IN")
            mock_device.set_pin_function.assert_any_call(gp3="GPIO_IN")

    def test_gpio_input_pullup_configuration(self, mock_device, sensor_config):
        """Test GPIO input pullup resistor configuration."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()
            manager.configure_gpio(sensor_config)

            # Test pullup resistor configuration for sensor pins
            mock_device.GPIO_0_direction = "input"
            mock_device.GPIO_1_direction = "input"
            mock_device.GPIO_2_direction = "input"
            mock_device.GPIO_3_direction = "input"

            # Verify pullup resistors enabled for all sensor pins
            assert mock_device.GPIO_0_pullup is True
            assert mock_device.GPIO_1_pullup is True
            assert mock_device.GPIO_2_pullup is True
            assert mock_device.GPIO_3_pullup is True

    def test_read_gpio_states(self, mock_device, sensor_config):
        """Test reading GPIO pin states."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device
            mock_device.GPIO_0_value = 1  # Movement detected
            mock_device.GPIO_1_value = 1  # Filament present
            mock_device.GPIO_2_value = 0  # No movement
            mock_device.GPIO_3_value = 0  # No filament

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()
            manager.configure_gpio(sensor_config)

            # Read all GPIO states
            states = manager.read_gpio_states()

            assert states["GP0"] == 1  # Sensor 1 movement
            assert states["GP1"] == 1  # Sensor 1 runout
            assert states["GP2"] == 0  # Sensor 2 movement
            assert states["GP3"] == 0  # Sensor 2 runout

    def test_device_reset_recovery(self, mock_device):
        """Test device reset and recovery procedures."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()

            # Simulate device disconnection
            mock_device.is_connected.return_value = False

            # Test recovery
            assert manager.is_connected() is False

            # Simulate reconnection
            mock_device.is_connected.return_value = True
            recovery_success = manager.reconnect()

            assert recovery_success is True
            assert manager.is_connected() is True

    def test_gpio_configuration_validation(self, mock_device):
        """Test validation of GPIO pin configuration."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()

            # Test invalid pin configuration
            invalid_config = {
                "sensor1": {
                    "movement_pin": 5,  # Invalid pin (only 0-3 available)
                    "runout_pin": 1
                }
            }

            with pytest.raises(ValueError, match="Invalid GPIO pin"):
                manager.configure_gpio(invalid_config)

    def test_concurrent_gpio_access(self, mock_device, sensor_config):
        """Test thread-safe GPIO access."""
        import threading
        import queue

        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()
            manager.configure_gpio(sensor_config)

            results = queue.Queue()

            def read_gpio_worker():
                """Worker function for concurrent GPIO reads."""
                try:
                    states = manager.read_gpio_states()
                    results.put(("success", states))
                except Exception as e:
                    results.put(("error", str(e)))

            # Start multiple threads reading GPIO
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=read_gpio_worker)
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=1.0)

            # Verify all reads succeeded
            assert results.qsize() == 5
            while not results.empty():
                status, data = results.get()
                assert status == "success"
                assert isinstance(data, dict)

    def test_hardware_interface_initialization(self, sensor_config):
        """Test hardware interface wrapper initialization."""
        with patch('src.services.mcp2221_manager.MCP2221Manager') as mock_manager:
            # This will fail initially - HardwareInterface doesn't exist
            interface = HardwareInterface(sensor_config)

            # Verify manager was initialized
            assert interface.manager is not None
            assert interface.config == sensor_config

            # Test initialization failure handling
            mock_manager.side_effect = Exception("Hardware init failed")

            with pytest.raises(RuntimeError, match="Failed to initialize hardware"):
                HardwareInterface(sensor_config)

    def test_device_enumeration(self):
        """Test enumeration of available MCP2221A devices."""
        with patch('hid.enumerate') as mock_enumerate:
            mock_enumerate.return_value = [
                {
                    'vendor_id': 0x04D8,
                    'product_id': 0x00DD,
                    'serial_number': 'ABC123',
                    'path': b'path1'
                },
                {
                    'vendor_id': 0x04D8,
                    'product_id': 0x00DD,
                    'serial_number': 'DEF456',
                    'path': b'path2'
                }
            ]

            # This will fail initially - MCP2221Manager doesn't exist
            devices = MCP2221Manager.enumerate_devices()

            assert len(devices) == 2
            assert devices[0]['serial_number'] == 'ABC123'
            assert devices[1]['serial_number'] == 'DEF456'

    def test_gpio_interrupt_configuration(self, mock_device, sensor_config):
        """Test GPIO interrupt configuration for edge detection."""
        with patch('EasyMCP2221.Device') as mock_device_class:
            mock_device_class.return_value = mock_device

            # This will fail initially - MCP2221Manager doesn't exist
            manager = MCP2221Manager()
            manager.detect_device()
            manager.configure_gpio(sensor_config)

            # Configure interrupts for movement detection
            manager.configure_interrupts({
                "GP0": "falling_edge",  # Sensor 1 movement
                "GP2": "falling_edge"   # Sensor 2 movement
            })

            # Verify interrupt configuration
            # Note: MCP2221A doesn't have true interrupts,
            # but we can test the polling configuration
            assert manager.interrupt_config["GP0"] == "falling_edge"
            assert manager.interrupt_config["GP2"] == "falling_edge"