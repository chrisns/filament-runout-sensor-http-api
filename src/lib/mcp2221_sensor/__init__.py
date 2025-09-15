"""
MCP2221A Sensor Library for USB-GPIO Hardware Interface.

This library provides hardware abstraction for the MCP2221A USB-to-GPIO adapter,
specifically designed for filament sensor monitoring with dual BIGTREETECH sensors.

Classes:
    MCP2221Manager: Main USB connection and GPIO management
    PulseDetector: Edge detection and debouncing logic
    ConnectionManager: Connection retry with exponential backoff

Features:
    - Dual sensor support (2 sensors with 2 pins each)
    - GPIO pins 0-3 configured as inputs with pull-ups
    - 2ms debouncing for pulse detection
    - USB disconnection recovery
    - Thread-safe GPIO operations
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

try:
    from EasyMCP2221 import Device
except ImportError:
    Device = None
    logging.warning("EasyMCP2221 not installed - hardware functionality disabled")

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GPIOState:
    """Current state of all GPIO pins."""
    GP0: bool  # Sensor 1 Movement
    GP1: bool  # Sensor 1 Runout
    GP2: bool  # Sensor 2 Movement
    GP3: bool  # Sensor 2 Runout
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "GP0": self.GP0,
            "GP1": self.GP1,
            "GP2": self.GP2,
            "GP3": self.GP3,
            "timestamp": self.timestamp.isoformat()
        }


class MCP2221Manager:
    """
    MCP2221A USB-GPIO manager for filament sensor monitoring.

    Handles USB device connection, GPIO configuration, and state reading
    with thread-safe operations and connection recovery.
    """

    # MCP2221A USB identifiers
    VID = 0x04D8
    PID = 0x00DD

    def __init__(self):
        """Initialize MCP2221 manager."""
        self._device: Optional[Device] = None
        self._lock = threading.RLock()
        self._is_configured = False
        self._gpio_config: Dict[str, Any] = {}
        self._interrupt_config: Dict[str, str] = {}

        logger.info("MCP2221Manager initialized")

    def detect_device(self) -> bool:
        """
        Detect and connect to MCP2221A device.

        Returns:
            bool: True if device detected and connected successfully
        """
        with self._lock:
            try:
                if Device is None:
                    logger.error("EasyMCP2221 library not available")
                    return False

                # Try to connect to device
                self._device = Device()

                # Verify it's the correct device
                if (hasattr(self._device, 'VID') and
                    hasattr(self._device, 'PID') and
                    self._device.VID == self.VID and
                    self._device.PID == self.PID):

                    logger.info(f"MCP2221A detected: VID={self._device.VID:04X}, PID={self._device.PID:04X}")
                    return True
                else:
                    logger.warning("Connected device is not MCP2221A")
                    self._device = None
                    return False

            except Exception as e:
                logger.error(f"Failed to detect MCP2221A device: {e}")
                self._device = None
                return False

    def is_connected(self) -> bool:
        """
        Check if device is currently connected.

        Returns:
            bool: True if device is connected and responsive
        """
        with self._lock:
            if self._device is None:
                return False

            try:
                # Test device responsiveness
                _ = self._device.VID
                return True
            except Exception as e:
                logger.debug(f"Device connection check failed: {e}")
                return False

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to device.

        Returns:
            bool: True if reconnection successful
        """
        logger.info("Attempting device reconnection...")

        # Close existing connection
        self.disconnect()

        # Try to detect and reconnect
        if self.detect_device():
            # Reconfigure GPIO if we had previous configuration
            if self._gpio_config:
                try:
                    self.configure_gpio(self._gpio_config)
                    logger.info("Device reconnected and reconfigured successfully")
                    return True
                except Exception as e:
                    logger.error(f"Failed to reconfigure GPIO after reconnection: {e}")
                    return False
            else:
                logger.info("Device reconnected successfully")
                return True

        return False

    def disconnect(self) -> None:
        """Disconnect from device."""
        with self._lock:
            if self._device is not None:
                try:
                    # MCP2221 doesn't need explicit disconnect
                    pass
                except Exception as e:
                    logger.debug(f"Error during disconnect: {e}")
                finally:
                    self._device = None
                    self._is_configured = False
                    logger.info("Device disconnected")

    def configure_gpio(self, config: Dict[str, Any]) -> None:
        """
        Configure GPIO pins for sensor monitoring.

        Args:
            config: Configuration dictionary with sensor pin mappings

        Raises:
            ConnectionError: If device not connected
            ValueError: If invalid pin configuration
        """
        with self._lock:
            if not self.is_connected():
                raise ConnectionError("MCP2221A device not connected")

            try:
                # Validate pin numbers
                self._validate_gpio_config(config)

                # Configure all pins as GPIO inputs with pull-ups
                self._device.set_pin_function(gp0="GPIO_IN")
                self._device.set_pin_function(gp1="GPIO_IN")
                self._device.set_pin_function(gp2="GPIO_IN")
                self._device.set_pin_function(gp3="GPIO_IN")

                # Enable pull-up resistors for all sensor pins
                self._device.GPIO_0_direction = "input"
                self._device.GPIO_1_direction = "input"
                self._device.GPIO_2_direction = "input"
                self._device.GPIO_3_direction = "input"

                # Note: EasyMCP2221 may not expose pullup properties directly
                # This is device/library dependent
                try:
                    self._device.GPIO_0_pullup = True
                    self._device.GPIO_1_pullup = True
                    self._device.GPIO_2_pullup = True
                    self._device.GPIO_3_pullup = True
                except AttributeError:
                    logger.warning("Pull-up configuration not available in this EasyMCP2221 version")

                self._gpio_config = config.copy()
                self._is_configured = True

                logger.info("GPIO pins configured successfully")
                logger.debug(f"GPIO configuration: {config}")

            except Exception as e:
                logger.error(f"Failed to configure GPIO: {e}")
                raise

    def _validate_gpio_config(self, config: Dict[str, Any]) -> None:
        """
        Validate GPIO pin configuration.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If configuration is invalid
        """
        valid_pins = {0, 1, 2, 3}
        used_pins = set()

        for sensor_id, sensor_config in config.items():
            if sensor_id.startswith('sensor'):
                movement_pin = sensor_config.get('movement_pin')
                runout_pin = sensor_config.get('runout_pin')

                # Check pin numbers are valid
                if movement_pin not in valid_pins:
                    raise ValueError(f"Invalid GPIO pin {movement_pin} for {sensor_id} movement")
                if runout_pin not in valid_pins:
                    raise ValueError(f"Invalid GPIO pin {runout_pin} for {sensor_id} runout")

                # Check for pin conflicts
                if movement_pin in used_pins:
                    raise ValueError(f"GPIO pin {movement_pin} already in use")
                if runout_pin in used_pins:
                    raise ValueError(f"GPIO pin {runout_pin} already in use")

                used_pins.add(movement_pin)
                used_pins.add(runout_pin)

    def read_gpio_states(self) -> Dict[str, int]:
        """
        Read current state of all GPIO pins.

        Returns:
            Dict[str, int]: Current pin states (0 or 1)

        Raises:
            ConnectionError: If device not connected
        """
        with self._lock:
            if not self.is_connected():
                raise ConnectionError("MCP2221A device not connected")

            try:
                return {
                    "GP0": int(self._device.GPIO_0_value),
                    "GP1": int(self._device.GPIO_1_value),
                    "GP2": int(self._device.GPIO_2_value),
                    "GP3": int(self._device.GPIO_3_value)
                }
            except Exception as e:
                logger.error(f"Failed to read GPIO states: {e}")
                raise

    def read_gpio_state_object(self) -> GPIOState:
        """
        Read GPIO states as structured object.

        Returns:
            GPIOState: Current pin states with timestamp
        """
        states = self.read_gpio_states()
        return GPIOState(
            GP0=bool(states["GP0"]),
            GP1=bool(states["GP1"]),
            GP2=bool(states["GP2"]),
            GP3=bool(states["GP3"]),
            timestamp=datetime.now()
        )

    def configure_interrupts(self, interrupt_config: Dict[str, str]) -> None:
        """
        Configure interrupt-style detection for GPIO pins.

        Note: MCP2221A doesn't have true interrupts, this configures
        polling-based edge detection parameters.

        Args:
            interrupt_config: Pin interrupt configuration
        """
        self._interrupt_config = interrupt_config.copy()
        logger.info(f"Interrupt configuration stored: {interrupt_config}")

    @property
    def device_info(self) -> Dict[str, Any]:
        """Get device information."""
        if not self.is_connected():
            return {}

        return {
            "VID": self._device.VID,
            "PID": self._device.PID,
            "connected": True,
            "configured": self._is_configured
        }

    @property
    def interrupt_config(self) -> Dict[str, str]:
        """Get current interrupt configuration."""
        return self._interrupt_config.copy()

    @staticmethod
    def enumerate_devices() -> List[Dict[str, Any]]:
        """
        Enumerate available MCP2221A devices.

        Returns:
            List[Dict]: List of available device information
        """
        try:
            import hid
            devices = hid.enumerate(MCP2221Manager.VID, MCP2221Manager.PID)
            return [
                {
                    'vendor_id': dev['vendor_id'],
                    'product_id': dev['product_id'],
                    'serial_number': dev.get('serial_number', ''),
                    'path': dev.get('path', b'').decode('utf-8', errors='ignore')
                }
                for dev in devices
            ]
        except ImportError:
            logger.warning("hid library not available for device enumeration")
            return []
        except Exception as e:
            logger.error(f"Failed to enumerate devices: {e}")
            return []


# Public API exports
__all__ = [
    'MCP2221Manager',
    'GPIOState'
]