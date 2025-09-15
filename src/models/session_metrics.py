"""SessionMetrics data model for tracking usage statistics and calculations."""

from datetime import datetime, timedelta
from typing import Dict, Optional
from pydantic import BaseModel, Field, computed_field


class SensorMetrics(BaseModel):
    """Metrics for a single sensor during the session."""

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }

    sensor_id: int = Field(ge=1, le=2, description="Sensor identifier")
    total_pulses: int = Field(default=0, ge=0, description="Total pulse count")
    total_distance_mm: float = Field(default=0.0, ge=0.0, description="Total distance in mm")
    runout_events: int = Field(default=0, ge=0, description="Number of runout events")
    feeding_time_seconds: float = Field(default=0.0, ge=0.0, description="Active feeding time")
    last_activity: Optional[datetime] = Field(default=None, description="Last movement detected")

    @computed_field
    @property
    def total_distance_m(self) -> float:
        """Total distance in meters."""
        return round(self.total_distance_mm / 1000.0, 3)

    @computed_field
    @property
    def average_feed_rate_mm_min(self) -> float:
        """Average feed rate in mm/minute."""
        if self.feeding_time_seconds <= 0:
            return 0.0
        return round((self.total_distance_mm / self.feeding_time_seconds) * 60.0, 2)

    @computed_field
    @property
    def time_since_activity(self) -> Optional[float]:
        """Seconds since last activity."""
        if self.last_activity is None:
            return None
        return (datetime.now() - self.last_activity).total_seconds()

    def is_active(self, timeout_seconds: float = 300.0) -> bool:
        """Check if sensor has been active recently."""
        time_since = self.time_since_activity
        return time_since is not None and time_since < timeout_seconds


class SystemPerformance(BaseModel):
    """System performance metrics."""

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }

    polling_cycles: int = Field(default=0, ge=0, description="Total polling cycles")
    missed_polls: int = Field(default=0, ge=0, description="Missed polling cycles")
    average_poll_time_ms: float = Field(default=0.0, ge=0.0, description="Average poll time")
    max_poll_time_ms: float = Field(default=0.0, ge=0.0, description="Maximum poll time")
    api_requests: int = Field(default=0, ge=0, description="Total API requests served")
    errors_count: int = Field(default=0, ge=0, description="Total error count")

    @computed_field
    @property
    def poll_success_rate(self) -> float:
        """Polling success rate as percentage."""
        if self.polling_cycles == 0:
            return 100.0
        success_rate = ((self.polling_cycles - self.missed_polls) / self.polling_cycles) * 100.0
        return round(success_rate, 2)

    @computed_field
    @property
    def is_healthy(self) -> bool:
        """System health check."""
        return (
            self.poll_success_rate > 95.0 and
            self.average_poll_time_ms < 50.0 and
            self.errors_count == 0
        )


class SessionMetrics(BaseModel):
    """Complete session metrics and calculations."""

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            timedelta: lambda v: v.total_seconds()
        },
        "validate_assignment": True,
        "extra": "forbid"
    }

    # Session timing
    session_start: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    # Sensor metrics
    sensor1: SensorMetrics = Field(
        default_factory=lambda: SensorMetrics(sensor_id=1),
        description="Metrics for sensor 1"
    )
    sensor2: SensorMetrics = Field(
        default_factory=lambda: SensorMetrics(sensor_id=2),
        description="Metrics for sensor 2"
    )

    # System performance
    performance: SystemPerformance = Field(
        default_factory=SystemPerformance,
        description="System performance metrics"
    )

    @computed_field
    @property
    def session_duration(self) -> timedelta:
        """Total session duration."""
        return datetime.now() - self.session_start

    @computed_field
    @property
    def session_duration_hours(self) -> float:
        """Session duration in hours."""
        return round(self.session_duration.total_seconds() / 3600.0, 2)

    @computed_field
    @property
    def total_distance_mm(self) -> float:
        """Combined distance from both sensors."""
        return self.sensor1.total_distance_mm + self.sensor2.total_distance_mm

    @computed_field
    @property
    def total_distance_m(self) -> float:
        """Combined distance in meters."""
        return round(self.total_distance_mm / 1000.0, 3)

    @computed_field
    @property
    def total_pulses(self) -> int:
        """Combined pulse count from both sensors."""
        return self.sensor1.total_pulses + self.sensor2.total_pulses

    @computed_field
    @property
    def active_sensors(self) -> int:
        """Number of currently active sensors."""
        active_count = 0
        if self.sensor1.is_active():
            active_count += 1
        if self.sensor2.is_active():
            active_count += 1
        return active_count

    @computed_field
    @property
    def system_status(self) -> str:
        """Overall system status."""
        if not self.performance.is_healthy:
            return "error"
        elif self.active_sensors == 0:
            return "idle"
        elif self.active_sensors == 1:
            return "single"
        else:
            return "dual"

    def get_sensor_metrics(self, sensor_id: int) -> SensorMetrics:
        """Get metrics for specific sensor."""
        if sensor_id == 1:
            return self.sensor1
        elif sensor_id == 2:
            return self.sensor2
        else:
            raise ValueError("sensor_id must be 1 or 2")

    def update_sensor_metrics(
        self,
        sensor_id: int,
        pulses_delta: int = 0,
        distance_delta_mm: float = 0.0,
        feeding_time_delta: float = 0.0,
        runout_occurred: bool = False
    ) -> None:
        """Update metrics for a specific sensor."""
        sensor = self.get_sensor_metrics(sensor_id)

        if pulses_delta > 0:
            sensor.total_pulses += pulses_delta
            sensor.last_activity = datetime.now()

        if distance_delta_mm > 0.0:
            sensor.total_distance_mm += distance_delta_mm

        if feeding_time_delta > 0.0:
            sensor.feeding_time_seconds += feeding_time_delta

        if runout_occurred:
            sensor.runout_events += 1

        self.last_updated = datetime.now()

    def update_performance(
        self,
        poll_time_ms: float,
        missed_poll: bool = False,
        api_request: bool = False,
        error_occurred: bool = False
    ) -> None:
        """Update system performance metrics."""
        self.performance.polling_cycles += 1

        if missed_poll:
            self.performance.missed_polls += 1

        if api_request:
            self.performance.api_requests += 1

        if error_occurred:
            self.performance.errors_count += 1

        # Update average poll time
        current_avg = self.performance.average_poll_time_ms
        total_cycles = self.performance.polling_cycles
        self.performance.average_poll_time_ms = (
            (current_avg * (total_cycles - 1) + poll_time_ms) / total_cycles
        )

        # Update max poll time
        if poll_time_ms > self.performance.max_poll_time_ms:
            self.performance.max_poll_time_ms = poll_time_ms

        self.last_updated = datetime.now()

    def export_summary(self) -> Dict[str, any]:
        """Export session summary for reporting."""
        return {
            "session_hours": self.session_duration_hours,
            "total_distance_m": self.total_distance_m,
            "total_pulses": self.total_pulses,
            "active_sensors": self.active_sensors,
            "system_status": self.system_status,
            "sensor1_distance_m": self.sensor1.total_distance_m,
            "sensor2_distance_m": self.sensor2.total_distance_m,
            "poll_success_rate": self.performance.poll_success_rate,
            "system_healthy": self.performance.is_healthy
        }