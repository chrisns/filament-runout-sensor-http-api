"""SystemStatus singleton for overall system state management."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from threading import Lock
from pydantic import BaseModel, Field, computed_field

from .sensor_reading import SensorReading
from .sensor_configuration import SensorConfiguration
from .session_metrics import SessionMetrics
from .alert_event import AlertEvent, AlertType, AlertSeverity


class SystemHealth(BaseModel):
    """System health status."""

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }

    hardware_connected: bool = Field(default=False, description="MCP2221A hardware connected")
    sensors_responding: Dict[int, bool] = Field(
        default_factory=lambda: {1: False, 2: False},
        description="Sensor response status"
    )
    last_hardware_check: Optional[datetime] = Field(
        default=None,
        description="Last hardware connectivity check"
    )
    error_count_24h: int = Field(default=0, ge=0, description="Errors in last 24 hours")
    uptime_seconds: float = Field(default=0.0, ge=0.0, description="System uptime")

    @computed_field
    @property
    def overall_health(self) -> str:
        """Overall system health status."""
        if not self.hardware_connected:
            return "disconnected"
        elif self.error_count_24h > 10:
            return "degraded"
        elif not any(self.sensors_responding.values()):
            return "no_sensors"
        elif all(self.sensors_responding.values()):
            return "healthy"
        else:
            return "partial"

    @computed_field
    @property
    def responsive_sensor_count(self) -> int:
        """Number of responsive sensors."""
        return sum(self.sensors_responding.values())


class SystemStatus(BaseModel):
    """Singleton system status manager."""

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()},
        "validate_assignment": True,
        "extra": "forbid"
    }

    # System state
    is_running: bool = Field(default=False, description="System running state")
    started_at: Optional[datetime] = Field(default=None, description="System start time")
    last_update: datetime = Field(default_factory=datetime.now)

    # Current readings
    current_readings: Dict[int, Optional[SensorReading]] = Field(
        default_factory=lambda: {1: None, 2: None},
        description="Latest sensor readings"
    )

    # Configuration and metrics
    configuration: Optional[SensorConfiguration] = Field(
        default=None,
        description="Current system configuration"
    )
    metrics: SessionMetrics = Field(
        default_factory=SessionMetrics,
        description="Session metrics"
    )

    # System health
    health: SystemHealth = Field(
        default_factory=SystemHealth,
        description="System health status"
    )

    # Recent alerts (keep last 100)
    recent_alerts: List[AlertEvent] = Field(
        default_factory=list,
        description="Recent alert events"
    )

    # Class-level singleton management
    _instance: Optional['SystemStatus'] = None
    _lock: Lock = Lock()

    def __new__(cls) -> 'SystemStatus':
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'SystemStatus':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing."""
        with cls._lock:
            cls._instance = None

    @computed_field
    @property
    def uptime_seconds(self) -> float:
        """Current system uptime in seconds."""
        if self.started_at is None:
            return 0.0
        return (datetime.now() - self.started_at).total_seconds()

    @computed_field
    @property
    def uptime_hours(self) -> float:
        """Current system uptime in hours."""
        return round(self.uptime_seconds / 3600.0, 2)

    @computed_field
    @property
    def system_summary(self) -> Dict[str, Any]:
        """System summary for API responses."""
        return {
            "running": self.is_running,
            "uptime_hours": self.uptime_hours,
            "health": self.health.overall_health,
            "sensors_active": self.health.responsive_sensor_count,
            "total_distance_m": self.metrics.total_distance_m,
            "unacknowledged_alerts": self.get_unacknowledged_alert_count(),
            "last_update": self.last_update.isoformat()
        }

    def start_system(self, config: SensorConfiguration) -> None:
        """Start the monitoring system."""
        self.is_running = True
        self.started_at = datetime.now()
        self.configuration = config
        self.metrics = SessionMetrics()  # Reset metrics
        self.add_alert(AlertEvent.create_system_startup())
        self._update_timestamp()

    def stop_system(self) -> None:
        """Stop the monitoring system."""
        if self.is_running:
            self.add_alert(AlertEvent(
                alert_type=AlertType.SYSTEM_STOPPED,
                severity=AlertSeverity.INFO,
                message="Filament sensor monitoring system stopped"
            ))
        self.is_running = False
        self._update_timestamp()

    def update_sensor_reading(self, reading: SensorReading) -> None:
        """Update current sensor reading."""
        self.current_readings[reading.sensor_id] = reading
        self.health.sensors_responding[reading.sensor_id] = True
        self._update_timestamp()

    def update_hardware_status(self, connected: bool) -> None:
        """Update hardware connection status."""
        was_connected = self.health.hardware_connected
        self.health.hardware_connected = connected
        self.health.last_hardware_check = datetime.now()

        if was_connected and not connected:
            self.add_alert(AlertEvent.create_hardware_error("MCP2221A disconnected"))
        elif not was_connected and connected:
            self.add_alert(AlertEvent(
                alert_type=AlertType.SENSOR_RECONNECTED,
                severity=AlertSeverity.INFO,
                message="MCP2221A hardware reconnected"
            ))

        self._update_timestamp()

    def update_configuration(self, config: SensorConfiguration) -> None:
        """Update system configuration."""
        old_config = self.configuration
        self.configuration = config

        if old_config is not None:
            self.add_alert(AlertEvent.create_configuration_change(
                "System configuration updated",
                {"polling_ms": config.polling.polling_interval_ms}
            ))

        self._update_timestamp()

    def add_alert(self, alert: AlertEvent) -> None:
        """Add a new alert to the system."""
        self.recent_alerts.append(alert)

        # Keep only last 100 alerts
        if len(self.recent_alerts) > 100:
            self.recent_alerts = self.recent_alerts[-100:]

        # Update error count for health tracking
        if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            self.health.error_count_24h += 1

        self._update_timestamp()

    def get_sensor_reading(self, sensor_id: int) -> Optional[SensorReading]:
        """Get current reading for specific sensor."""
        if sensor_id not in [1, 2]:
            raise ValueError("sensor_id must be 1 or 2")
        return self.current_readings.get(sensor_id)

    def get_recent_alerts(self, count: int = 10) -> List[AlertEvent]:
        """Get recent alerts, most recent first."""
        return list(reversed(self.recent_alerts[-count:]))

    def get_unacknowledged_alerts(self) -> List[AlertEvent]:
        """Get all unacknowledged alerts."""
        return [alert for alert in self.recent_alerts if not alert.acknowledged]

    def get_unacknowledged_alert_count(self) -> int:
        """Count of unacknowledged alerts."""
        return len(self.get_unacknowledged_alerts())

    def acknowledge_all_alerts(self) -> int:
        """Acknowledge all unacknowledged alerts."""
        count = 0
        for alert in self.recent_alerts:
            if not alert.acknowledged:
                alert.acknowledge()
                count += 1

        if count > 0:
            self._update_timestamp()

        return count

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get detailed system diagnostics."""
        sensor1_reading = self.get_sensor_reading(1)
        sensor2_reading = self.get_sensor_reading(2)

        return {
            "system": {
                "running": self.is_running,
                "uptime_seconds": self.uptime_seconds,
                "health_status": self.health.overall_health,
                "hardware_connected": self.health.hardware_connected,
                "last_update": self.last_update.isoformat()
            },
            "sensors": {
                "sensor1": {
                    "responding": self.health.sensors_responding[1],
                    "current_reading": sensor1_reading.model_dump() if sensor1_reading else None,
                    "metrics": self.metrics.sensor1.model_dump()
                },
                "sensor2": {
                    "responding": self.health.sensors_responding[2],
                    "current_reading": sensor2_reading.model_dump() if sensor2_reading else None,
                    "metrics": self.metrics.sensor2.model_dump()
                }
            },
            "performance": self.metrics.performance.model_dump(),
            "alerts": {
                "total_count": len(self.recent_alerts),
                "unacknowledged_count": self.get_unacknowledged_alert_count(),
                "recent_alerts": [alert.model_dump() for alert in self.get_recent_alerts(5)]
            },
            "configuration": self.configuration.model_dump() if self.configuration else None
        }

    def _update_timestamp(self) -> None:
        """Update the last update timestamp."""
        self.last_update = datetime.now()

    def export_status(self) -> Dict[str, Any]:
        """Export complete status for API responses."""
        return {
            "system_summary": self.system_summary,
            "current_readings": {
                str(k): v.model_dump() if v else None
                for k, v in self.current_readings.items()
            },
            "session_metrics": self.metrics.export_summary(),
            "health": self.health.model_dump(),
            "recent_alerts": [alert.model_dump() for alert in self.get_recent_alerts()]
        }