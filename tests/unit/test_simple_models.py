"""Simple unit tests for models that work with the actual model structure."""

import pytest
from src.models.sensor_configuration import (
    SensorConfiguration,
    GPIOMapping,
    CalibrationSettings,
    PollingSettings
)


class TestSensorConfigurationBasic:
    """Basic tests for SensorConfiguration model."""

    def test_default_configuration(self):
        """Test creating configuration with defaults."""
        config = SensorConfiguration()

        # Test nested structure
        assert config.polling.polling_interval_ms == 100
        assert config.calibration.mm_per_pulse == 2.88
        assert config.api_port == 5002
        assert config.enable_debug_logging is False

        # Test GPIO mappings
        assert config.sensor1_gpio.movement_pin == 0
        assert config.sensor1_gpio.runout_pin == 1
        assert config.sensor2_gpio.movement_pin == 2
        assert config.sensor2_gpio.runout_pin == 3

    def test_custom_configuration(self):
        """Test creating configuration with custom values."""
        config = SensorConfiguration(
            polling=PollingSettings(polling_interval_ms=50),
            calibration=CalibrationSettings(mm_per_pulse=3.0),
            api_port=8080,
            enable_debug_logging=True
        )

        assert config.polling.polling_interval_ms == 50
        assert config.calibration.mm_per_pulse == 3.0
        assert config.api_port == 8080
        assert config.enable_debug_logging is True

    def test_gpio_validation(self):
        """Test GPIO pin validation."""
        # Valid configuration
        config = SensorConfiguration()
        assert len(config.gpio_pin_map) == 4

        # Invalid - same pins for different functions
        with pytest.raises(ValueError):
            SensorConfiguration(
                sensor1_gpio=GPIOMapping(movement_pin=0, runout_pin=1),
                sensor2_gpio=GPIOMapping(movement_pin=0, runout_pin=2)  # Pin 0 reused
            )

    def test_polling_settings(self):
        """Test polling settings validation."""
        # Valid polling interval
        settings = PollingSettings(polling_interval_ms=200)
        assert settings.polling_interval_ms == 200
        assert settings.polling_frequency_hz == 5.0  # 1000/200

        # Too low polling interval
        with pytest.raises(ValueError):
            PollingSettings(polling_interval_ms=5)

        # Too high polling interval
        with pytest.raises(ValueError):
            PollingSettings(polling_interval_ms=2000)

    def test_calibration_settings(self):
        """Test calibration settings validation."""
        # Valid calibration
        settings = CalibrationSettings(
            mm_per_pulse=2.5,
            debounce_ms=20,
            runout_threshold_ms=1000
        )
        assert settings.mm_per_pulse == 2.5
        assert settings.debounce_ms == 20
        assert settings.runout_threshold_ms == 1000

        # Invalid mm_per_pulse
        with pytest.raises(ValueError):
            CalibrationSettings(mm_per_pulse=-1.0)

        # Invalid debounce
        with pytest.raises(ValueError):
            CalibrationSettings(debounce_ms=0)