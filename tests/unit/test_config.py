"""Unit tests for configuration management."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.lib.config import (
    load_configuration,
    load_default_configuration,
    export_configuration,
    validate_configuration
)
from src.models import SensorConfiguration


class TestConfigurationLoading:
    """Test configuration loading functionality."""

    def test_load_default_configuration(self):
        """Test loading default configuration."""
        config = load_default_configuration()

        assert isinstance(config, SensorConfiguration)
        assert config.polling_interval_ms == 100
        assert config.mm_per_pulse == 2.88
        assert config.sensor_1_enabled is True
        assert config.sensor_2_enabled is True

    def test_load_configuration_from_file(self):
        """Test loading configuration from a file."""
        config_data = {
            "polling_interval_ms": 50,
            "mm_per_pulse": 3.0,
            "sensor_1_enabled": False,
            "debug_mode": True
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_configuration(temp_path)

            assert config.polling_interval_ms == 50
            assert config.mm_per_pulse == 3.0
            assert config.sensor_1_enabled is False
            assert config.debug_mode is True
        finally:
            Path(temp_path).unlink()

    def test_load_configuration_file_not_found(self):
        """Test loading configuration when file doesn't exist."""
        config = load_configuration("nonexistent.json")

        # Should return default configuration
        assert isinstance(config, SensorConfiguration)
        assert config.polling_interval_ms == 100

    def test_load_configuration_invalid_json(self):
        """Test loading configuration with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            config = load_configuration(temp_path)

            # Should return default configuration on error
            assert isinstance(config, SensorConfiguration)
            assert config.polling_interval_ms == 100
        finally:
            Path(temp_path).unlink()


class TestConfigurationExport:
    """Test configuration export functionality."""

    def test_export_configuration(self):
        """Test exporting configuration to file."""
        config = SensorConfiguration(
            polling_interval_ms=75,
            mm_per_pulse=2.5,
            sensor_2_enabled=False
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            export_configuration(config, temp_path)

            # Read back and verify
            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert data["polling_interval_ms"] == 75
            assert data["mm_per_pulse"] == 2.5
            assert data["sensor_2_enabled"] is False
        finally:
            Path(temp_path).unlink()

    def test_export_configuration_with_defaults(self):
        """Test exporting default configuration."""
        config = SensorConfiguration()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            export_configuration(config, temp_path)

            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert data["polling_interval_ms"] == 100
            assert data["mm_per_pulse"] == 2.88
            assert data["sensor_1_enabled"] is True
            assert data["sensor_2_enabled"] is True
        finally:
            Path(temp_path).unlink()


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_validate_valid_configuration(self):
        """Test validating a valid configuration."""
        config_data = {
            "polling_interval_ms": 100,
            "mm_per_pulse": 2.88,
            "sensor_1_enabled": True,
            "sensor_2_enabled": True
        }

        is_valid, errors = validate_configuration(config_data)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_polling_interval(self):
        """Test validating configuration with invalid polling interval."""
        config_data = {
            "polling_interval_ms": 5,  # Too low
            "mm_per_pulse": 2.88
        }

        is_valid, errors = validate_configuration(config_data)

        assert is_valid is False
        assert len(errors) > 0
        assert "polling_interval_ms" in str(errors[0])

    def test_validate_negative_mm_per_pulse(self):
        """Test validating configuration with negative mm_per_pulse."""
        config_data = {
            "polling_interval_ms": 100,
            "mm_per_pulse": -1.0  # Negative value
        }

        is_valid, errors = validate_configuration(config_data)

        assert is_valid is False
        assert len(errors) > 0
        assert "mm_per_pulse" in str(errors[0])

    def test_validate_missing_required_fields(self):
        """Test validating configuration with missing fields."""
        config_data = {}  # Empty configuration

        # Should use defaults and be valid
        is_valid, errors = validate_configuration(config_data)

        assert is_valid is True  # Defaults should be valid

    def test_validate_extra_fields(self):
        """Test validating configuration with extra fields."""
        config_data = {
            "polling_interval_ms": 100,
            "mm_per_pulse": 2.88,
            "unknown_field": "value"  # Extra field
        }

        is_valid, errors = validate_configuration(config_data)

        # Extra fields should be ignored but config still valid
        assert is_valid is True