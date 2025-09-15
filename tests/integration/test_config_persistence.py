"""
Integration tests for YAML configuration loading and saving.

These tests validate configuration persistence, validation, migration,
and runtime configuration updates for the filament sensor system.
"""

import pytest
import yaml
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

# These imports will fail initially - that's expected for TDD
try:
    from src.lib.config.config_manager import ConfigManager
    from src.lib.config.config_validator import ConfigValidator
    from src.models.configuration import (
        SensorConfiguration,
        SystemConfiguration,
        ConfigurationError
    )
    from src.lib.config.migration import ConfigMigrator
except ImportError:
    # Expected failure - modules don't exist yet
    ConfigManager = None
    ConfigValidator = None
    SensorConfiguration = None
    SystemConfiguration = None
    ConfigurationError = None
    ConfigMigrator = None


@pytest.mark.integration
class TestConfigPersistence:
    """Test YAML configuration persistence and management."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config testing."""
        temp_dir = tempfile.mkdtemp(prefix="filament_sensor_config_")
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def default_config(self):
        """Default configuration for testing."""
        return {
            "version": "1.0",
            "system": {
                "polling_interval_ms": 100,
                "max_history_entries": 1000,
                "log_level": "INFO",
                "api_enabled": True,
                "api_port": 5002
            },
            "hardware": {
                "device_vid": "0x04D8",
                "device_pid": "0x00DD",
                "connection_timeout_ms": 5000,
                "gpio_pullup_enabled": True
            },
            "sensors": {
                "sensor1": {
                    "name": "Extruder 1",
                    "enabled": True,
                    "movement_pin": 0,
                    "runout_pin": 1,
                    "mm_per_pulse": 2.88,
                    "debounce_ms": 50,
                    "runout_debounce_ms": 100,
                    "active_state": "low"
                },
                "sensor2": {
                    "name": "Extruder 2",
                    "enabled": True,
                    "movement_pin": 2,
                    "runout_pin": 3,
                    "mm_per_pulse": 2.88,
                    "debounce_ms": 50,
                    "runout_debounce_ms": 100,
                    "active_state": "low"
                }
            },
            "display": {
                "terminal_ui_enabled": True,
                "update_interval_ms": 100,
                "max_log_lines": 100,
                "theme": "dark"
            },
            "alerts": {
                "runout_notifications": True,
                "movement_timeout_seconds": 300,
                "low_filament_threshold_mm": 10.0
            }
        }

    @pytest.fixture
    def invalid_config(self):
        """Invalid configuration for testing validation."""
        return {
            "version": "1.0",
            "sensors": {
                "sensor1": {
                    "movement_pin": 5,  # Invalid pin (only 0-3 available)
                    "runout_pin": 1,
                    "mm_per_pulse": -1.0,  # Invalid negative value
                    "debounce_ms": "invalid"  # Invalid type
                }
            }
        }

    def test_config_manager_initialization(self, temp_config_dir, default_config):
        """Test ConfigManager initialization and default config creation."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Should create default config if none exists
        assert manager.config_file.exists() is False

        # Load or create config
        config = manager.load_config()

        # Should use defaults when no file exists
        assert isinstance(config, SystemConfiguration)
        assert config.system.polling_interval_ms == 100  # Default value

    def test_yaml_config_loading(self, temp_config_dir, default_config):
        """Test loading configuration from YAML file."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # Write test config to file
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)
        config = manager.load_config()

        # Verify config was loaded correctly
        assert config.version == "1.0"
        assert config.system.polling_interval_ms == 100
        assert config.sensors.sensor1.movement_pin == 0
        assert config.sensors.sensor2.runout_pin == 3

    def test_yaml_config_saving(self, temp_config_dir, default_config):
        """Test saving configuration to YAML file."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Create configuration object
        config = SystemConfiguration(**default_config)

        # Save config
        manager.save_config(config)

        # Verify file was created and contains correct data
        assert config_file.exists()

        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["version"] == "1.0"
        assert saved_data["system"]["polling_interval_ms"] == 100
        assert saved_data["sensors"]["sensor1"]["movement_pin"] == 0

    def test_config_validation(self, temp_config_dir, invalid_config):
        """Test configuration validation and error handling."""
        config_file = Path(temp_config_dir) / "invalid_config.yaml"

        # Write invalid config to file
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Should raise validation error
        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        # Verify error details
        error = exc_info.value
        assert "Invalid GPIO pin" in str(error)
        assert "movement_pin" in str(error)

    def test_config_validator_schema_validation(self, default_config):
        """Test configuration schema validation."""
        # This will fail initially - ConfigValidator doesn't exist
        validator = ConfigValidator()

        # Valid configuration should pass
        validation_result = validator.validate(default_config)
        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0

        # Invalid configuration should fail
        invalid_config = default_config.copy()
        invalid_config["sensors"]["sensor1"]["movement_pin"] = "invalid"

        validation_result = validator.validate(invalid_config)
        assert validation_result.is_valid is False
        assert len(validation_result.errors) > 0

    def test_runtime_config_updates(self, temp_config_dir, default_config):
        """Test runtime configuration updates and persistence."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Load initial config
        config = SystemConfiguration(**default_config)
        manager.save_config(config)

        # Update configuration at runtime
        new_values = {
            "system.polling_interval_ms": 50,  # Change from 100 to 50
            "sensors.sensor1.mm_per_pulse": 1.44,  # Change pulse value
            "display.theme": "light"  # Change theme
        }

        updated_config = manager.update_config(new_values)

        # Verify updates were applied
        assert updated_config.system.polling_interval_ms == 50
        assert updated_config.sensors.sensor1.mm_per_pulse == 1.44
        assert updated_config.display.theme == "light"

        # Verify changes were persisted
        reloaded_config = manager.load_config()
        assert reloaded_config.system.polling_interval_ms == 50

    def test_config_migration(self, temp_config_dir):
        """Test configuration migration between versions."""
        config_file = Path(temp_config_dir) / "old_config.yaml"

        # Create old version config
        old_config = {
            "version": "0.9",  # Old version
            "polling_ms": 100,  # Old structure
            "sensor1_movement_pin": 0,  # Old naming
            "sensor1_runout_pin": 1,
            "sensor2_movement_pin": 2,
            "sensor2_runout_pin": 3
        }

        with open(config_file, 'w') as f:
            yaml.dump(old_config, f)

        # This will fail initially - ConfigMigrator doesn't exist
        migrator = ConfigMigrator()

        # Detect and perform migration
        needs_migration = migrator.needs_migration(old_config)
        assert needs_migration is True

        migrated_config = migrator.migrate_config(old_config, "1.0")

        # Verify migration results
        assert migrated_config["version"] == "1.0"
        assert migrated_config["system"]["polling_interval_ms"] == 100
        assert migrated_config["sensors"]["sensor1"]["movement_pin"] == 0

    def test_config_backup_and_restore(self, temp_config_dir, default_config):
        """Test configuration backup and restore functionality."""
        config_file = Path(temp_config_dir) / "config.yaml"
        backup_file = Path(temp_config_dir) / "config_backup.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Save initial config
        config = SystemConfiguration(**default_config)
        manager.save_config(config)

        # Create backup
        manager.create_backup(backup_file)
        assert backup_file.exists()

        # Modify original config
        config.system.polling_interval_ms = 200
        manager.save_config(config)

        # Restore from backup
        restored_config = manager.restore_from_backup(backup_file)

        # Verify restoration
        assert restored_config.system.polling_interval_ms == 100  # Original value

    def test_concurrent_config_access(self, temp_config_dir, default_config):
        """Test thread-safe configuration access."""
        import threading
        import time

        config_file = Path(temp_config_dir) / "concurrent_config.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)
        config = SystemConfiguration(**default_config)
        manager.save_config(config)

        results = []
        errors = []

        def config_reader(thread_id):
            """Read configuration in separate thread."""
            try:
                for i in range(10):
                    loaded_config = manager.load_config()
                    results.append((thread_id, i, loaded_config.system.polling_interval_ms))
                    time.sleep(0.01)
            except Exception as e:
                errors.append((thread_id, str(e)))

        def config_writer(thread_id):
            """Write configuration in separate thread."""
            try:
                for i in range(5):
                    updated_config = manager.load_config()
                    updated_config.system.polling_interval_ms = 100 + (thread_id * 10) + i
                    manager.save_config(updated_config)
                    time.sleep(0.02)
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start multiple reader and writer threads
        threads = []

        # 3 reader threads
        for i in range(3):
            thread = threading.Thread(target=config_reader, args=(f"reader_{i}",))
            threads.append(thread)
            thread.start()

        # 2 writer threads
        for i in range(2):
            thread = threading.Thread(target=config_writer, args=(f"writer_{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent access errors: {errors}"

        # Verify operations completed
        assert len(results) > 0

    def test_config_change_notifications(self, temp_config_dir, default_config):
        """Test configuration change notification system."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Set up change notifications
        change_events = []

        def on_config_changed(old_config, new_config, changed_fields):
            """Handle configuration change events."""
            change_events.append({
                "old_value": old_config.system.polling_interval_ms,
                "new_value": new_config.system.polling_interval_ms,
                "changed_fields": changed_fields
            })

        manager.register_change_handler(on_config_changed)

        # Load and modify config
        config = SystemConfiguration(**default_config)
        manager.save_config(config)

        # Make changes
        config.system.polling_interval_ms = 150
        manager.save_config(config)

        # Verify change notification was triggered
        assert len(change_events) == 1
        assert change_events[0]["old_value"] == 100
        assert change_events[0]["new_value"] == 150

    def test_config_environment_overrides(self, temp_config_dir, default_config):
        """Test configuration overrides from environment variables."""
        config_file = Path(temp_config_dir) / "config.yaml"

        # Set environment variables
        env_overrides = {
            "FILAMENT_SENSOR_POLLING_INTERVAL_MS": "75",
            "FILAMENT_SENSOR_API_PORT": "5003",
            "FILAMENT_SENSOR_SENSOR1_MM_PER_PULSE": "1.44"
        }

        with patch.dict(os.environ, env_overrides):
            # This will fail initially - ConfigManager doesn't exist
            manager = ConfigManager(config_file, enable_env_overrides=True)

            config = SystemConfiguration(**default_config)
            manager.save_config(config)

            # Load config with environment overrides
            loaded_config = manager.load_config()

            # Verify environment overrides were applied
            assert loaded_config.system.polling_interval_ms == 75
            assert loaded_config.system.api_port == 5003
            assert loaded_config.sensors.sensor1.mm_per_pulse == 1.44

    def test_config_schema_evolution(self, temp_config_dir):
        """Test handling of configuration schema evolution."""
        config_file = Path(temp_config_dir) / "evolving_config.yaml"

        # Version 1.0 schema
        config_v1 = {
            "version": "1.0",
            "system": {"polling_interval_ms": 100},
            "sensors": {"sensor1": {"movement_pin": 0}}
        }

        # Version 1.1 schema (adds new fields)
        config_v1_1 = {
            "version": "1.1",
            "system": {
                "polling_interval_ms": 100,
                "max_cpu_usage_percent": 50  # New field
            },
            "sensors": {
                "sensor1": {
                    "movement_pin": 0,
                    "calibration_factor": 1.0  # New field
                }
            }
        }

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Test forward compatibility (new config with old code)
        with open(config_file, 'w') as f:
            yaml.dump(config_v1_1, f)

        # Should gracefully handle unknown fields
        config = manager.load_config()
        assert config.system.polling_interval_ms == 100

        # Test backward compatibility (old config with new code)
        with open(config_file, 'w') as f:
            yaml.dump(config_v1, f)

        # Should fill in default values for missing fields
        config = manager.load_config()
        assert hasattr(config.system, 'polling_interval_ms')

    def test_config_validation_detailed_errors(self, temp_config_dir):
        """Test detailed configuration validation error reporting."""
        config_file = Path(temp_config_dir) / "detailed_validation.yaml"

        # Configuration with multiple errors
        multi_error_config = {
            "version": "1.0",
            "system": {
                "polling_interval_ms": -50,  # Invalid: negative
                "api_port": 70000  # Invalid: port out of range
            },
            "sensors": {
                "sensor1": {
                    "movement_pin": 10,  # Invalid: pin out of range
                    "mm_per_pulse": "invalid",  # Invalid: wrong type
                    "debounce_ms": 0  # Invalid: zero debounce
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(multi_error_config, f)

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        error = exc_info.value

        # Verify detailed error reporting
        error_messages = str(error).lower()
        assert "polling_interval_ms" in error_messages
        assert "api_port" in error_messages
        assert "movement_pin" in error_messages
        assert "mm_per_pulse" in error_messages
        assert "debounce_ms" in error_messages

    def test_config_partial_updates(self, temp_config_dir, default_config):
        """Test partial configuration updates without full reload."""
        config_file = Path(temp_config_dir) / "partial_updates.yaml"

        # This will fail initially - ConfigManager doesn't exist
        manager = ConfigManager(config_file)

        # Save initial config
        config = SystemConfiguration(**default_config)
        manager.save_config(config)

        # Perform partial update
        partial_updates = {
            "sensors.sensor1.enabled": False,
            "display.theme": "light",
            "system.polling_interval_ms": 200
        }

        updated_config = manager.apply_partial_update(partial_updates)

        # Verify only specified fields were changed
        assert updated_config.sensors.sensor1.enabled is False
        assert updated_config.display.theme == "light"
        assert updated_config.system.polling_interval_ms == 200

        # Verify other fields remained unchanged
        assert updated_config.sensors.sensor1.movement_pin == 0  # Original value
        assert updated_config.sensors.sensor2.enabled is True   # Original value