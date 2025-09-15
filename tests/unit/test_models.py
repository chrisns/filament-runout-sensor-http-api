"""Unit tests for data models."""

import pytest
from datetime import datetime
from src.models import (
    SensorReading,
    SensorConfiguration,
    SystemStatus,
    SessionMetrics,
    AlertEvent
)


class TestSensorReading:
    """Test SensorReading model."""

    def test_sensor_reading_creation(self):
        """Test creating a sensor reading."""
        reading = SensorReading(
            sensor_id=1,
            timestamp=datetime.now(),
            runout_detected=False,
            movement_pulse=True,
            filament_used_mm=10.5
        )

        assert reading.sensor_id == 1
        assert reading.runout_detected is False
        assert reading.movement_pulse is True
        assert reading.filament_used_mm == 10.5

    def test_sensor_reading_defaults(self):
        """Test sensor reading with default values."""
        reading = SensorReading(sensor_id=2)

        assert reading.sensor_id == 2
        assert reading.timestamp is not None
        assert reading.runout_detected is False
        assert reading.movement_pulse is False
        assert reading.filament_used_mm == 0.0


class TestSensorConfiguration:
    """Test SensorConfiguration model."""

    def test_default_configuration(self):
        """Test default sensor configuration."""
        config = SensorConfiguration()

        assert config.polling_interval_ms == 100
        assert config.mm_per_pulse == 2.88
        assert config.sensor_1_enabled is True
        assert config.sensor_2_enabled is True
        assert config.debug_mode is False

    def test_custom_configuration(self):
        """Test custom sensor configuration."""
        config = SensorConfiguration(
            polling_interval_ms=50,
            mm_per_pulse=3.0,
            sensor_1_enabled=False,
            debug_mode=True
        )

        assert config.polling_interval_ms == 50
        assert config.mm_per_pulse == 3.0
        assert config.sensor_1_enabled is False
        assert config.debug_mode is True

    def test_configuration_validation(self):
        """Test configuration validation."""
        # Test minimum polling interval
        with pytest.raises(ValueError):
            SensorConfiguration(polling_interval_ms=5)

        # Test negative mm_per_pulse
        with pytest.raises(ValueError):
            SensorConfiguration(mm_per_pulse=-1.0)


class TestSystemStatus:
    """Test SystemStatus singleton model."""

    def test_singleton_pattern(self):
        """Test that SystemStatus is a singleton."""
        status1 = SystemStatus.get_instance()
        status2 = SystemStatus.get_instance()

        assert status1 is status2

    def test_status_fields(self):
        """Test system status fields."""
        status = SystemStatus.get_instance()
        status.reset()

        assert status.hardware_connected is False
        assert status.api_server_running is False
        assert status.display_running is False
        assert status.monitoring_active is False
        assert status.startup_time is not None

    def test_status_update(self):
        """Test updating system status."""
        status = SystemStatus.get_instance()
        status.reset()

        status.hardware_connected = True
        status.api_server_running = True

        assert status.hardware_connected is True
        assert status.api_server_running is True


class TestSessionMetrics:
    """Test SessionMetrics model."""

    def test_metrics_creation(self):
        """Test creating session metrics."""
        metrics = SessionMetrics(
            session_id="test-session",
            start_time=datetime.now(),
            sensor_1_total_mm=100.5,
            sensor_2_total_mm=200.75,
            sensor_1_pulse_count=35,
            sensor_2_pulse_count=70
        )

        assert metrics.session_id == "test-session"
        assert metrics.sensor_1_total_mm == 100.5
        assert metrics.sensor_2_total_mm == 200.75
        assert metrics.sensor_1_pulse_count == 35
        assert metrics.sensor_2_pulse_count == 70

    def test_metrics_defaults(self):
        """Test session metrics with defaults."""
        metrics = SessionMetrics()

        assert metrics.session_id is not None
        assert metrics.start_time is not None
        assert metrics.sensor_1_total_mm == 0.0
        assert metrics.sensor_2_total_mm == 0.0
        assert metrics.sensor_1_pulse_count == 0
        assert metrics.sensor_2_pulse_count == 0
        assert metrics.runout_events == []


class TestAlertEvent:
    """Test AlertEvent model."""

    def test_alert_creation(self):
        """Test creating an alert event."""
        alert = AlertEvent(
            sensor_id=1,
            alert_type="runout",
            message="Filament runout detected on sensor 1",
            severity="critical"
        )

        assert alert.sensor_id == 1
        assert alert.alert_type == "runout"
        assert alert.message == "Filament runout detected on sensor 1"
        assert alert.severity == "critical"
        assert alert.timestamp is not None

    def test_alert_defaults(self):
        """Test alert event with defaults."""
        alert = AlertEvent(
            sensor_id=2,
            alert_type="warning",
            message="Low filament"
        )

        assert alert.sensor_id == 2
        assert alert.alert_type == "warning"
        assert alert.severity == "warning"
        assert alert.acknowledged is False