"""Main CLI application orchestrating all components."""

import argparse
import asyncio
import sys
import signal
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json

import structlog

from ..models import SystemStatus, SensorConfiguration
from ..services import SensorMonitor, DataAggregator, SessionStorage
from ..lib.api_server import run_server, set_system_status, connection_manager
from ..lib.config import load_configuration, load_default_configuration, export_configuration
from ..lib.display import FilamentSensorApp


logger = structlog.get_logger(__name__)


class FilamentSensorApplication:
    """Main application orchestrating all components."""

    def __init__(self):
        """Initialize the application."""
        # Core components
        self.system_status = SystemStatus.get_instance()
        self.sensor_monitor: Optional[SensorMonitor] = None
        self.data_aggregator: Optional[DataAggregator] = None
        self.session_storage: Optional[SessionStorage] = None

        # Configuration
        self.configuration: Optional[SensorConfiguration] = None

        # Runtime state
        self.is_running = False
        self.api_server_task: Optional[asyncio.Task] = None
        self.display_task: Optional[asyncio.Task] = None

    async def initialize(self,
                        config_path: Optional[str] = None,
                        demo_mode: bool = False,
                        in_memory_storage: bool = True) -> None:
        """Initialize all application components."""
        try:
            logger.info("Initializing filament sensor application")

            # Load configuration
            if config_path and Path(config_path).exists():
                self.configuration = load_configuration(config_path)
                logger.info("Loaded configuration from file", config_path=config_path)
            else:
                self.configuration = load_default_configuration()
                logger.info("Using default configuration")

            # Initialize session storage
            self.session_storage = SessionStorage(
                in_memory=in_memory_storage,
                max_retention_hours=24
            )
            await self.session_storage.initialize()

            # Initialize data aggregator
            self.data_aggregator = DataAggregator(self.system_status)

            # Initialize sensor monitor
            if not demo_mode:
                self.sensor_monitor = SensorMonitor(self.system_status)

                # Connect data aggregator to sensor monitor for real-time updates
                self.sensor_monitor.add_update_callback(self.data_aggregator.add_sensor_reading)
                self.sensor_monitor.add_update_callback(self._on_sensor_update)
            else:
                logger.info("Running in demo mode - hardware monitoring disabled")

            # Set up system status with configuration
            self.system_status.start_system(self.configuration)

            # Set global reference for API server
            set_system_status(self.system_status)

            logger.info("Application initialization completed")

        except Exception as e:
            logger.error("Failed to initialize application", error=str(e))
            raise

    async def start(self,
                   enable_api: bool = True,
                   api_port: int = 5002,
                   enable_display: bool = True,
                   demo_mode: bool = False,
                   debug: bool = False) -> None:
        """Start all application components."""
        try:
            logger.info("Starting filament sensor application",
                       enable_api=enable_api,
                       enable_display=enable_display,
                       demo_mode=demo_mode)

            self.is_running = True

            # Start data aggregation
            await self.data_aggregator.start_aggregation()

            # Start sensor monitoring (unless demo mode)
            if self.sensor_monitor and not demo_mode:
                await self.sensor_monitor.start_monitoring(self.configuration)
            elif demo_mode:
                await self._setup_demo_data()

            # Start API server
            if enable_api:
                self.api_server_task = asyncio.create_task(
                    self._run_api_server(api_port, debug)
                )

            # Start display interface
            if enable_display:
                self.display_task = asyncio.create_task(
                    self._run_display_interface()
                )

            logger.info("All components started successfully")

            # Set up graceful shutdown
            self._setup_signal_handlers()

        except Exception as e:
            logger.error("Failed to start application", error=str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all application components gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping filament sensor application")

        self.is_running = False

        try:
            # Stop sensor monitoring
            if self.sensor_monitor:
                await self.sensor_monitor.stop_monitoring()

            # Stop data aggregation
            if self.data_aggregator:
                await self.data_aggregator.stop_aggregation()

            # Stop API server
            if self.api_server_task:
                self.api_server_task.cancel()
                try:
                    await self.api_server_task
                except asyncio.CancelledError:
                    pass

            # Stop display interface
            if self.display_task:
                self.display_task.cancel()
                try:
                    await self.display_task
                except asyncio.CancelledError:
                    pass

            # Close session storage
            if self.session_storage:
                await self.session_storage.close()

            # Update system status
            self.system_status.stop_system()

            logger.info("Application stopped successfully")

        except Exception as e:
            logger.error("Error during application shutdown", error=str(e))

    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive application status."""
        status = {
            "application": {
                "is_running": self.is_running,
                "components": {
                    "sensor_monitor": self.sensor_monitor is not None,
                    "data_aggregator": self.data_aggregator is not None,
                    "session_storage": self.session_storage is not None,
                    "api_server": self.api_server_task is not None and not self.api_server_task.done(),
                    "display": self.display_task is not None and not self.display_task.done()
                }
            },
            "system_status": self.system_status.export_status(),
            "performance": {}
        }

        # Add component-specific statistics
        if self.sensor_monitor:
            status["performance"]["sensor_monitor"] = self.sensor_monitor.get_monitoring_stats()

        if self.data_aggregator:
            status["performance"]["data_aggregator"] = self.data_aggregator.get_aggregation_stats()

        if self.session_storage:
            status["performance"]["session_storage"] = self.session_storage.get_storage_stats()

        return status

    async def export_data(self, output_path: str) -> bool:
        """Export all application data."""
        try:
            logger.info("Exporting application data", output_path=output_path)

            export_data = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "application_version": "1.0.0",
                    "export_type": "full_session"
                },
                "configuration": self.configuration.model_dump() if self.configuration else None,
                "system_status": self.system_status.export_status(),
                "application_status": await self.get_status()
            }

            # Export session storage data if available
            if self.session_storage:
                storage_export_path = f"{output_path}_storage.json"
                await self.session_storage.export_session_data(storage_export_path)
                export_data["storage_export_path"] = storage_export_path

            # Write main export file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info("Application data exported successfully", output_path=output_path)
            return True

        except Exception as e:
            logger.error("Failed to export application data", error=str(e))
            return False

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal", signal=sig)
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _on_sensor_update(self, reading) -> None:
        """Handle sensor reading updates."""
        try:
            # Store reading in session storage
            if self.session_storage:
                await self.session_storage.store_sensor_reading(reading)

            # Broadcast to WebSocket clients
            await connection_manager.broadcast_sensor_update(reading)

        except Exception as e:
            logger.error("Error handling sensor update", error=str(e))

    async def _setup_demo_data(self) -> None:
        """Set up demo data for testing."""
        from ..models import SensorReading, AlertEvent, AlertType, AlertSeverity

        logger.info("Setting up demo data")

        # Create demo sensor readings
        demo_reading_1 = SensorReading(
            sensor_id=1,
            has_filament=True,
            is_moving=True,
            pulse_count=2000,
            distance_mm=5760.0,  # 2000 * 2.88
            raw_gpio_state={"GP0": True, "GP1": False, "GP2": False, "GP3": False}
        )

        demo_reading_2 = SensorReading(
            sensor_id=2,
            has_filament=True,
            is_moving=False,
            pulse_count=1500,
            distance_mm=4320.0,  # 1500 * 2.88
            raw_gpio_state={"GP0": False, "GP1": False, "GP2": False, "GP3": False}
        )

        # Update system status
        self.system_status.update_sensor_reading(demo_reading_1)
        self.system_status.update_sensor_reading(demo_reading_2)
        self.system_status.update_hardware_status(True)

        # Add demo alert
        self.system_status.add_alert(AlertEvent(
            alert_type=AlertType.SYSTEM_STARTED,
            severity=AlertSeverity.INFO,
            message="Demo mode: Application started with simulated data"
        ))

        # Simulate ongoing updates
        asyncio.create_task(self._demo_update_loop())

    async def _demo_update_loop(self) -> None:
        """Demo update loop for simulated data."""
        from ..models import SensorReading
        pulse_count_1 = 2000
        pulse_count_2 = 1500

        while self.is_running:
            try:
                # Update sensor 1 (moving)
                pulse_count_1 += 5
                demo_reading_1 = SensorReading(
                    sensor_id=1,
                    has_filament=True,
                    is_moving=True,
                    pulse_count=pulse_count_1,
                    distance_mm=pulse_count_1 * 2.88,
                    raw_gpio_state={"GP0": True, "GP1": False, "GP2": False, "GP3": False}
                )

                self.system_status.update_sensor_reading(demo_reading_1)
                await self._on_sensor_update(demo_reading_1)

                # Occasionally update sensor 2
                if pulse_count_1 % 20 == 0:  # Every 4 seconds
                    pulse_count_2 += 2
                    demo_reading_2 = SensorReading(
                        sensor_id=2,
                        has_filament=True,
                        is_moving=True,
                        pulse_count=pulse_count_2,
                        distance_mm=pulse_count_2 * 2.88,
                        raw_gpio_state={"GP0": False, "GP1": False, "GP2": True, "GP3": False}
                    )

                    self.system_status.update_sensor_reading(demo_reading_2)
                    await self._on_sensor_update(demo_reading_2)

                await asyncio.sleep(0.2)  # 200ms updates

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in demo update loop", error=str(e))
                await asyncio.sleep(1.0)

    async def _run_api_server(self, port: int, debug: bool) -> None:
        """Run the API server in a separate task."""
        try:
            import uvicorn
            from ..lib.api_server import create_app

            app = create_app()

            config = uvicorn.Config(
                app=app,
                host="localhost",
                port=port,
                log_level="debug" if debug else "info"
            )

            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error("API server error", error=str(e))

    async def _run_display_interface(self) -> None:
        """Run the display interface."""
        try:
            # Create and run the Textual app
            app = FilamentSensorApp(self.system_status)
            await app.run_async()

        except Exception as e:
            logger.error("Display interface error", error=str(e))


async def main_async():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Filament Sensor Monitor - MCP2221A-based dual sensor monitoring system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.main                           # Start with default settings
  python -m src.cli.main --config config.json     # Load specific configuration
  python -m src.cli.main --demo                    # Run in demo mode
  python -m src.cli.main --no-api                  # Run without API server
  python -m src.cli.main --debug                   # Enable debug logging
  python -m src.cli.main --export-config          # Export default config and exit
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and verbose output"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode with simulated sensor data"
    )

    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Disable the HTTP API server"
    )

    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable the terminal display interface"
    )

    parser.add_argument(
        "--api-port",
        type=int,
        default=5002,
        help="Port for HTTP API server (default: 5002)"
    )

    parser.add_argument(
        "--export-config",
        type=str,
        help="Export default configuration to specified path and exit"
    )

    parser.add_argument(
        "--export-data",
        type=str,
        help="Export application data to specified path and exit"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = "DEBUG" if args.debug else "INFO"
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer(colors=True)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(structlog, log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Handle export config
    if args.export_config:
        try:
            config = load_default_configuration()
            export_configuration(config, args.export_config)
            logger.info("Configuration exported successfully", path=args.export_config)
            return 0
        except Exception as e:
            logger.error("Failed to export configuration", error=str(e))
            return 1

    # Initialize and run application
    app = FilamentSensorApplication()

    try:
        # Initialize
        await app.initialize(
            config_path=args.config,
            demo_mode=args.demo,
            in_memory_storage=True  # Always use in-memory for session-only requirement
        )

        # Handle data export
        if args.export_data:
            success = await app.export_data(args.export_data)
            return 0 if success else 1

        # Start application
        await app.start(
            enable_api=not args.no_api,
            api_port=args.api_port,
            enable_display=not args.no_display,
            demo_mode=args.demo,
            debug=args.debug
        )

        # Keep running until stopped
        while app.is_running:
            await asyncio.sleep(1)

        return 0

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error("Application error", error=str(e))
        return 1
    finally:
        await app.stop()


def main():
    """Main entry point."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())