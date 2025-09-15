"""Configuration validation utilities for YAML config files.

This module provides comprehensive validation for filament sensor configuration
files, including schema validation, value range checks, and logical consistency
validation.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from pydantic import ValidationError

from ...models.sensor_configuration import (
    SensorConfiguration,
    GPIOMapping,
    CalibrationSettings,
    PollingSettings
)


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors."""

    def __init__(self, message: str, path: str = "", details: Optional[Dict] = None):
        self.message = message
        self.path = path
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.path:
            return f"Config validation error at '{self.path}': {self.message}"
        return f"Config validation error: {self.message}"


class ValidationResult:
    """Result of configuration validation."""

    def __init__(self):
        self.is_valid = True
        self.errors: List[ConfigValidationError] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def add_error(self, error: ConfigValidationError) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, message: str, path: str = "") -> None:
        """Add validation warning."""
        warning_msg = f"Warning at '{path}': {message}" if path else f"Warning: {message}"
        self.warnings.append(warning_msg)

    def add_info(self, message: str) -> None:
        """Add informational message."""
        self.info.append(message)

    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        return {
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.info),
            "errors": [str(error) for error in self.errors],
            "warnings": self.warnings,
            "info": self.info
        }

    def print_results(self, verbose: bool = True) -> None:
        """Print validation results to console."""
        if self.is_valid:
            print("✓ Configuration validation passed")
        else:
            print("✗ Configuration validation failed")

        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings and verbose:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.info and verbose:
            print(f"\nInfo ({len(self.info)}):")
            for info in self.info:
                print(f"  • {info}")


