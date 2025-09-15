"""CLI interface for the API server."""

import argparse
import asyncio
import sys
from typing import Optional

import structlog

from . import run_server, create_app, set_system_status
from ...models import SystemStatus


logger = structlog.get_logger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Filament Sensor API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.lib.api_server                    # Start server on default port 5002
  python -m src.lib.api_server --port 8080        # Start server on port 8080
  python -m src.lib.api_server --debug            # Start server with debug logging
  python -m src.lib.api_server --host 0.0.0.0     # Start server accessible from network
        """
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind the server to (default: localhost)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5002,
        help="Port to run the server on (default: 5002)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging and auto-reload"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Start in demo mode with mock data"
    )

    parser.add_argument(
        "--test-endpoints",
        action="store_true",
        help="Test all API endpoints and exit"
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

    if args.test_endpoints:
        asyncio.run(test_endpoints(args.host, args.port))
        return

    if args.demo:
        logger.info("Starting API server in demo mode")
        setup_demo_data()
    else:
        logger.info("Starting API server")

    try:
        run_server(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server error", error=str(e))
        sys.exit(1)


def setup_demo_data():
    """Set up demo data for testing the API."""
    from datetime import datetime, timedelta
    from ...models import (
        SensorConfiguration,
        SensorReading,
        AlertEvent,
        AlertType,
        AlertSeverity
    )

    # Initialize system status with demo data
    system_status = SystemStatus.get_instance()

    # Create demo configuration
    try:
        from ...lib.config import load_default_configuration
        config = load_default_configuration()
    except ImportError:
        # Fallback minimal configuration
        from ...models.sensor_configuration import (
            SensorConfig,
            PollingConfig,
            DetectionConfig,
            CalibrationConfig,
            LoggingConfig
        )

        config = SensorConfiguration(
            sensors=[
                SensorConfig(id=1, name="Demo Sensor 1", enabled=True),
                SensorConfig(id=2, name="Demo Sensor 2", enabled=True)
            ],
            polling=PollingConfig(polling_interval_ms=100),
            detection=DetectionConfig(),
            calibration=CalibrationConfig(),
            logging=LoggingConfig()
        )

    system_status.start_system(config)
    system_status.update_hardware_status(True)

    # Create demo sensor readings
    now = datetime.now()

    sensor1_reading = SensorReading(
        sensor_id=1,
        has_filament=True,
        is_moving=True,
        pulse_count=1500,
        distance_mm=4320.0,  # 1500 * 2.88
        raw_gpio_state={"GP0": True, "GP1": False, "GP2": False, "GP3": False}
    )

    sensor2_reading = SensorReading(
        sensor_id=2,
        has_filament=True,
        is_moving=False,
        pulse_count=800,
        distance_mm=2304.0,  # 800 * 2.88
        raw_gpio_state={"GP0": False, "GP1": False, "GP2": False, "GP3": False}
    )

    system_status.update_sensor_reading(sensor1_reading)
    system_status.update_sensor_reading(sensor2_reading)

    # Add demo alerts
    system_status.add_alert(AlertEvent(
        alert_type=AlertType.SYSTEM_STARTED,
        severity=AlertSeverity.INFO,
        message="Demo mode: API server started with mock data",
        timestamp=now - timedelta(minutes=5)
    ))

    system_status.add_alert(AlertEvent(
        alert_type=AlertType.SENSOR_MOVEMENT,
        severity=AlertSeverity.INFO,
        message="Demo: Sensor 1 movement detected",
        timestamp=now - timedelta(minutes=2),
        sensor_id=1
    ))

    # Set global reference for API
    set_system_status(system_status)

    logger.info("Demo data initialized",
               sensors=len(system_status.current_readings),
               alerts=len(system_status.recent_alerts))


async def test_endpoints(host: str, port: int):
    """Test all API endpoints."""
    import httpx

    base_url = f"http://{host}:{port}"

    endpoints = [
        "/health",
        "/status",
        "/config",
        "/metrics",
        "/alerts",
        "/connections"
    ]

    logger.info("Testing API endpoints", base_url=base_url)

    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            try:
                logger.info("Testing endpoint", endpoint=endpoint)
                response = await client.get(url, timeout=5.0)

                if response.status_code == 200:
                    logger.info("✓ Endpoint OK", endpoint=endpoint, status=response.status_code)
                else:
                    logger.warning("✗ Endpoint error", endpoint=endpoint, status=response.status_code)

            except httpx.ConnectError:
                logger.error("✗ Connection failed", endpoint=endpoint, message="Server not running?")
            except httpx.TimeoutException:
                logger.error("✗ Timeout", endpoint=endpoint)
            except Exception as e:
                logger.error("✗ Endpoint error", endpoint=endpoint, error=str(e))

    # Test WebSocket endpoint
    try:
        import websockets
        uri = f"ws://{host}:{port}/ws"
        logger.info("Testing WebSocket", uri=uri)

        async with websockets.connect(uri) as websocket:
            # Send ping
            await websocket.send('{"type": "ping"}')
            response = await websocket.recv()
            logger.info("✓ WebSocket OK", response=response)

    except ImportError:
        logger.warning("websockets not available, skipping WebSocket test")
    except Exception as e:
        logger.error("✗ WebSocket error", error=str(e))

    logger.info("Endpoint testing completed")


if __name__ == "__main__":
    main()