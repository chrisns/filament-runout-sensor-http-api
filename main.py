#!/usr/bin/env python3
"""
MCP2221A Dual Filament Sensor Monitor - Main Application
Orchestrates all components for real-time filament monitoring.
"""

import sys
import asyncio
import argparse
import logging
import json
import signal
from pathlib import Path
from typing import Optional

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Component availability flags
COMPONENTS_AVAILABLE = {
    'mcp2221': False,
    'display': False,
    'api': False,
    'config': False
}

# Try to import components
try:
    from src.lib.mcp2221_sensor import MCP2221Manager
    from src.lib.mcp2221_sensor.pulse_detector import PulseDetector
    COMPONENTS_AVAILABLE['mcp2221'] = True
except ImportError as e:
    logger.warning(f"MCP2221 sensor library not available: {e}")

try:
    from src.lib.display import SensorMonitorApp
    COMPONENTS_AVAILABLE['display'] = True
except ImportError as e:
    logger.warning(f"Display library not available: {e}")

try:
    from src.lib.api_server import create_app, run_server
    COMPONENTS_AVAILABLE['api'] = True
except ImportError as e:
    logger.warning(f"API server not available: {e}")

try:
    from src.lib.config import ConfigManager
    COMPONENTS_AVAILABLE['config'] = True
except ImportError as e:
    logger.warning(f"Config library not available: {e}")

try:
    from src.services.sensor_monitor import SensorMonitor
    from src.services.data_aggregator import DataAggregator
    from src.services.session_storage import SessionStorage
except ImportError as e:
    logger.warning(f"Core services not available: {e}")

try:
    from src.models import SystemStatus, SensorReading
except ImportError as e:
    logger.warning(f"Data models not available: {e}")


