"""Simple unit tests for services that don't require complex mocking."""

import pytest
from datetime import datetime

# Test just the models without service dependencies
from src.models import SensorReading, SessionMetrics, AlertEvent


class TestSensorReadingSimple:
    """Simple tests for SensorReading model."""

    def test_sensor_reading_creation(self):
        """Test creating a sensor reading."""
        reading = SensorReading(
            sensor_id=1,
            timestamp=datetime.now(),
            has_filament=True,
            is_moving=True,
            distance_mm=10.5,
            pulse_count=3
        )

        assert reading.sensor_id == 1
        assert reading.has_filament is True
        assert reading.is_moving is True
        assert reading.distance_mm == 10.5
        assert reading.pulse_count == 3
        assert reading.filament_status == "feeding"

    def test_sensor_reading_with_runout(self):
        """Test sensor reading indicating runout."""
        reading = SensorReading(
            sensor_id=2,
            has_filament=False,
            is_moving=False,
            distance_mm=0.0,
            pulse_count=0
        )

        assert reading.sensor_id == 2
        assert reading.timestamp is not None
        assert reading.has_filament is False
        assert reading.is_moving is False
        assert reading.distance_mm == 0.0
        assert reading.pulse_count == 0
        assert reading.filament_status == "runout"


class TestSessionMetricsSimple:
    """Simple tests for SessionMetrics model."""

    def test_metrics_creation(self):
        """Test creating session metrics."""
        metrics = SessionMetrics()

        # Update sensor metrics
        metrics.update_sensor_metrics(
            sensor_id=1,
            pulses_delta=35,
            distance_delta_mm=100.5,
            feeding_time_delta=60.0
        )
        metrics.update_sensor_metrics(
            sensor_id=2,
            pulses_delta=70,
            distance_delta_mm=200.75,
            feeding_time_delta=120.0,
            runout_occurred=True
        )

        assert metrics.sensor1.total_distance_mm == 100.5
        assert metrics.sensor2.total_distance_mm == 200.75
        assert metrics.sensor1.total_pulses == 35
        assert metrics.sensor2.total_pulses == 70
        assert metrics.sensor2.runout_events == 1

    def test_metrics_defaults(self):
        """Test session metrics with defaults."""
        metrics = SessionMetrics()

        assert metrics.session_start is not None
        assert metrics.sensor1.total_distance_mm == 0.0
        assert metrics.sensor2.total_distance_mm == 0.0
        assert metrics.sensor1.total_pulses == 0
        assert metrics.sensor2.total_pulses == 0
        assert metrics.total_distance_mm == 0.0

    def test_total_distance_calculation(self):
        """Test total distance calculation."""
        metrics = SessionMetrics()
        metrics.sensor1.total_distance_mm = 100.0
        metrics.sensor2.total_distance_mm = 150.0

        assert metrics.total_distance_mm == 250.0
        assert metrics.total_distance_m == 0.25


class TestAlertEventSimple:
    """Simple tests for AlertEvent model."""

    def test_alert_creation(self):
        """Test creating an alert event."""
        from src.models.alert_event import AlertType, AlertSeverity

        alert = AlertEvent(
            alert_type=AlertType.RUNOUT_DETECTED,
            severity=AlertSeverity.CRITICAL,
            message="Filament runout detected on sensor 1"
        )

        assert alert.alert_type == "runout_detected"
        assert alert.severity == "critical"
        assert alert.message == "Filament runout detected on sensor 1"
        assert alert.timestamp is not None

    def test_alert_with_sensor_context(self):
        """Test alert event with sensor context."""
        from src.models.alert_event import AlertType, AlertSeverity

        alert = AlertEvent(
            alert_type=AlertType.MOVEMENT_STARTED,
            severity=AlertSeverity.INFO,
            message="Filament movement started",
            sensor_id=1
        )

        assert alert.alert_type == "movement_started"
        assert alert.severity == "info"
        assert alert.sensor_id == 1