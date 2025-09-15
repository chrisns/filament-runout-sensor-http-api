"""Command-line interface for configuration management.

Provides CLI tools for validating, creating, exporting, and managing
filament sensor configuration files.

Usage:
    python -m src.lib.config [COMMAND] [OPTIONS]

Commands:
    validate    - Validate configuration file
    export      - Export configuration to different formats
    create      - Create new configuration file
    merge       - Merge configuration files
    schema      - Generate/export configuration schema

Examples:
    # Validate configuration
    python -m src.lib.config validate config.yaml

    # Create default configuration
    python -m src.lib.config create --output config.yaml

    # Export with validation
    python -m src.lib.config export config.yaml --output exported.yaml --validate
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.lib.config import (
    ConfigManager,
    ConfigurationError,
    load_config_from_file,
    save_config_to_file,
    create_default_config_file
)
from src.lib.config.validation import (
    validate_config_file,
    create_config_schema,
    generate_example_config
)
from src.models.sensor_configuration import SensorConfiguration


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Filament Sensor Configuration Management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Global options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="COMMAND"
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration file"
    )
    validate_parser.add_argument(
        "config_file",
        type=Path,
        help="Path to configuration file to validate"
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation mode"
    )
    validate_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for validation results"
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export configuration to different formats"
    )
    export_parser.add_argument(
        "config_file",
        type=Path,
        help="Path to configuration file to export"
    )
    export_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path (default: stdout)"
    )
    export_parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Export format"
    )
    export_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate before exporting"
    )
    export_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output"
    )

    # Create command
    create_parser = subparsers.add_parser(
        "create",
        help="Create new configuration file"
    )
    create_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output file path"
    )
    create_parser.add_argument(
        "--template",
        choices=["default", "minimal", "comprehensive"],
        default="default",
        help="Configuration template type"
    )
    create_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing file"
    )

    # Merge command
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge configuration files"
    )
    merge_parser.add_argument(
        "base_config",
        type=Path,
        help="Base configuration file"
    )
    merge_parser.add_argument(
        "override_config",
        type=Path,
        help="Override configuration file"
    )
    merge_parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output merged configuration file"
    )
    merge_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate merged configuration"
    )

    # Schema command
    schema_parser = subparsers.add_parser(
        "schema",
        help="Generate configuration schema"
    )
    schema_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output schema file (default: stdout)"
    )
    schema_parser.add_argument(
        "--format",
        choices=["json", "yaml"],
        default="json",
        help="Schema format"
    )

    # Info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show configuration information"
    )
    info_parser.add_argument(
        "config_file",
        type=Path,
        help="Path to configuration file"
    )
    info_parser.add_argument(
        "--format",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format"
    )

    return parser


def cmd_validate(args) -> int:
    """Handle validate command."""
    try:
        print(f"Validating configuration: {args.config_file}")

        result = validate_config_file(args.config_file, strict=args.strict)

        if args.format == "json":
            print(json.dumps(result.get_summary(), indent=2))
        else:
            result.print_results(verbose=args.verbose)

        return 0 if result.is_valid else 1

    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        return 1


def cmd_export(args) -> int:
    """Handle export command."""
    try:
        # Load and validate configuration
        if args.validate:
            result = validate_config_file(args.config_file)
            if not result.is_valid:
                print("Configuration validation failed:", file=sys.stderr)
                result.print_results(verbose=False)
                return 1

        # Load configuration
        config = load_config_from_file(args.config_file, validate=args.validate)

        # Export to requested format
        if args.format == "json":
            output_content = json.dumps(
                config.export_dict(),
                indent=2 if args.pretty else None,
                sort_keys=True
            )
        else:  # yaml
            manager = ConfigManager(args.config_file, validate=False)
            manager._current_config = config
            output_content = manager.export_config_yaml()

        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"Configuration exported to: {args.output}")
        else:
            print(output_content)

        return 0

    except Exception as e:
        print(f"Export error: {e}", file=sys.stderr)
        return 1


def cmd_create(args) -> int:
    """Handle create command."""
    try:
        # Check if file exists
        if args.output.exists() and not args.overwrite:
            print(f"File already exists: {args.output}", file=sys.stderr)
            print("Use --overwrite to replace existing file")
            return 1

        # Generate configuration based on template
        if args.template == "minimal":
            config_data = {
                "sensor1_gpio": {"movement_pin": 0, "runout_pin": 1},
                "sensor2_gpio": {"movement_pin": 2, "runout_pin": 3},
                "calibration": {"mm_per_pulse": 2.88},
                "polling": {"polling_interval_ms": 100}
            }
        elif args.template == "comprehensive":
            config_data = generate_example_config()
            # Add additional comprehensive settings
            config_data.update({
                "enable_debug_logging": True,
                "api_port": 5002
            })
        else:  # default
            config_data = generate_example_config()

        # Create configuration object and save
        config = SensorConfiguration(**config_data)
        save_config_to_file(config, args.output)

        print(f"Created configuration file: {args.output}")
        print(f"Template: {args.template}")

        return 0

    except Exception as e:
        print(f"Create error: {e}", file=sys.stderr)
        return 1


def cmd_merge(args) -> int:
    """Handle merge command."""
    try:
        # Load base configuration
        base_manager = ConfigManager(args.base_config, validate=False)
        base_config = base_manager.load_config()

        # Load override configuration
        import yaml
        with open(args.override_config, 'r', encoding='utf-8') as f:
            override_data = yaml.safe_load(f) or {}

        # Merge configurations
        merged_config = base_manager.merge_config(override_data)

        # Validate if requested
        if args.validate:
            validation_result = base_manager.validate_current_config()
            if not validation_result.is_valid:
                print("Merged configuration validation failed:", file=sys.stderr)
                validation_result.print_results(verbose=False)
                return 1

        # Save merged configuration
        save_config_to_file(merged_config, args.output)

        print(f"Merged configuration saved to: {args.output}")
        print(f"Base: {args.base_config}")
        print(f"Override: {args.override_config}")

        return 0

    except Exception as e:
        print(f"Merge error: {e}", file=sys.stderr)
        return 1


def cmd_schema(args) -> int:
    """Handle schema command."""
    try:
        schema = create_config_schema()

        if args.format == "yaml":
            import yaml
            output_content = yaml.dump(schema, default_flow_style=False, indent=2)
        else:  # json
            output_content = json.dumps(schema, indent=2, sort_keys=True)

        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"Schema exported to: {args.output}")
        else:
            print(output_content)

        return 0

    except Exception as e:
        print(f"Schema error: {e}", file=sys.stderr)
        return 1


def cmd_info(args) -> int:
    """Handle info command."""
    try:
        # Load configuration
        config = load_config_from_file(args.config_file, validate=True)

        # Gather information
        info_data = {
            "file_path": str(args.config_file),
            "file_size": args.config_file.stat().st_size,
            "last_modified": args.config_file.stat().st_mtime,
            "configuration": {
                "api_port": config.api_port,
                "debug_logging": config.enable_debug_logging,
                "polling_frequency_hz": config.polling.polling_frequency_hz,
                "mm_per_pulse": config.calibration.mm_per_pulse,
                "gpio_pins": config.gpio_pin_map
            },
            "validation": "passed"
        }

        # Output in requested format
        if args.format == "json":
            print(json.dumps(info_data, indent=2, default=str))
        elif args.format == "yaml":
            import yaml
            print(yaml.dump(info_data, default_flow_style=False, indent=2))
        else:  # text
            print(f"Configuration File: {info_data['file_path']}")
            print(f"Size: {info_data['file_size']} bytes")
            print(f"Last Modified: {info_data['last_modified']}")
            print(f"\nSettings:")
            print(f"  API Port: {info_data['configuration']['api_port']}")
            print(f"  Debug Logging: {info_data['configuration']['debug_logging']}")
            print(f"  Polling Frequency: {info_data['configuration']['polling_frequency_hz']:.1f} Hz")
            print(f"  mm per Pulse: {info_data['configuration']['mm_per_pulse']}")
            print(f"\nGPIO Pin Mapping:")
            for pin, function in info_data['configuration']['gpio_pins'].items():
                print(f"  GP{pin}: {function}")

        return 0

    except Exception as e:
        print(f"Info error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the configuration CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Command dispatch
    commands = {
        "validate": cmd_validate,
        "export": cmd_export,
        "create": cmd_create,
        "merge": cmd_merge,
        "schema": cmd_schema,
        "info": cmd_info
    }

    if args.command not in commands:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    try:
        return commands[args.command](args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def quick_validate(config_path: str) -> bool:
    """Quick validation function for testing."""
    try:
        result = validate_config_file(config_path)
        return result.is_valid
    except Exception:
        return False


def create_sample_configs() -> None:
    """Create sample configuration files for testing."""
    # Create default config
    create_default_config_file("sample_config.yaml")
    print("Created: sample_config.yaml")

    # Create minimal config
    minimal_data = {
        "sensor1_gpio": {"movement_pin": 0, "runout_pin": 1},
        "sensor2_gpio": {"movement_pin": 2, "runout_pin": 3},
        "calibration": {"mm_per_pulse": 2.88},
        "polling": {"polling_interval_ms": 100}
    }
    minimal_config = SensorConfiguration(**minimal_data)
    save_config_to_file(minimal_config, "minimal_config.yaml")
    print("Created: minimal_config.yaml")


if __name__ == "__main__":
    # Handle special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--create-samples":
            create_sample_configs()
            sys.exit(0)
        elif sys.argv[1] == "--test-validation":
            # Quick test of validation functionality
            create_default_config_file("test_config.yaml")
            is_valid = quick_validate("test_config.yaml")
            print(f"Validation test: {'PASSED' if is_valid else 'FAILED'}")
            Path("test_config.yaml").unlink(missing_ok=True)
            sys.exit(0 if is_valid else 1)

    # Run normal CLI
    sys.exit(main())