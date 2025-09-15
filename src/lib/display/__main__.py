"""Command-line interface for the display library.

Provides CLI access to the filament sensor monitoring display with various modes
including demo mode for testing and development.

Usage:
    python -m src.lib.display [OPTIONS]

Examples:
    # Run with demo data
    python -m src.lib.display --demo

    # Run in compact mode
    python -m src.lib.display --layout compact

    # Run with custom update interval
    python -m src.lib.display --update-interval 50
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.lib.display import SensorMonitorApp
from src.models.system_status import SystemStatus
from src.models.sensor_configuration import SensorConfiguration


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Filament Sensor Monitor Display",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                    # Run with simulated sensor data
  %(prog)s --layout compact          # Start in compact view mode
  %(prog)s --update-interval 50      # Update display every 50ms
  %(prog)s --demo --layout debug     # Demo mode with debug information
        """
    )

    # Display mode options
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Enable demo mode with simulated sensor data"
    )

    parser.add_argument(
        "--layout",
        choices=["split", "compact", "debug"],
        default="split",
        help="Initial display layout (default: split)"
    )

    # Update and timing options
    parser.add_argument(
        "--update-interval",
        type=int,
        default=100,
        metavar="MS",
        help="Display update interval in milliseconds (default: 100)"
    )

    # Connection options
    parser.add_argument(
        "--no-hardware",
        action="store_true",
        help="Run without attempting hardware connection (demo data only)"
    )

    # Display options
    parser.add_argument(
        "--title",
        type=str,
        default="Filament Sensor Monitor",
        help="Custom application title"
    )

    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="Display theme (default: dark)"
    )

    # Debug options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )

    return parser


def setup_logging(level: str, verbose: bool) -> None:
    """Setup logging configuration."""
    import logging
    import structlog

    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not verbose else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def create_demo_system_status() -> SystemStatus:
    """Create a system status instance with demo data."""
    import random
    from datetime import datetime
    from src.models.sensor_reading import SensorReading
    from src.models.alert_event import AlertEvent, AlertType, AlertSeverity

    # Create system status
    system_status = SystemStatus()

    # Configure with default settings
    config = SensorConfiguration()
    system_status.start_system(config)

    # Add some initial demo readings
    for sensor_id in [1, 2]:
        reading = SensorReading(
            sensor_id=sensor_id,
            has_filament=True,
            is_moving=random.choice([True, False]),
            pulse_count=random.randint(500, 5000),
            distance_mm=random.uniform(500.0, 2500.0)
        )
        system_status.update_sensor_reading(reading)

    # Set hardware as connected
    system_status.update_hardware_status(True)

    # Add a demo alert
    alert = AlertEvent(
        alert_type=AlertType.SYSTEM_STARTED,
        severity=AlertSeverity.INFO,
        message="Demo mode activated - simulated sensor data"
    )
    system_status.add_alert(alert)

    return system_status


def main() -> int:
    """Main entry point for the display CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.verbose)

    try:
        # Create system status
        if args.demo or args.no_hardware:
            system_status = create_demo_system_status()
        else:
            # In real mode, create empty system status
            # Hardware connection would be handled by main application
            system_status = SystemStatus()

        # Create application
        app = SensorMonitorApp(
            system_status=system_status,
            title=args.title
        )

        # Set initial layout
        app.layout_manager.set_current_layout(args.layout)

        # Configure update interval
        app.update_interval = args.update_interval / 1000.0  # Convert to seconds

        # Enable demo mode if requested
        if args.demo:
            app.enable_demo_mode()

        # Run the application
        if args.verbose:
            print(f"Starting {args.title}")
            print(f"Layout: {args.layout}")
            print(f"Update interval: {args.update_interval}ms")
            print(f"Demo mode: {'enabled' if args.demo else 'disabled'}")
            print("Press 'q' to quit, 'h' for help")

        app.run()
        return 0

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0

    except Exception as e:
        print(f"Error starting display: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def run_quick_demo() -> None:
    """Run a quick demo for testing purposes."""
    print("Starting quick demo...")

    # Create demo system
    system_status = create_demo_system_status()

    # Create and run app
    app = SensorMonitorApp(system_status=system_status)
    app.enable_demo_mode()

    print("Demo started. Press 'q' to quit.")
    app.run()


def validate_display_components() -> bool:
    """Validate that all display components can be imported and created."""
    try:
        from src.lib.display.widgets import (
            SensorStatusWidget,
            SystemHealthWidget,
            SessionMetricsWidget,
            AlertsPanelWidget,
            StatusBarWidget,
            LiveGraphWidget
        )
        from src.lib.display.layouts import (
            DualSensorSplitLayout,
            CompactMonitorLayout,
            DebugLayout,
            LayoutManager
        )

        # Test widget creation
        sensor_widget = SensorStatusWidget(sensor_id=1)
        health_widget = SystemHealthWidget()
        metrics_widget = SessionMetricsWidget()
        alerts_widget = AlertsPanelWidget()
        status_widget = StatusBarWidget()
        graph_widget = LiveGraphWidget(sensor_id=1)

        # Test layout creation
        split_layout = DualSensorSplitLayout()
        compact_layout = CompactMonitorLayout()
        debug_layout = DebugLayout()
        layout_manager = LayoutManager()

        print("✓ All display components validated successfully")
        return True

    except Exception as e:
        print(f"✗ Display component validation failed: {e}")
        return False


if __name__ == "__main__":
    # Handle special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick-demo":
            run_quick_demo()
            sys.exit(0)
        elif sys.argv[1] == "--validate":
            success = validate_display_components()
            sys.exit(0 if success else 1)

    # Run normal CLI
    sys.exit(main())