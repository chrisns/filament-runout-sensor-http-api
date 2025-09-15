"""DataAggregator service for calculating metrics and aggregating sensor data."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import statistics
from collections import deque
import threading

import structlog

from ..models import (
    SystemStatus,
    SensorReading,
    SessionMetrics,
    AlertEvent,
    AlertType,
    AlertSeverity
)


logger = structlog.get_logger(__name__)


class SensorDataWindow:
    """Rolling window of sensor data for statistical analysis."""

    def __init__(self, window_minutes: int = 60):
        """Initialize data window."""
        self.window_minutes = window_minutes
        self.readings: deque = deque()
        self._lock = threading.Lock()

    def add_reading(self, reading: SensorReading) -> None:
        """Add a new sensor reading to the window."""
        with self._lock:
            self.readings.append(reading)
            self._cleanup_old_readings()

    def _cleanup_old_readings(self) -> None:
        """Remove readings older than the window."""
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)

        while self.readings and self.readings[0].timestamp < cutoff_time:
            self.readings.popleft()

    def get_readings(self, minutes: Optional[int] = None) -> List[SensorReading]:
        """Get readings from the specified time window."""
        with self._lock:
            if not minutes:
                return list(self.readings)

            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            return [r for r in self.readings if r.timestamp >= cutoff_time]

    def get_movement_periods(self, minutes: int = 60) -> List[Tuple[datetime, datetime]]:
        """Get periods of continuous movement within the time window."""
        readings = self.get_readings(minutes)
        if not readings:
            return []

        periods = []
        current_start = None

        for reading in readings:
            if reading.is_moving and current_start is None:
                current_start = reading.timestamp
            elif not reading.is_moving and current_start is not None:
                periods.append((current_start, reading.timestamp))
                current_start = None

        # Handle ongoing movement at end of window
        if current_start is not None:
            periods.append((current_start, datetime.now()))

        return periods

    def calculate_average_speed(self, minutes: int = 60) -> float:
        """Calculate average movement speed over the time window."""
        readings = self.get_readings(minutes)
        moving_readings = [r for r in readings if r.is_moving]

        if len(moving_readings) < 2:
            return 0.0

        # Calculate speed between consecutive moving readings
        speeds = []
        for i in range(1, len(moving_readings)):
            curr = moving_readings[i]
            prev = moving_readings[i - 1]

            time_diff = (curr.timestamp - prev.timestamp).total_seconds()
            distance_diff = curr.distance_mm - prev.distance_mm

            if time_diff > 0 and distance_diff > 0:
                speed_mm_s = distance_diff / time_diff
                speeds.append(speed_mm_s)

        return statistics.mean(speeds) if speeds else 0.0


class DataAggregator:
    """Service for calculating metrics and aggregating sensor data."""

    def __init__(self, system_status: Optional[SystemStatus] = None):
        """Initialize the data aggregator."""
        self.system_status = system_status or SystemStatus.get_instance()

        # Data windows for each sensor
        self.sensor_windows: Dict[int, SensorDataWindow] = {
            1: SensorDataWindow(window_minutes=120),  # 2-hour window
            2: SensorDataWindow(window_minutes=120)
        }

        # Aggregation state
        self.is_running = False
        self._aggregation_task: Optional[asyncio.Task] = None
        self.aggregation_interval_seconds = 30  # Aggregate every 30 seconds

        # Performance tracking
        self.last_aggregation_duration_ms = 0.0
        self.aggregation_count = 0

    async def start_aggregation(self) -> None:
        """Start the data aggregation service."""
        if self.is_running:
            logger.warning("Data aggregator already running")
            return

        logger.info("Starting data aggregator")

        self.is_running = True
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())

        logger.info("Data aggregator started",
                   aggregation_interval=self.aggregation_interval_seconds)

    async def stop_aggregation(self) -> None:
        """Stop the data aggregation service."""
        if not self.is_running:
            logger.warning("Data aggregator not running")
            return

        logger.info("Stopping data aggregator")

        self.is_running = False

        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass
            self._aggregation_task = None

        logger.info("Data aggregator stopped")

    def add_sensor_reading(self, reading: SensorReading) -> None:
        """Add a new sensor reading to the aggregation windows."""
        if reading.sensor_id in self.sensor_windows:
            self.sensor_windows[reading.sensor_id].add_reading(reading)

    def calculate_session_metrics(self) -> SessionMetrics:
        """Calculate current session metrics."""
        try:
            # Get current metrics object
            metrics = self.system_status.metrics

            # Update sensor-specific metrics
            for sensor_id in [1, 2]:
                self._update_sensor_metrics(sensor_id)

            # Update performance metrics
            self._update_performance_metrics()

            # Update system-wide metrics
            self._update_system_metrics()

            return metrics

        except Exception as e:
            logger.error("Error calculating session metrics", error=str(e))
            return SessionMetrics()

    def _update_sensor_metrics(self, sensor_id: int) -> None:
        """Update metrics for a specific sensor."""
        try:
            sensor_metrics = getattr(self.system_status.metrics, f"sensor{sensor_id}")
            window = self.sensor_windows[sensor_id]

            # Get recent readings
            recent_readings = window.get_readings(minutes=60)
            all_readings = window.get_readings()

            if not recent_readings:
                return

            # Update basic statistics
            latest_reading = max(recent_readings, key=lambda r: r.timestamp)
            sensor_metrics.total_distance_mm = latest_reading.distance_mm
            sensor_metrics.total_pulses = latest_reading.pulse_count

            # Count events in recent window
            sensor_metrics.movement_events = len([r for r in recent_readings if r.is_moving])
            sensor_metrics.runout_events = len([r for r in recent_readings if not r.has_filament])

            # Update last movement time
            moving_readings = [r for r in recent_readings if r.is_moving]
            if moving_readings:
                sensor_metrics.last_movement = max(moving_readings, key=lambda r: r.timestamp).timestamp

            # Calculate activity periods
            movement_periods = window.get_movement_periods(minutes=60)
            sensor_metrics.activity_periods = len(movement_periods)

            # Calculate average speed
            sensor_metrics.average_speed_mm_s = window.calculate_average_speed(minutes=60)

            # Update usage rate (mm per hour)
            if len(all_readings) >= 2:
                earliest = min(all_readings, key=lambda r: r.timestamp)
                time_hours = (latest_reading.timestamp - earliest.timestamp).total_seconds() / 3600.0
                if time_hours > 0:
                    sensor_metrics.usage_rate_mm_h = latest_reading.distance_mm / time_hours

        except Exception as e:
            logger.error("Error updating sensor metrics", sensor_id=sensor_id, error=str(e))

    def _update_performance_metrics(self) -> None:
        """Update system performance metrics."""
        try:
            performance = self.system_status.metrics.performance

            # Update aggregation performance
            performance.last_aggregation_ms = self.last_aggregation_duration_ms
            performance.aggregation_count = self.aggregation_count

            # Calculate memory usage (simplified estimation)
            total_readings = sum(len(window.readings) for window in self.sensor_windows.values())
            estimated_memory_mb = (total_readings * 0.001) + 10  # Base overhead
            performance.estimated_memory_mb = estimated_memory_mb

            # Update data processing metrics
            performance.total_readings_processed = sum(
                getattr(self.system_status.metrics, f"sensor{i}").total_pulses
                for i in [1, 2]
            )

        except Exception as e:
            logger.error("Error updating performance metrics", error=str(e))

    def _update_system_metrics(self) -> None:
        """Update system-wide aggregated metrics."""
        try:
            # Calculate total system distance
            total_distance_mm = sum(
                getattr(self.system_status.metrics, f"sensor{i}").total_distance_mm
                for i in [1, 2]
            )

            # Update system metrics
            self.system_status.metrics.total_distance_m = total_distance_mm / 1000.0
            self.system_status.metrics.session_duration_hours = self.system_status.uptime_hours

            # Calculate efficiency metrics
            if self.system_status.uptime_hours > 0:
                self.system_status.metrics.avg_usage_rate_mm_h = (
                    total_distance_mm / self.system_status.uptime_hours
                )

        except Exception as e:
            logger.error("Error updating system metrics", error=str(e))

    async def _aggregation_loop(self) -> None:
        """Main aggregation loop."""
        logger.info("Data aggregation loop started")

        while self.is_running:
            try:
                start_time = datetime.now()

                # Perform aggregation
                await self._perform_aggregation()

                # Track performance
                duration = (datetime.now() - start_time).total_seconds() * 1000
                self.last_aggregation_duration_ms = duration
                self.aggregation_count += 1

                # Sleep until next aggregation
                await asyncio.sleep(self.aggregation_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in aggregation loop", error=str(e))
                await asyncio.sleep(5.0)  # Back off on error

        logger.info("Data aggregation loop stopped")

    async def _perform_aggregation(self) -> None:
        """Perform data aggregation and metric calculation."""
        try:
            # Calculate updated metrics
            self.calculate_session_metrics()

            # Check for metric-based alerts
            await self._check_metric_alerts()

            # Log aggregation status periodically
            if self.aggregation_count % 20 == 0:  # Every 10 minutes at 30s intervals
                logger.debug("Data aggregation completed",
                           aggregation_count=self.aggregation_count,
                           duration_ms=self.last_aggregation_duration_ms,
                           total_distance_m=self.system_status.metrics.total_distance_m)

        except Exception as e:
            logger.error("Error performing aggregation", error=str(e))

    async def _check_metric_alerts(self) -> None:
        """Check metrics for alert conditions."""
        try:
            # Check for high usage rates
            for sensor_id in [1, 2]:
                sensor_metrics = getattr(self.system_status.metrics, f"sensor{sensor_id}")

                # Alert on very high speed (potential issue)
                if sensor_metrics.average_speed_mm_s > 50.0:  # 50 mm/s = 180 mm/min
                    self.system_status.add_alert(AlertEvent(
                        alert_type=AlertType.SENSOR_MOVEMENT,
                        severity=AlertSeverity.WARNING,
                        message=f"High filament speed detected on sensor {sensor_id}: "
                               f"{sensor_metrics.average_speed_mm_s:.1f} mm/s",
                        sensor_id=sensor_id,
                        metadata={"speed_mm_s": sensor_metrics.average_speed_mm_s}
                    ))

                # Alert on no movement for extended period (if filament present)
                current_reading = self.system_status.get_sensor_reading(sensor_id)
                if (current_reading and
                    current_reading.has_filament and
                    not current_reading.is_moving and
                    sensor_metrics.last_movement and
                    datetime.now() - sensor_metrics.last_movement > timedelta(hours=2)):

                    self.system_status.add_alert(AlertEvent(
                        alert_type=AlertType.SENSOR_INACTIVE,
                        severity=AlertSeverity.WARNING,
                        message=f"Sensor {sensor_id} inactive for {datetime.now() - sensor_metrics.last_movement}",
                        sensor_id=sensor_id
                    ))

            # Check system-wide metrics
            if self.system_status.metrics.total_distance_m > 1000.0:  # 1km
                if not hasattr(self, '_distance_milestone_1km'):
                    self._distance_milestone_1km = True
                    self.system_status.add_alert(AlertEvent(
                        alert_type=AlertType.SYSTEM_MILESTONE,
                        severity=AlertSeverity.INFO,
                        message=f"Milestone reached: {self.system_status.metrics.total_distance_m:.1f}m total filament processed",
                        metadata={"milestone_type": "distance", "value": self.system_status.metrics.total_distance_m}
                    ))

        except Exception as e:
            logger.error("Error checking metric alerts", error=str(e))

    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get aggregation performance statistics."""
        return {
            "is_running": self.is_running,
            "aggregation_interval_seconds": self.aggregation_interval_seconds,
            "last_aggregation_duration_ms": self.last_aggregation_duration_ms,
            "aggregation_count": self.aggregation_count,
            "sensor_windows": {
                sensor_id: len(window.readings)
                for sensor_id, window in self.sensor_windows.items()
            },
            "estimated_memory_mb": self.system_status.metrics.performance.estimated_memory_mb
        }

    def export_historical_data(self, sensor_id: Optional[int] = None,
                             minutes: int = 60) -> Dict[str, Any]:
        """Export historical sensor data for analysis."""
        try:
            if sensor_id:
                if sensor_id in self.sensor_windows:
                    readings = self.sensor_windows[sensor_id].get_readings(minutes)
                    return {
                        "sensor_id": sensor_id,
                        "readings": [reading.model_dump() for reading in readings],
                        "count": len(readings)
                    }
                else:
                    return {"error": f"Invalid sensor_id: {sensor_id}"}
            else:
                # Export all sensors
                data = {}
                for sid, window in self.sensor_windows.items():
                    readings = window.get_readings(minutes)
                    data[f"sensor_{sid}"] = {
                        "readings": [reading.model_dump() for reading in readings],
                        "count": len(readings)
                    }
                return data

        except Exception as e:
            logger.error("Error exporting historical data", error=str(e))
            return {"error": str(e)}


# Export the main component
__all__ = ["DataAggregator", "SensorDataWindow"]