class ConfigValidator:
    """Comprehensive configuration validator."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.result = ValidationResult()

    def validate_config(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate complete configuration dictionary."""
        self.result = ValidationResult()

        try:
            # Step 1: Basic structure validation
            self._validate_structure(config_data)

            # Step 2: Create and validate Pydantic model
            config_obj = self._validate_pydantic_model(config_data)

            if config_obj:
                # Step 3: Advanced logical validation
                self._validate_logical_consistency(config_obj)

                # Step 4: Performance and safety checks
                self._validate_performance_settings(config_obj)

                # Step 5: Hardware-specific validation
                self._validate_hardware_settings(config_obj)

        except Exception as e:
            self.result.add_error(ConfigValidationError(
                f"Unexpected validation error: {str(e)}"
            ))

        return self.result

    def validate_yaml_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate YAML configuration file."""
        self.result = ValidationResult()
        file_path = Path(file_path)

        try:
            # Check file existence and readability
            if not file_path.exists():
                self.result.add_error(ConfigValidationError(
                    f"Configuration file does not exist: {file_path}"
                ))
                return self.result

            if not file_path.is_file():
                self.result.add_error(ConfigValidationError(
                    f"Path is not a file: {file_path}"
                ))
                return self.result

            # Load and parse YAML
            import yaml
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                self.result.add_error(ConfigValidationError(
                    f"YAML parsing error: {str(e)}"
                ))
                return self.result

            # Validate the loaded configuration
            return self.validate_config(config_data)

        except Exception as e:
            self.result.add_error(ConfigValidationError(
                f"File validation error: {str(e)}"
            ))
            return self.result

    def _validate_structure(self, config: Dict[str, Any]) -> None:
        """Validate basic configuration structure."""
        required_sections = [
            "sensor1_gpio",
            "sensor2_gpio",
            "calibration",
            "polling"
        ]

        for section in required_sections:
            if section not in config:
                self.result.add_error(ConfigValidationError(
                    f"Missing required section: {section}",
                    path=section
                ))

        # Check for unknown top-level keys
        known_keys = {
            "sensor1_gpio", "sensor2_gpio", "calibration", "polling",
            "enable_debug_logging", "api_port"
        }
        unknown_keys = set(config.keys()) - known_keys

        if unknown_keys:
            if self.strict_mode:
                for key in unknown_keys:
                    self.result.add_error(ConfigValidationError(
                        f"Unknown configuration key: {key}",
                        path=key
                    ))
            else:
                self.result.add_warning(
                    f"Unknown configuration keys (will be ignored): {', '.join(unknown_keys)}"
                )

    def _validate_pydantic_model(self, config: Dict[str, Any]) -> Optional[SensorConfiguration]:
        """Validate using Pydantic model."""
        try:
            config_obj = SensorConfiguration(**config)
            self.result.add_info("Pydantic model validation passed")
            return config_obj

        except ValidationError as e:
            for error in e.errors():
                field_path = ".".join(str(x) for x in error['loc'])
                self.result.add_error(ConfigValidationError(
                    error['msg'],
                    path=field_path,
                    details={"type": error['type'], "input": error.get('input')}
                ))
            return None

    def _validate_logical_consistency(self, config: SensorConfiguration) -> None:
        """Validate logical consistency of configuration."""
        # Check GPIO pin uniqueness (already handled by Pydantic, but double-check)
        all_pins = [
            config.sensor1_gpio.movement_pin,
            config.sensor1_gpio.runout_pin,
            config.sensor2_gpio.movement_pin,
            config.sensor2_gpio.runout_pin
        ]

        if len(set(all_pins)) != 4:
            self.result.add_error(ConfigValidationError(
                "GPIO pins must all be unique",
                path="gpio_mappings"
            ))

        # Check calibration relationships
        if config.calibration.runout_threshold_ms <= config.calibration.debounce_ms:
            self.result.add_warning(
                "Runout threshold should be significantly larger than debounce time",
                path="calibration"
            )

        # Check polling intervals
        if config.polling.ui_update_interval_ms < config.polling.polling_interval_ms:
            self.result.add_warning(
                "UI update interval should not be faster than sensor polling",
                path="polling"
            )

    def _validate_performance_settings(self, config: SensorConfiguration) -> None:
        """Validate performance-related settings."""
        # Check polling frequency limits
        polling_hz = config.polling.polling_frequency_hz

        if polling_hz > 100:  # 100 Hz = 10ms intervals
            self.result.add_warning(
                f"Very high polling frequency ({polling_hz:.1f} Hz) may impact performance",
                path="polling.polling_interval_ms"
            )

        if polling_hz < 1:  # Less than 1 Hz
            self.result.add_warning(
                f"Very low polling frequency ({polling_hz:.1f} Hz) may miss events",
                path="polling.polling_interval_ms"
            )

        # Check mm_per_pulse reasonableness
        mm_per_pulse = config.calibration.mm_per_pulse
        if mm_per_pulse > 10:
            self.result.add_warning(
                f"Large mm_per_pulse value ({mm_per_pulse}) - verify calibration",
                path="calibration.mm_per_pulse"
            )

        if mm_per_pulse < 0.1:
            self.result.add_warning(
                f"Very small mm_per_pulse value ({mm_per_pulse}) - may be too sensitive",
                path="calibration.mm_per_pulse"
            )

        # Check API port
        if config.api_port < 1024:
            self.result.add_warning(
                f"API port {config.api_port} requires elevated privileges",
                path="api_port"
            )

    def _validate_hardware_settings(self, config: SensorConfiguration) -> None:
        """Validate hardware-specific settings."""
        # Check debounce timing
        debounce_ms = config.calibration.debounce_ms
        if debounce_ms < 5:
            self.result.add_warning(
                f"Very short debounce time ({debounce_ms}ms) may cause false triggers",
                path="calibration.debounce_ms"
            )

        if debounce_ms > 100:
            self.result.add_warning(
                f"Long debounce time ({debounce_ms}ms) may miss rapid pulses",
                path="calibration.debounce_ms"
            )

        # Check runout threshold
        runout_ms = config.calibration.runout_threshold_ms
        if runout_ms < 100:
            self.result.add_warning(
                f"Very short runout threshold ({runout_ms}ms) may cause false alarms",
                path="calibration.runout_threshold_ms"
            )

        # Validate GPIO pin assignments for MCP2221A
        self._validate_mcp2221a_pins(config)

    def _validate_mcp2221a_pins(self, config: SensorConfiguration) -> None:
        """Validate GPIO pins are valid for MCP2221A."""
        all_pins = [
            config.sensor1_gpio.movement_pin,
            config.sensor1_gpio.runout_pin,
            config.sensor2_gpio.movement_pin,
            config.sensor2_gpio.runout_pin
        ]

        for pin in all_pins:
            if pin not in range(4):  # MCP2221A has GP0-GP3
                self.result.add_error(ConfigValidationError(
                    f"Invalid GPIO pin {pin} - MCP2221A supports pins 0-3 only",
                    path="gpio_mappings"
                ))

        # Check recommended pin assignments
        recommended_mapping = {
            0: "sensor1_movement",
            1: "sensor1_runout",
            2: "sensor2_movement",
            3: "sensor2_runout"
        }

        actual_mapping = config.gpio_pin_map
        if actual_mapping != recommended_mapping:
            self.result.add_info(
                "Using non-standard GPIO pin mapping (may be intentional)"
            )


def validate_config_dict(config_data: Dict[str, Any], strict: bool = False) -> ValidationResult:
    """Validate configuration dictionary (convenience function)."""
    validator = ConfigValidator(strict_mode=strict)
    return validator.validate_config(config_data)


def validate_config_file(file_path: Union[str, Path], strict: bool = False) -> ValidationResult:
    """Validate configuration YAML file (convenience function)."""
    validator = ConfigValidator(strict_mode=strict)
    return validator.validate_yaml_file(file_path)


def create_config_schema() -> Dict[str, Any]:
    """Create JSON schema for configuration validation."""
    return {
        "type": "object",
        "required": ["sensor1_gpio", "sensor2_gpio", "calibration", "polling"],
        "properties": {
            "sensor1_gpio": {
                "type": "object",
                "required": ["movement_pin", "runout_pin"],
                "properties": {
                    "movement_pin": {"type": "integer", "minimum": 0, "maximum": 3},
                    "runout_pin": {"type": "integer", "minimum": 0, "maximum": 3}
                }
            },
            "sensor2_gpio": {
                "type": "object",
                "required": ["movement_pin", "runout_pin"],
                "properties": {
                    "movement_pin": {"type": "integer", "minimum": 0, "maximum": 3},
                    "runout_pin": {"type": "integer", "minimum": 0, "maximum": 3}
                }
            },
            "calibration": {
                "type": "object",
                "properties": {
                    "mm_per_pulse": {"type": "number", "minimum": 0.001, "maximum": 100},
                    "debounce_ms": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "runout_threshold_ms": {"type": "integer", "minimum": 100, "maximum": 5000}
                }
            },
            "polling": {
                "type": "object",
                "properties": {
                    "polling_interval_ms": {"type": "integer", "minimum": 10, "maximum": 1000},
                    "ui_update_interval_ms": {"type": "integer", "minimum": 50, "maximum": 1000},
                    "api_response_timeout_ms": {"type": "integer", "minimum": 1000, "maximum": 30000}
                }
            },
            "enable_debug_logging": {"type": "boolean"},
            "api_port": {"type": "integer", "minimum": 1024, "maximum": 65535}
        },
        "additionalProperties": False
    }


def generate_example_config() -> Dict[str, Any]:
    """Generate example configuration dictionary."""
    return {
        "sensor1_gpio": {
            "movement_pin": 0,
            "runout_pin": 1
        },
        "sensor2_gpio": {
            "movement_pin": 2,
            "runout_pin": 3
        },
        "calibration": {
            "mm_per_pulse": 2.88,
            "debounce_ms": 10,
            "runout_threshold_ms": 500
        },
        "polling": {
            "polling_interval_ms": 100,
            "ui_update_interval_ms": 100,
            "api_response_timeout_ms": 5000
        },
        "enable_debug_logging": False,
        "api_port": 5002
    }