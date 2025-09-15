"""AlertEvent data model for system notifications and events."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class AlertType(str, Enum):
    """Types of alert events."""

    # Sensor events
    RUNOUT_DETECTED = "runout_detected"
    FILAMENT_LOADED = "filament_loaded"
    MOVEMENT_STARTED = "movement_started"
    MOVEMENT_STOPPED = "movement_stopped"
    SENSOR_DISCONNECTED = "sensor_disconnected"
    SENSOR_RECONNECTED = "sensor_reconnected"

    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    CONFIGURATION_CHANGED = "configuration_changed"
    HARDWARE_ERROR = "hardware_error"
    POLLING_ERROR = "polling_error"
    API_ERROR = "api_error"

    # Performance events
    HIGH_POLL_TIME = "high_poll_time"
    MISSED_POLLS = "missed_polls"
    MEMORY_WARNING = "memory_warning"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertEvent(BaseModel):
    """Individual alert event with validation and metadata."""

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()},
        "validate_assignment": True,
        "extra": "forbid",
        "use_enum_values": True
    }

    # Core event data
    timestamp: datetime = Field(default_factory=datetime.now)
    alert_type: AlertType = Field(description="Type of alert event")
    severity: AlertSeverity = Field(description="Alert severity level")
    message: str = Field(min_length=1, max_length=500, description="Alert message")

    # Optional context
    sensor_id: Optional[int] = Field(
        default=None,
        ge=1,
        le=2,
        description="Related sensor ID if applicable"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional event details"
    )

    # Event tracking
    acknowledged: bool = Field(default=False, description="Alert acknowledged by user")
    acknowledged_at: Optional[datetime] = Field(
        default=None,
        description="When alert was acknowledged"
    )

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate and clean message text."""
        return v.strip()

    @field_validator('sensor_id')
    @classmethod
    def validate_sensor_id(cls, v: Optional[int]) -> Optional[int]:
        """Validate sensor ID if provided."""
        if v is not None and v not in [1, 2]:
            raise ValueError("sensor_id must be 1 or 2 if provided")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-init validation."""
        # Sensor-related alerts should have sensor_id
        sensor_alerts = {
            AlertType.RUNOUT_DETECTED,
            AlertType.FILAMENT_LOADED,
            AlertType.MOVEMENT_STARTED,
            AlertType.MOVEMENT_STOPPED,
            AlertType.SENSOR_DISCONNECTED,
            AlertType.SENSOR_RECONNECTED
        }

        if self.alert_type in sensor_alerts and self.sensor_id is None:
            raise ValueError(f"{self.alert_type} requires sensor_id")

    @property
    def age_seconds(self) -> float:
        """Age of this alert in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    @property
    def is_recent(self) -> bool:
        """Check if alert occurred in the last 60 seconds."""
        return self.age_seconds < 60.0

    @property
    def requires_attention(self) -> bool:
        """Check if alert requires user attention."""
        return (
            self.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] and
            not self.acknowledged
        )

    def acknowledge(self) -> None:
        """Mark alert as acknowledged."""
        if not self.acknowledged:
            self.acknowledged = True
            self.acknowledged_at = datetime.now()

    @classmethod
    def create_runout_alert(
        cls,
        sensor_id: int,
        details: Optional[Dict[str, Any]] = None
    ) -> "AlertEvent":
        """Create a filament runout alert."""
        return cls(
            alert_type=AlertType.RUNOUT_DETECTED,
            severity=AlertSeverity.WARNING,
            message=f"Filament runout detected on sensor {sensor_id}",
            sensor_id=sensor_id,
            details=details or {}
        )

    @classmethod
    def create_hardware_error(
        cls,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> "AlertEvent":
        """Create a hardware error alert."""
        return cls(
            alert_type=AlertType.HARDWARE_ERROR,
            severity=AlertSeverity.ERROR,
            message=f"Hardware error: {message}",
            details=details or {}
        )

    @classmethod
    def create_system_startup(cls) -> "AlertEvent":
        """Create a system startup alert."""
        return cls(
            alert_type=AlertType.SYSTEM_STARTED,
            severity=AlertSeverity.INFO,
            message="Filament sensor monitoring system started"
        )

    @classmethod
    def create_configuration_change(
        cls,
        change_description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> "AlertEvent":
        """Create a configuration change alert."""
        return cls(
            alert_type=AlertType.CONFIGURATION_CHANGED,
            severity=AlertSeverity.INFO,
            message=f"Configuration updated: {change_description}",
            details=details or {}
        )

    @classmethod
    def create_performance_warning(
        cls,
        metric: str,
        value: float,
        threshold: float,
        details: Optional[Dict[str, Any]] = None
    ) -> "AlertEvent":
        """Create a performance warning alert."""
        alert_type = AlertType.HIGH_POLL_TIME if "poll" in metric.lower() else AlertType.MISSED_POLLS

        return cls(
            alert_type=alert_type,
            severity=AlertSeverity.WARNING,
            message=f"Performance issue: {metric} = {value} (threshold: {threshold})",
            details=details or {"metric": metric, "value": value, "threshold": threshold}
        )

    def to_log_entry(self) -> str:
        """Convert alert to structured log entry."""
        sensor_info = f" [Sensor {self.sensor_id}]" if self.sensor_id else ""
        return f"[{self.severity.upper()}]{sensor_info} {self.alert_type}: {self.message}"

    def __str__(self) -> str:
        """String representation for display."""
        timestamp_str = self.timestamp.strftime("%H:%M:%S")
        sensor_info = f" (Sensor {self.sensor_id})" if self.sensor_id else ""
        ack_info = " [ACK]" if self.acknowledged else ""
        return f"{timestamp_str} {self.severity.upper()}{sensor_info}: {self.message}{ack_info}"