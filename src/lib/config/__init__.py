"""Configuration management library with YAML support and hot-reload.

This library provides comprehensive configuration management for the filament
sensor monitoring system, including:

- YAML file loading and saving
- Configuration validation and schema checking
- Hot-reload capability with file watching
- Environment variable overrides
- Configuration merging and defaults

Usage:
    from src.lib.config import ConfigManager

    # Basic usage
    config_manager = ConfigManager("config.yaml")
    config = config_manager.load_config()

    # With validation
    config_manager = ConfigManager("config.yaml", validate=True)
    config = config_manager.load_config()

    # With hot-reload
    config_manager = ConfigManager("config.yaml", hot_reload=True)
    config_manager.on_config_changed = my_callback
    config = config_manager.load_config()
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime
from threading import Thread, Event
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import yaml
from pydantic import ValidationError

from ...models.sensor_configuration import SensorConfiguration
from .validation import ConfigValidator, ValidationResult, generate_example_config


class ConfigChangeHandler(FileSystemEventHandler):
    """File system event handler for configuration hot-reload."""

    def __init__(self, config_manager: 'ConfigManager'):
        super().__init__()
        self.config_manager = config_manager

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        if Path(event.src_path) == self.config_manager.config_path:
            self.config_manager._trigger_reload()


class ConfigManager:
    """Comprehensive configuration manager with YAML support and validation."""

    def __init__(
        self,
        config_path: Union[str, Path],
        validate: bool = True,
        strict_validation: bool = False,
        hot_reload: bool = False,
        create_if_missing: bool = False
    ):
        self.config_path = Path(config_path)
        self.validate = validate
        self.strict_validation = strict_validation
        self.hot_reload = hot_reload
        self.create_if_missing = create_if_missing

        # State
        self._current_config: Optional[SensorConfiguration] = None
        self._last_loaded: Optional[datetime] = None
        self._last_validation: Optional[ValidationResult] = None

        # Hot-reload components
        self._observer: Optional[Observer] = None
        self._reload_event = Event()
        self._reload_thread: Optional[Thread] = None
        self._shutdown_event = Event()

        # Callbacks
        self.on_config_changed: Optional[Callable[[SensorConfiguration], None]] = None
        self.on_config_error: Optional[Callable[[Exception], None]] = None
        self.on_validation_warning: Optional[Callable[[ValidationResult], None]] = None

        # Environment variable prefix for overrides
        self.env_prefix = "FILAMENT_SENSOR_"

        # Initialize
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the configuration manager."""
        # Create config file if requested and missing
        if self.create_if_missing and not self.config_path.exists():
            self._create_default_config()

        # Start hot-reload if enabled
        if self.hot_reload:
            self._start_hot_reload()

    def load_config(self) -> SensorConfiguration:
        """Load and return the current configuration."""
        try:
            # Load YAML data
            config_data = self._load_yaml_file()

            # Apply environment variable overrides
            config_data = self._apply_env_overrides(config_data)

            # Validate if requested
            if self.validate:
                validation_result = self._validate_config(config_data)
                self._last_validation = validation_result

                if not validation_result.is_valid:
                    raise ConfigurationError(
                        f"Configuration validation failed: {validation_result.errors[0]}"
                    )

                # Handle warnings
                if validation_result.warnings and self.on_validation_warning:
                    self.on_validation_warning(validation_result)

            # Create configuration object
            self._current_config = SensorConfiguration(**config_data)
            self._last_loaded = datetime.now()

            return self._current_config

        except Exception as e:
            if self.on_config_error:
                self.on_config_error(e)
            raise

    def save_config(self, config: SensorConfiguration) -> None:
        """Save configuration to YAML file."""
        try:
            # Convert to dictionary
            config_data = config.export_dict()

            # Write to YAML file
            self._save_yaml_file(config_data)

            # Update current config
            self._current_config = config
            self._last_loaded = datetime.now()

        except Exception as e:
            if self.on_config_error:
                self.on_config_error(e)
            raise

    def reload_config(self) -> SensorConfiguration:
        """Force reload configuration from file."""
        return self.load_config()

    def get_current_config(self) -> Optional[SensorConfiguration]:
        """Get the currently loaded configuration without reloading."""
        return self._current_config

    def is_config_stale(self, max_age_seconds: float = 30.0) -> bool:
        """Check if configuration is stale based on file modification time."""
        if not self._last_loaded:
            return True

        try:
            file_mtime = datetime.fromtimestamp(self.config_path.stat().st_mtime)
            return file_mtime > self._last_loaded
        except OSError:
            return True

    def get_validation_result(self) -> Optional[ValidationResult]:
        """Get the last validation result."""
        return self._last_validation

    def validate_current_config(self) -> ValidationResult:
        """Validate the current configuration."""
        if not self._current_config:
            raise ConfigurationError("No configuration loaded")

        config_data = self._current_config.export_dict()
        return self._validate_config(config_data)

    def export_config_yaml(self, output_path: Optional[Path] = None) -> str:
        """Export current configuration to YAML string or file."""
        if not self._current_config:
            raise ConfigurationError("No configuration loaded")

        config_data = self._current_config.export_dict()
        yaml_content = self._dict_to_yaml(config_data)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)

        return yaml_content

    def merge_config(self, override_data: Dict[str, Any]) -> SensorConfiguration:
        """Merge override data with current configuration."""
        if not self._current_config:
            base_data = generate_example_config()
        else:
            base_data = self._current_config.export_dict()

        # Deep merge the dictionaries
        merged_data = self._deep_merge(base_data, override_data)

        # Create new configuration
        if self.validate:
            validation_result = self._validate_config(merged_data)
            if not validation_result.is_valid:
                raise ConfigurationError(
                    f"Merged configuration validation failed: {validation_result.errors[0]}"
                )

        return SensorConfiguration(**merged_data)

    def _load_yaml_file(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        if not self.config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"YAML parsing error: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading config file: {e}")

    def _save_yaml_file(self, config_data: Dict[str, Any]) -> None:
        """Save configuration data to YAML file."""
        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write YAML with proper formatting
            yaml_content = self._dict_to_yaml(config_data)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)

        except Exception as e:
            raise ConfigurationError(f"Error writing config file: {e}")

    def _dict_to_yaml(self, data: Dict[str, Any]) -> str:
        """Convert dictionary to formatted YAML string."""
        # Add header comment
        header = f"""# Filament Sensor Configuration
# Generated: {datetime.now().isoformat()}
#
# GPIO Pin Mapping (MCP2221A):
#   GP0: Sensor 1 Movement Detection
#   GP1: Sensor 1 Runout Detection
#   GP2: Sensor 2 Movement Detection
#   GP3: Sensor 2 Runout Detection

"""

        # Convert to YAML with nice formatting
        yaml_content = yaml.dump(
            data,
            default_flow_style=False,
            indent=2,
            sort_keys=False,
            allow_unicode=True
        )

        return header + yaml_content

    def _validate_config(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate configuration data."""
        validator = ConfigValidator(strict_mode=self.strict_validation)
        return validator.validate_config(config_data)

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Define mapping of environment variables to config paths
        env_mappings = {
            f"{self.env_prefix}API_PORT": ["api_port"],
            f"{self.env_prefix}DEBUG": ["enable_debug_logging"],
            f"{self.env_prefix}POLLING_INTERVAL": ["polling", "polling_interval_ms"],
            f"{self.env_prefix}MM_PER_PULSE": ["calibration", "mm_per_pulse"],
            f"{self.env_prefix}DEBOUNCE_MS": ["calibration", "debounce_ms"],
        }

        modified_data = config_data.copy()

        for env_var, path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string value to appropriate type
                converted_value = self._convert_env_value(env_value, path)
                self._set_nested_value(modified_data, path, converted_value)

        return modified_data

    def _convert_env_value(self, value: str, path: list) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if path[-1] in ["enable_debug_logging"]:
            return value.lower() in ('true', '1', 'yes', 'on')

        # Integer conversion
        if path[-1] in ["api_port", "polling_interval_ms", "debounce_ms", "runout_threshold_ms"]:
            return int(value)

        # Float conversion
        if path[-1] in ["mm_per_pulse"]:
            return float(value)

        # String (default)
        return value

    def _set_nested_value(self, data: Dict[str, Any], path: list, value: Any) -> None:
        """Set nested dictionary value using path list."""
        current = data
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _create_default_config(self) -> None:
        """Create default configuration file."""
        default_config = generate_example_config()
        self._save_yaml_file(default_config)

    def _start_hot_reload(self) -> None:
        """Start hot-reload file watching."""
        if not self.config_path.exists():
            return

        try:
            self._observer = Observer()
            handler = ConfigChangeHandler(self)

            # Watch the directory containing the config file
            watch_dir = self.config_path.parent
            self._observer.schedule(handler, str(watch_dir), recursive=False)
            self._observer.start()

            # Start reload thread
            self._reload_thread = Thread(target=self._reload_worker, daemon=True)
            self._reload_thread.start()

        except Exception as e:
            if self.on_config_error:
                self.on_config_error(e)

    def _reload_worker(self) -> None:
        """Background worker for handling config reloads."""
        while not self._shutdown_event.is_set():
            if self._reload_event.wait(timeout=1.0):
                self._reload_event.clear()

                try:
                    # Small delay to ensure file write is complete
                    time.sleep(0.1)

                    # Reload configuration
                    new_config = self.load_config()

                    # Notify callback
                    if self.on_config_changed:
                        self.on_config_changed(new_config)

                except Exception as e:
                    if self.on_config_error:
                        self.on_config_error(e)

    def _trigger_reload(self) -> None:
        """Trigger configuration reload."""
        self._reload_event.set()

    def shutdown(self) -> None:
        """Shutdown configuration manager and cleanup resources."""
        self._shutdown_event.set()

        if self._observer:
            self._observer.stop()
            self._observer.join()

        if self._reload_thread:
            self._reload_thread.join(timeout=5.0)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


# Convenience functions
def load_config_from_file(
    config_path: Union[str, Path],
    validate: bool = True
) -> SensorConfiguration:
    """Load configuration from YAML file (convenience function)."""
    manager = ConfigManager(config_path, validate=validate)
    return manager.load_config()


def save_config_to_file(
    config: SensorConfiguration,
    config_path: Union[str, Path]
) -> None:
    """Save configuration to YAML file (convenience function)."""
    manager = ConfigManager(config_path, validate=False)
    manager.save_config(config)


def create_default_config_file(config_path: Union[str, Path]) -> None:
    """Create default configuration file (convenience function)."""
    manager = ConfigManager(config_path, create_if_missing=True, validate=False)
    # Config file is created during initialization