class FilamentMonitorApp:
    """Main application orchestrator."""

    def __init__(self, config_path: str = "config.yaml", demo: bool = False):
        self.config_path = config_path
        self.demo_mode = demo
        self.running = False
        self.components = {}
        self.tasks = []

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Filament Monitor Application...")

        # Load configuration
        if COMPONENTS_AVAILABLE['config']:
            try:
                self.components['config'] = ConfigManager(self.config_path)
                config = self.components['config'].get_config()
                logger.info(f"Configuration loaded from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                config = self.get_default_config()
        else:
            config = self.get_default_config()

        # Initialize system status
        try:
            self.components['status'] = SystemStatus()
            self.components['status'].start_system()
        except:
            logger.warning("System status not available")

        # Initialize session storage
        try:
            self.components['storage'] = SessionStorage(":memory:")
            await self.components['storage'].initialize()
            logger.info("Session storage initialized")
        except Exception as e:
            logger.warning(f"Session storage not available: {e}")

        # Initialize data aggregator
        try:
            self.components['aggregator'] = DataAggregator(
                storage=self.components.get('storage'),
                config=config
            )
            logger.info("Data aggregator initialized")
        except Exception as e:
            logger.warning(f"Data aggregator not available: {e}")

        # Initialize hardware or demo mode
        if self.demo_mode:
            logger.info("Running in DEMO mode - no hardware required")
            self.components['monitor'] = self.create_demo_monitor()
        elif COMPONENTS_AVAILABLE['mcp2221']:
            try:
                self.components['hardware'] = MCP2221Manager()
                self.components['monitor'] = SensorMonitor(
                    hardware_manager=self.components['hardware'],
                    config=config,
                    callback=self.on_sensor_reading
                )
                logger.info("Hardware monitoring initialized")
            except Exception as e:
                logger.warning(f"Hardware not available, switching to demo: {e}")
                self.demo_mode = True
                self.components['monitor'] = self.create_demo_monitor()
        else:
            logger.warning("MCP2221 library not available, running in demo mode")
            self.demo_mode = True
            self.components['monitor'] = self.create_demo_monitor()

        return True

    def create_demo_monitor(self):
        """Create a demo monitor that generates fake sensor data."""
        class DemoMonitor:
            def __init__(self, callback):
                self.callback = callback
                self.running = False

            async def start(self):
                self.running = True
                pulse_count = [0, 0]
                while self.running:
                    # Generate fake sensor readings
                    import random
                    from datetime import datetime

                    for sensor_id in [1, 2]:
                        # Simulate movement on sensor 1, idle on sensor 2
                        is_moving = (sensor_id == 1 and random.random() > 0.3)
                        if is_moving:
                            pulse_count[sensor_id - 1] += 1

                        reading = {
                            'timestamp': datetime.utcnow(),
                            'sensor_id': sensor_id,
                            'has_filament': True,
                            'is_moving': is_moving,
                            'pulse_count': pulse_count[sensor_id - 1],
                            'distance_mm': pulse_count[sensor_id - 1] * 2.88
                        }

                        if self.callback:
                            await self.callback(reading)

                    await asyncio.sleep(0.5)

            async def stop(self):
                self.running = False

        return DemoMonitor(self.on_sensor_reading)

    async def on_sensor_reading(self, reading: dict):
        """Handle new sensor reading."""
        try:
            # Update system status
            if 'status' in self.components:
                sensor_reading = SensorReading(**reading)
                self.components['status'].update_sensor_reading(
                    reading['sensor_id'],
                    sensor_reading
                )

            # Store in session storage
            if 'storage' in self.components:
                await self.components['storage'].store_reading(reading)

            # Update aggregator
            if 'aggregator' in self.components:
                await self.components['aggregator'].process_reading(reading)

            # Broadcast via WebSocket if API is running
            if 'api' in self.components:
                # This would be implemented in the API server
                pass

        except Exception as e:
            logger.error(f"Error processing sensor reading: {e}")

    def get_default_config(self):
        """Get default configuration."""
        return {
            'sensors': {
                'sensor_1': {
                    'movement_pin': 0,
                    'runout_pin': 1,
                    'calibration_mm_per_pulse': 2.88,
                    'enabled': True
                },
                'sensor_2': {
                    'movement_pin': 2,
                    'runout_pin': 3,
                    'calibration_mm_per_pulse': 2.88,
                    'enabled': True
                }
            },
            'polling': {
                'interval_ms': 100,
                'debounce_ms': 2,
                'timeout_seconds': 5
            },
            'api': {
                'port': 5002,
                'host': '0.0.0.0'
            }
        }

    async def start_components(self, enable_api=True, enable_display=True):
        """Start all enabled components."""
        self.running = True

        # Start sensor monitoring
        if 'monitor' in self.components:
            monitor_task = asyncio.create_task(self.components['monitor'].start())
            self.tasks.append(monitor_task)
            logger.info("Sensor monitoring started")

        # Start API server
        if enable_api and COMPONENTS_AVAILABLE['api']:
            try:
                config = self.components.get('config', {}).get_config() if 'config' in self.components else self.get_default_config()
                api_config = config.get('api', {})

                # Create API app with components
                app = await create_app(
                    status=self.components.get('status'),
                    storage=self.components.get('storage'),
                    config_manager=self.components.get('config')
                )

                # Run in background task
                api_task = asyncio.create_task(
                    run_server(
                        app,
                        host=api_config.get('host', '0.0.0.0'),
                        port=api_config.get('port', 5002)
                    )
                )
                self.tasks.append(api_task)
                self.components['api'] = app
                logger.info(f"API server started on port {api_config.get('port', 5002)}")
            except Exception as e:
                logger.error(f"Failed to start API server: {e}")

        # Start terminal display
        if enable_display and COMPONENTS_AVAILABLE['display']:
            try:
                display_app = SensorMonitorApp(
                    system_status=self.components.get('status'),
                    demo_mode=self.demo_mode
                )
                display_task = asyncio.create_task(display_app.run_async())
                self.tasks.append(display_task)
                self.components['display'] = display_app
                logger.info("Terminal display started")
            except Exception as e:
                logger.error(f"Failed to start display: {e}")

        # Start data aggregation background task
        if 'aggregator' in self.components:
            aggregator_task = asyncio.create_task(
                self.components['aggregator'].start_background_tasks()
            )
            self.tasks.append(aggregator_task)

    async def stop_components(self):
        """Stop all components gracefully."""
        logger.info("Shutting down components...")
        self.running = False

        # Stop monitor
        if 'monitor' in self.components:
            await self.components['monitor'].stop()

        # Stop aggregator
        if 'aggregator' in self.components:
            await self.components['aggregator'].stop()

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)

        # Stop system
        if 'status' in self.components:
            self.components['status'].stop_system()

        logger.info("All components stopped")

    async def run(self, enable_api=True, enable_display=True):
        """Main application loop."""
        try:
            # Initialize
            if not await self.initialize():
                logger.error("Failed to initialize application")
                return 1

            # Start components
            await self.start_components(enable_api, enable_display)

            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("\nReceived interrupt signal")
        except Exception as e:
            logger.error(f"Application error: {e}")
            return 1
        finally:
            await self.stop_components()

        return 0

    async def export_config(self, output_path: str, format: str = 'json'):
        """Export current configuration."""
        if 'config' in self.components:
            config = self.components['config'].get_config()
        else:
            config = self.get_default_config()

        output = Path(output_path)
        if format == 'json':
            output.write_text(json.dumps(config, indent=2))
        else:  # yaml
            import yaml
            output.write_text(yaml.dump(config, default_flow_style=False))

        logger.info(f"Configuration exported to {output_path}")

    async def export_data(self, output_path: str):
        """Export session data."""
        if 'storage' in self.components:
            await self.components['storage'].export_data(output_path)
            logger.info(f"Session data exported to {output_path}")
        else:
            logger.warning("No session data to export")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP2221A Dual Filament Sensor Monitor"
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Configuration file path'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run in demo mode (no hardware required)'
    )
    parser.add_argument(
        '--no-api',
        action='store_true',
        help='Disable API server'
    )
    parser.add_argument(
        '--no-display',
        action='store_true',
        help='Disable terminal display'
    )
    parser.add_argument(
        '--export-config',
        metavar='FILE',
        help='Export configuration and exit'
    )
    parser.add_argument(
        '--export-data',
        metavar='FILE',
        help='Export session data and exit'
    )

    args = parser.parse_args()

    # Set debug logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create application
    app = FilamentMonitorApp(
        config_path=args.config,
        demo=args.demo
    )

    # Handle exports
    if args.export_config:
        format = 'json' if args.export_config.endswith('.json') else 'yaml'
        asyncio.run(app.export_config(args.export_config, format))
        return 0

    if args.export_data:
        asyncio.run(app.export_data(args.export_data))
        return 0

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("\nShutdown signal received")
        app.running = False

    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal_handler)

    # Show startup message
    print("=" * 60)
    print("MCP2221A Dual Filament Sensor Monitor")
    print("=" * 60)
    print(f"Mode: {'DEMO' if args.demo else 'HARDWARE'}")
    print(f"API: {'DISABLED' if args.no_api else 'ENABLED (port 5002)'}")
    print(f"Display: {'DISABLED' if args.no_display else 'ENABLED'}")
    print(f"Config: {args.config}")
    print("=" * 60)
    print("\nPress Ctrl+C to stop\n")

    # Check component availability
    if not any(COMPONENTS_AVAILABLE.values()):
        print("\n⚠ WARNING: No components available!")
        print("Please install dependencies:")
        print("  pip install -r requirements.txt")
        print("\nRunning in limited mode...")

    # Run application
    return asyncio.run(
        app.run(
            enable_api=not args.no_api,
            enable_display=not args.no_display
        )
    )


if __name__ == "__main__":
    sys.exit(main())