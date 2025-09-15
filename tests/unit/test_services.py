"""Unit tests for services."""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import asyncio

from src.services import SensorMonitor, DataAggregator, SessionStorage
from src.models import SensorReading, SessionMetrics, AlertEvent


class TestSensorMonitor:
    """Test SensorMonitor service."""

    @pytest.fixture
    def mock_mcp2221(self):
        """Create a mock MCP2221 device."""
        with patch('src.services.sensor_monitor.MCP2221Manager') as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_monitor_initialization(self, mock_mcp2221):
        """Test sensor monitor initialization."""
        monitor = SensorMonitor(demo_mode=True)

        assert monitor.demo_mode is True
        assert monitor.is_monitoring is False
        assert monitor.sensor_states == {1: {}, 2: {}}

    @pytest.mark.asyncio
    async def test_start_monitoring(self, mock_mcp2221):
        """Test starting sensor monitoring."""
        monitor = SensorMonitor(demo_mode=True)
        monitor.polling_interval_ms = 10  # Fast polling for test

        # Start monitoring in background
        task = asyncio.create_task(monitor.start_monitoring())

        # Let it run briefly
        await asyncio.sleep(0.05)

        assert monitor.is_monitoring is True

        # Stop monitoring
        await monitor.stop_monitoring()

        # Wait for task to complete
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()

    @pytest.mark.asyncio
    async def test_demo_mode_readings(self, mock_mcp2221):
        """Test demo mode generates readings."""
        monitor = SensorMonitor(demo_mode=True)

        reading = await monitor._generate_demo_reading(1)

        assert isinstance(reading, SensorReading)
        assert reading.sensor_id == 1
        assert isinstance(reading.runout_detected, bool)
        assert isinstance(reading.movement_pulse, bool)

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, mock_mcp2221):
        """Test stopping sensor monitoring."""
        monitor = SensorMonitor(demo_mode=True)
        monitor.is_monitoring = True

        await monitor.stop_monitoring()

        assert monitor.is_monitoring is False


class TestDataAggregator:
    """Test DataAggregator service."""

    def test_aggregator_initialization(self):
        """Test data aggregator initialization."""
        aggregator = DataAggregator()

        assert aggregator.session_metrics is not None
        assert aggregator.session_metrics.sensor_1_total_mm == 0.0
        assert aggregator.session_metrics.sensor_2_total_mm == 0.0

    def test_process_reading(self):
        """Test processing sensor readings."""
        aggregator = DataAggregator()

        # Create a reading with movement
        reading = SensorReading(
            sensor_id=1,
            movement_pulse=True,
            filament_used_mm=2.88
        )

        aggregator.process_reading(reading)

        assert aggregator.session_metrics.sensor_1_total_mm == 2.88
        assert aggregator.session_metrics.sensor_1_pulse_count == 1

    def test_process_runout_event(self):
        """Test processing runout events."""
        aggregator = DataAggregator()

        # Create a reading with runout
        reading = SensorReading(
            sensor_id=2,
            runout_detected=True
        )

        alerts = aggregator.process_reading(reading)

        assert len(alerts) == 1
        assert alerts[0].sensor_id == 2
        assert alerts[0].alert_type == "runout"
        assert len(aggregator.session_metrics.runout_events) == 1

    def test_get_current_metrics(self):
        """Test getting current metrics."""
        aggregator = DataAggregator()

        # Process some readings
        for i in range(5):
            reading = SensorReading(
                sensor_id=1,
                movement_pulse=True,
                filament_used_mm=2.88
            )
            aggregator.process_reading(reading)

        metrics = aggregator.get_current_metrics()

        assert metrics.sensor_1_total_mm == 14.4  # 5 * 2.88
        assert metrics.sensor_1_pulse_count == 5

    def test_reset_session(self):
        """Test resetting session metrics."""
        aggregator = DataAggregator()

        # Add some data
        reading = SensorReading(sensor_id=1, movement_pulse=True, filament_used_mm=10.0)
        aggregator.process_reading(reading)

        # Reset
        aggregator.reset_session()

        assert aggregator.session_metrics.sensor_1_total_mm == 0.0
        assert aggregator.session_metrics.sensor_1_pulse_count == 0
        assert len(aggregator.session_metrics.runout_events) == 0


class TestSessionStorage:
    """Test SessionStorage service."""

    def test_storage_initialization(self):
        """Test session storage initialization."""
        storage = SessionStorage(in_memory=True)

        assert storage.in_memory is True
        assert storage.readings_buffer == []
        assert storage.alerts_buffer == []

    def test_store_reading(self):
        """Test storing sensor readings."""
        storage = SessionStorage(in_memory=True)

        reading = SensorReading(sensor_id=1)
        storage.store_reading(reading)

        assert len(storage.readings_buffer) == 1
        assert storage.readings_buffer[0] == reading

    def test_store_alert(self):
        """Test storing alert events."""
        storage = SessionStorage(in_memory=True)

        alert = AlertEvent(
            sensor_id=1,
            alert_type="runout",
            message="Test alert"
        )
        storage.store_alert(alert)

        assert len(storage.alerts_buffer) == 1
        assert storage.alerts_buffer[0] == alert

    def test_get_recent_readings(self):
        """Test getting recent readings."""
        storage = SessionStorage(in_memory=True)

        # Store multiple readings
        for i in range(10):
            reading = SensorReading(sensor_id=1)
            storage.store_reading(reading)

        recent = storage.get_recent_readings(limit=5)

        assert len(recent) == 5

    def test_get_alerts(self):
        """Test getting alerts with filters."""
        storage = SessionStorage(in_memory=True)

        # Store different types of alerts
        alert1 = AlertEvent(sensor_id=1, alert_type="runout", message="Runout")
        alert2 = AlertEvent(sensor_id=2, alert_type="warning", message="Warning")
        alert3 = AlertEvent(sensor_id=1, alert_type="info", message="Info")

        storage.store_alert(alert1)
        storage.store_alert(alert2)
        storage.store_alert(alert3)

        # Get all alerts
        all_alerts = storage.get_alerts()
        assert len(all_alerts) == 3

        # Get alerts for sensor 1
        sensor1_alerts = storage.get_alerts(sensor_id=1)
        assert len(sensor1_alerts) == 2

        # Get runout alerts only
        runout_alerts = storage.get_alerts(alert_type="runout")
        assert len(runout_alerts) == 1

    def test_clear_session(self):
        """Test clearing session data."""
        storage = SessionStorage(in_memory=True)

        # Add some data
        storage.store_reading(SensorReading(sensor_id=1))
        storage.store_alert(AlertEvent(sensor_id=1, alert_type="test", message="Test"))

        # Clear
        storage.clear_session()

        assert len(storage.readings_buffer) == 0
        assert len(storage.alerts_buffer) == 0