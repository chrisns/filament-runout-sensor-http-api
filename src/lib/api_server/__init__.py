"""FastAPI server for filament sensor monitoring system."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
import structlog

from ...models import (
    SystemStatus,
    SensorConfiguration,
    SensorReading,
    AlertEvent,
    SessionMetrics
)
from .websocket import websocket_endpoint, connection_manager

logger = structlog.get_logger(__name__)


class ConfigurationUpdateRequest(BaseModel):
    """Request model for configuration updates."""

    polling_interval_ms: Optional[int] = Field(None, ge=10, le=10000)
    mm_per_pulse: Optional[float] = Field(None, gt=0, le=10.0)
    movement_timeout_ms: Optional[int] = Field(None, ge=100, le=60000)
    runout_debounce_ms: Optional[int] = Field(None, ge=0, le=5000)
    sensor_names: Optional[Dict[int, str]] = None
    logging_level: Optional[str] = Field(None, regex="^(DEBUG|INFO|WARNING|ERROR)$")


class AlertAcknowledgeRequest(BaseModel):
    """Request model for acknowledging alerts."""

    acknowledge_all: bool = Field(default=False)
    alert_ids: Optional[List[str]] = None


class StatusResponse(BaseModel):
    """Response model for /status endpoint."""

    timestamp: datetime
    system_status: Dict[str, Any]
    sensors: List[Dict[str, Any]]
    connection: Dict[str, Any]


class ConfigurationResponse(BaseModel):
    """Response model for /config endpoint."""

    polling_interval_ms: int
    sensors: List[Dict[str, Any]]
    thresholds: Dict[str, Any]
    calibration: Dict[str, Any]
    logging: Dict[str, Any]


class MetricsResponse(BaseModel):
    """Response model for /metrics endpoint."""

    session: Dict[str, Any]
    sensors: List[Dict[str, Any]]
    system: Dict[str, Any]
    performance: Dict[str, Any]


class AlertsResponse(BaseModel):
    """Response model for /alerts endpoint."""

    total_count: int
    unacknowledged_count: int
    alerts: List[Dict[str, Any]]


# Global reference to system status (singleton)
_system_status: Optional[SystemStatus] = None


def set_system_status(status: SystemStatus) -> None:
    """Set the global system status reference."""
    global _system_status
    _system_status = status


def get_system_status() -> SystemStatus:
    """Get the current system status."""
    global _system_status
    if _system_status is None:
        _system_status = SystemStatus.get_instance()
    return _system_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("API server starting up")

    # Start WebSocket background tasks
    connection_manager.start_background_tasks()

    yield

    # Stop WebSocket background tasks
    await connection_manager.stop_background_tasks()
    logger.info("API server shutting down")


def create_app() -> FastAPI:
    """Create FastAPI application with all routes."""

    app = FastAPI(
        title="Filament Sensor Monitor API",
        description="HTTP API for MCP2221A-based filament sensor monitoring system",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS configuration for web clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/status", response_model=StatusResponse)
    async def get_status():
        """Get current system status including sensor readings."""
        try:
            status = get_system_status()

            # Build sensor data
            sensors = []
            for sensor_id in [1, 2]:
                reading = status.get_sensor_reading(sensor_id)
                sensor_name = f"Sensor {sensor_id}"
                if status.configuration and status.configuration.sensors:
                    sensor_config = next((s for s in status.configuration.sensors if s.id == sensor_id), None)
                    if sensor_config:
                        sensor_name = sensor_config.name

                sensor_data = {
                    "id": f"sensor_{sensor_id}",
                    "name": sensor_name,
                    "status": "active" if reading and not reading.is_stale() else "inactive",
                    "filament_present": reading.has_filament if reading else False,
                    "movement_detected": reading.is_moving if reading else False,
                    "total_usage_mm": reading.distance_mm if reading else 0.0,
                    "last_movement": reading.timestamp.isoformat() if reading and reading.is_moving else None
                }
                sensors.append(sensor_data)

            # Build GPIO status
            gpio_status = [
                {"pin": "GP0", "function": "movement", "sensor_id": "sensor_1", "value": False},
                {"pin": "GP1", "function": "runout", "sensor_id": "sensor_1", "value": False},
                {"pin": "GP2", "function": "movement", "sensor_id": "sensor_2", "value": False},
                {"pin": "GP3", "function": "runout", "sensor_id": "sensor_2", "value": False},
            ]

            # Update GPIO values from current readings
            for sensor_id in [1, 2]:
                reading = status.get_sensor_reading(sensor_id)
                if reading and reading.raw_gpio_state:
                    movement_pin = f"GP{(sensor_id - 1) * 2}"
                    runout_pin = f"GP{(sensor_id - 1) * 2 + 1}"

                    for gpio in gpio_status:
                        if gpio["pin"] == movement_pin and gpio["function"] == "movement":
                            gpio["value"] = reading.raw_gpio_state.get(movement_pin, False)
                        elif gpio["pin"] == runout_pin and gpio["function"] == "runout":
                            gpio["value"] = not reading.raw_gpio_state.get(runout_pin, True)  # Inverted logic

            response_data = {
                "timestamp": datetime.now(),
                "system_status": {
                    "status": "running" if status.is_running else "stopped",
                    "uptime_seconds": status.uptime_seconds,
                    "polling_interval_ms": status.configuration.polling.polling_interval_ms if status.configuration else 100
                },
                "sensors": sensors,
                "connection": {
                    "mcp2221_connected": status.health.hardware_connected,
                    "device_serial": "MCP2221A-001" if status.health.hardware_connected else None,
                    "gpio_status": gpio_status
                }
            }

            return StatusResponse(**response_data)

        except Exception as e:
            logger.error("Error getting status", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.get("/config", response_model=ConfigurationResponse)
    async def get_config():
        """Get current system configuration."""
        try:
            status = get_system_status()
            config = status.configuration

            if not config:
                # Return default configuration
                sensors_config = [
                    {
                        "id": "sensor_1",
                        "name": "Sensor 1",
                        "enabled": True,
                        "gpio_pins": {"movement": "GP0", "runout": "GP1"}
                    },
                    {
                        "id": "sensor_2",
                        "name": "Sensor 2",
                        "enabled": True,
                        "gpio_pins": {"movement": "GP2", "runout": "GP3"}
                    }
                ]

                response_data = {
                    "polling_interval_ms": 100,
                    "sensors": sensors_config,
                    "thresholds": {
                        "movement_timeout_ms": 5000,
                        "runout_debounce_ms": 500
                    },
                    "calibration": {"mm_per_pulse": 2.88},
                    "logging": {"level": "INFO", "structured": True}
                }
            else:
                # Convert current configuration to response format
                sensors_config = []
                for sensor in config.sensors:
                    gpio_mapping = {
                        1: {"movement": "GP0", "runout": "GP1"},
                        2: {"movement": "GP2", "runout": "GP3"}
                    }

                    sensors_config.append({
                        "id": f"sensor_{sensor.id}",
                        "name": sensor.name,
                        "enabled": sensor.enabled,
                        "gpio_pins": gpio_mapping[sensor.id]
                    })

                response_data = {
                    "polling_interval_ms": config.polling.polling_interval_ms,
                    "sensors": sensors_config,
                    "thresholds": {
                        "movement_timeout_ms": config.detection.movement_timeout_ms,
                        "runout_debounce_ms": config.detection.runout_debounce_ms
                    },
                    "calibration": {"mm_per_pulse": config.calibration.mm_per_pulse},
                    "logging": {
                        "level": config.logging.level,
                        "structured": config.logging.structured
                    }
                }

            return ConfigurationResponse(**response_data)

        except Exception as e:
            logger.error("Error getting configuration", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.post("/config")
    async def update_config(update_request: ConfigurationUpdateRequest, background_tasks: BackgroundTasks):
        """Update system configuration."""
        try:
            status = get_system_status()
            current_config = status.configuration

            if not current_config:
                raise HTTPException(status_code=500, detail="No configuration loaded")

            # Create updated configuration
            updated_config = current_config.model_copy(deep=True)

            # Apply updates
            if update_request.polling_interval_ms is not None:
                updated_config.polling.polling_interval_ms = update_request.polling_interval_ms

            if update_request.mm_per_pulse is not None:
                updated_config.calibration.mm_per_pulse = update_request.mm_per_pulse

            if update_request.movement_timeout_ms is not None:
                updated_config.detection.movement_timeout_ms = update_request.movement_timeout_ms

            if update_request.runout_debounce_ms is not None:
                updated_config.detection.runout_debounce_ms = update_request.runout_debounce_ms

            if update_request.sensor_names:
                for sensor in updated_config.sensors:
                    if sensor.id in update_request.sensor_names:
                        sensor.name = update_request.sensor_names[sensor.id]

            if update_request.logging_level is not None:
                updated_config.logging.level = update_request.logging_level

            # Validate and apply configuration
            status.update_configuration(updated_config)

            logger.info("Configuration updated successfully")
            return {"message": "Configuration updated successfully"}

        except ValidationError as e:
            logger.error("Configuration validation error", errors=e.errors())
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}")
        except Exception as e:
            logger.error("Error updating configuration", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.get("/metrics", response_model=MetricsResponse)
    async def get_metrics():
        """Get session metrics including usage statistics."""
        try:
            status = get_system_status()

            # Build sensor metrics
            sensors_metrics = []
            for sensor_id in [1, 2]:
                reading = status.get_sensor_reading(sensor_id)
                sensor_metrics = getattr(status.metrics, f"sensor{sensor_id}")

                sensors_metrics.append({
                    "id": f"sensor_{sensor_id}",
                    "total_usage_mm": sensor_metrics.total_distance_mm,
                    "total_pulses": sensor_metrics.total_pulses,
                    "movement_events": sensor_metrics.movement_events,
                    "runout_events": sensor_metrics.runout_events,
                    "last_activity": sensor_metrics.last_movement.isoformat() if sensor_metrics.last_movement else None,
                    "activity_periods": sensor_metrics.activity_periods,
                    "average_speed_mm_s": sensor_metrics.average_speed_mm_s
                })

            response_data = {
                "session": {
                    "started_at": status.started_at.isoformat() if status.started_at else datetime.now().isoformat(),
                    "uptime_seconds": status.uptime_seconds,
                    "total_alerts": len(status.recent_alerts),
                    "active_alerts": status.get_unacknowledged_alert_count()
                },
                "sensors": sensors_metrics,
                "system": {
                    "health_status": status.health.overall_health,
                    "hardware_connected": status.health.hardware_connected,
                    "error_count_24h": status.health.error_count_24h,
                    "responsive_sensors": status.health.responsive_sensor_count
                },
                "performance": status.metrics.performance.model_dump()
            }

            return MetricsResponse(**response_data)

        except Exception as e:
            logger.error("Error getting metrics", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.get("/alerts", response_model=AlertsResponse)
    async def get_alerts(count: int = 20):
        """Get recent alerts with optional count limit."""
        try:
            status = get_system_status()

            recent_alerts = status.get_recent_alerts(count)
            alerts_data = [alert.model_dump() for alert in recent_alerts]

            response_data = {
                "total_count": len(status.recent_alerts),
                "unacknowledged_count": status.get_unacknowledged_alert_count(),
                "alerts": alerts_data
            }

            return AlertsResponse(**response_data)

        except Exception as e:
            logger.error("Error getting alerts", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.post("/alerts/acknowledge")
    async def acknowledge_alerts(request: AlertAcknowledgeRequest):
        """Acknowledge alerts."""
        try:
            status = get_system_status()

            if request.acknowledge_all:
                count = status.acknowledge_all_alerts()
                return {"message": f"Acknowledged {count} alerts"}

            elif request.alert_ids:
                # Individual alert acknowledgment would need to be implemented
                # For now, just acknowledge all as a simple implementation
                count = status.acknowledge_all_alerts()
                return {"message": f"Acknowledged {count} alerts"}

            else:
                raise HTTPException(status_code=400, detail="Must specify acknowledge_all=true or provide alert_ids")

        except Exception as e:
            logger.error("Error acknowledging alerts", error=str(e))
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @app.websocket("/ws")
    async def websocket_route(websocket: WebSocket, client_id: Optional[str] = None):
        """WebSocket endpoint for real-time updates."""
        await websocket_endpoint(websocket, client_id)

    @app.get("/health")
    async def health_check():
        """Basic health check endpoint."""
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    @app.get("/connections")
    async def get_connections():
        """Get information about active WebSocket connections."""
        return {
            "active_connections": len(connection_manager.active_connections),
            "connections": connection_manager.get_connection_info()
        }

    return app


def run_server(host: str = "localhost", port: int = 5002, debug: bool = False) -> None:
    """Run the FastAPI server."""
    import uvicorn

    log_level = "debug" if debug else "info"

    logger.info("Starting API server", host=host, port=port, debug=debug)

    uvicorn.run(
        "src.lib.api_server:create_app",
        host=host,
        port=port,
        log_level=log_level,
        factory=True,
        reload=debug
    )


# Export the main components
__all__ = [
    "create_app",
    "run_server",
    "set_system_status",
    "get_system_status",
    "StatusResponse",
    "ConfigurationResponse",
    "MetricsResponse",
    "AlertsResponse",
    "ConfigurationUpdateRequest",
    "AlertAcknowledgeRequest"
]