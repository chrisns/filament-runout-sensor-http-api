"""SensorReading data model for individual sensor measurements."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, computed_field


class SensorReading(BaseModel):
    """Individual sensor reading with validation and computed properties."""

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()},
        "validate_assignment": True,
        "extra": "forbid"
    }

    # Core reading data
    timestamp: datetime = Field(default_factory=datetime.now)
    sensor_id: int = Field(ge=1, le=2, description="Sensor identifier (1 or 2)")
    has_filament: bool = Field(description="True if filament detected")
    is_moving: bool = Field(description="True if filament movement detected")
    pulse_count: int = Field(ge=0, description="Total pulse count since start")
    distance_mm: float = Field(ge=0.0, description="Calculated distance in millimeters")

    # Optional metadata
    raw_gpio_state: Optional[dict[str, bool]] = Field(
        default=None,
        description="Raw GPIO pin states for debugging"
    )

    @field_validator('sensor_id')
    @classmethod
    def validate_sensor_id(cls, v: int) -> int:
        """Validate sensor ID is 1 or 2."""
        if v not in [1, 2]:
            raise ValueError("sensor_id must be 1 or 2")
        return v

    @field_validator('distance_mm')
    @classmethod
    def validate_distance(cls, v: float) -> float:
        """Validate distance is non-negative and reasonable."""
        if v < 0:
            raise ValueError("distance_mm cannot be negative")
        if v > 10000:  # 10 meters seems reasonable max
            raise ValueError("distance_mm exceeds reasonable maximum (10000mm)")
        return round(v, 3)  # Round to 3 decimal places

    @computed_field
    @property
    def filament_status(self) -> str:
        """Human-readable filament status."""
        if not self.has_filament:
            return "runout"
        elif self.is_moving:
            return "feeding"
        else:
            return "present"

    @computed_field
    @property
    def age_seconds(self) -> float:
        """Age of this reading in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    def is_stale(self, max_age_seconds: float = 1.0) -> bool:
        """Check if reading is stale based on age."""
        return self.age_seconds > max_age_seconds

    def __str__(self) -> str:
        """String representation for logging."""
        return (
            f"Sensor{self.sensor_id}: {self.filament_status} "
            f"({self.pulse_count}p, {self.distance_mm:.1f}mm)"
        )