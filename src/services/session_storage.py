"""SessionStorage service for SQLite-based session data management."""

import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import threading
from contextlib import contextmanager

import structlog

from ..models import (
    SensorReading,
    AlertEvent,
    SystemStatus,
    SessionMetrics
)


logger = structlog.get_logger(__name__)


class SessionStorage:
    """SQLite-based session storage for filament sensor data."""

    def __init__(self,
                 database_path: Optional[str] = None,
                 in_memory: bool = True,
                 max_retention_hours: int = 24):
        """Initialize session storage."""

        # Database configuration
        if in_memory:
            self.database_path = ":memory:"
        else:
            self.database_path = database_path or "filament_sensor_session.db"

        self.max_retention_hours = max_retention_hours
        self.connection: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

        # Background cleanup
        self.is_running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval_minutes = 30

        # Performance tracking
        self.query_count = 0
        self.insert_count = 0
        self.last_operation_duration_ms = 0.0

    async def initialize(self) -> None:
        """Initialize the database and create tables."""
        try:
            logger.info("Initializing session storage", database_path=self.database_path)

            # Create connection
            self.connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
                timeout=30.0
            )

            # Enable WAL mode for better concurrent access
            if self.database_path != ":memory:":
                self.connection.execute("PRAGMA journal_mode=WAL")

            # Create tables
            await self._create_tables()

            # Start background cleanup
            self.is_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

            logger.info("Session storage initialized")

        except Exception as e:
            logger.error("Failed to initialize session storage", error=str(e))
            raise

    async def close(self) -> None:
        """Close the database connection and cleanup."""
        logger.info("Closing session storage")

        # Stop background tasks
        self.is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self.connection:
            self.connection.close()
            self.connection = None

        logger.info("Session storage closed")

    @contextmanager
    def _get_cursor(self):
        """Get a database cursor with proper error handling."""
        if not self.connection:
            raise RuntimeError("Database not initialized")

        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error("Database operation failed", error=str(e))
            raise
        finally:
            cursor.close()

    async def _create_tables(self) -> None:
        """Create database tables for session data."""
        with self._lock:
            with self._get_cursor() as cursor:
                # Sensor readings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_readings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        sensor_id INTEGER NOT NULL,
                        has_filament BOOLEAN NOT NULL,
                        is_moving BOOLEAN NOT NULL,
                        pulse_count INTEGER NOT NULL,
                        distance_mm REAL NOT NULL,
                        raw_gpio_state TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Index for efficient queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp
                    ON sensor_readings (timestamp)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_id
                    ON sensor_readings (sensor_id, timestamp)
                """)

                # Alert events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alert_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        sensor_id INTEGER,
                        acknowledged BOOLEAN DEFAULT FALSE,
                        acknowledged_at TEXT,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_alert_events_timestamp
                    ON alert_events (timestamp)
                """)

                # System metrics snapshots table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metric_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        uptime_seconds REAL NOT NULL,
                        total_distance_m REAL NOT NULL,
                        sensor1_distance_mm REAL NOT NULL,
                        sensor2_distance_mm REAL NOT NULL,
                        sensor1_pulses INTEGER NOT NULL,
                        sensor2_pulses INTEGER NOT NULL,
                        hardware_connected BOOLEAN NOT NULL,
                        sensors_active INTEGER NOT NULL,
                        alert_count INTEGER NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metric_snapshots_timestamp
                    ON metric_snapshots (timestamp)
                """)

                # Performance tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        details TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                logger.info("Database tables created successfully")

    async def store_sensor_reading(self, reading: SensorReading) -> bool:
        """Store a sensor reading in the database."""
        try:
            start_time = datetime.now()

            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO sensor_readings
                        (timestamp, sensor_id, has_filament, is_moving, pulse_count, distance_mm, raw_gpio_state)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        reading.timestamp.isoformat(),
                        reading.sensor_id,
                        reading.has_filament,
                        reading.is_moving,
                        reading.pulse_count,
                        reading.distance_mm,
                        json.dumps(reading.raw_gpio_state) if reading.raw_gpio_state else None
                    ))

            # Track performance
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.last_operation_duration_ms = duration
            self.insert_count += 1

            return True

        except Exception as e:
            logger.error("Failed to store sensor reading", error=str(e))
            return False

    async def store_alert_event(self, alert: AlertEvent) -> bool:
        """Store an alert event in the database."""
        try:
            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO alert_events
                        (timestamp, alert_type, severity, message, sensor_id, acknowledged, acknowledged_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        alert.timestamp.isoformat(),
                        alert.alert_type.value,
                        alert.severity.value,
                        alert.message,
                        alert.sensor_id,
                        alert.acknowledged,
                        alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                        json.dumps(alert.metadata) if alert.metadata else None
                    ))

            self.insert_count += 1
            return True

        except Exception as e:
            logger.error("Failed to store alert event", error=str(e))
            return False

    async def store_metrics_snapshot(self, system_status: SystemStatus) -> bool:
        """Store a metrics snapshot in the database."""
        try:
            metrics = system_status.metrics

            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO metric_snapshots
                        (timestamp, uptime_seconds, total_distance_m,
                         sensor1_distance_mm, sensor2_distance_mm,
                         sensor1_pulses, sensor2_pulses,
                         hardware_connected, sensors_active, alert_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().isoformat(),
                        system_status.uptime_seconds,
                        metrics.total_distance_m,
                        metrics.sensor1.total_distance_mm,
                        metrics.sensor2.total_distance_mm,
                        metrics.sensor1.total_pulses,
                        metrics.sensor2.total_pulses,
                        system_status.health.hardware_connected,
                        system_status.health.responsive_sensor_count,
                        len(system_status.recent_alerts)
                    ))

            self.insert_count += 1
            return True

        except Exception as e:
            logger.error("Failed to store metrics snapshot", error=str(e))
            return False

    async def get_sensor_readings(self,
                                sensor_id: Optional[int] = None,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None,
                                limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve sensor readings with optional filtering."""
        try:
            start_time_db = datetime.now()

            # Build query
            query = "SELECT * FROM sensor_readings WHERE 1=1"
            params = []

            if sensor_id:
                query += " AND sensor_id = ?"
                params.append(sensor_id)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to dictionaries
                    columns = [desc[0] for desc in cursor.description]
                    results = []

                    for row in rows:
                        reading_dict = dict(zip(columns, row))

                        # Parse JSON fields
                        if reading_dict['raw_gpio_state']:
                            reading_dict['raw_gpio_state'] = json.loads(reading_dict['raw_gpio_state'])

                        results.append(reading_dict)

            # Track performance
            duration = (datetime.now() - start_time_db).total_seconds() * 1000
            self.last_operation_duration_ms = duration
            self.query_count += 1

            return results

        except Exception as e:
            logger.error("Failed to retrieve sensor readings", error=str(e))
            return []

    async def get_alert_events(self,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             acknowledged: Optional[bool] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve alert events with optional filtering."""
        try:
            # Build query
            query = "SELECT * FROM alert_events WHERE 1=1"
            params = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            if acknowledged is not None:
                query += " AND acknowledged = ?"
                params.append(acknowledged)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to dictionaries
                    columns = [desc[0] for desc in cursor.description]
                    results = []

                    for row in rows:
                        alert_dict = dict(zip(columns, row))

                        # Parse JSON fields
                        if alert_dict['metadata']:
                            alert_dict['metadata'] = json.loads(alert_dict['metadata'])

                        results.append(alert_dict)

            self.query_count += 1
            return results

        except Exception as e:
            logger.error("Failed to retrieve alert events", error=str(e))
            return []

    async def get_metrics_history(self,
                                start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None,
                                limit: int = 288) -> List[Dict[str, Any]]:  # 288 = 24 hours at 5min intervals
        """Retrieve metrics snapshots with optional filtering."""
        try:
            # Build query
            query = "SELECT * FROM metric_snapshots WHERE 1=1"
            params = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            with self._lock:
                with self._get_cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    # Convert to dictionaries
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in rows]

            self.query_count += 1
            return results

        except Exception as e:
            logger.error("Failed to retrieve metrics history", error=str(e))
            return []

    async def cleanup_old_data(self) -> Dict[str, int]:
        """Clean up old data based on retention policy."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.max_retention_hours)
            cutoff_iso = cutoff_time.isoformat()

            counts = {}

            with self._lock:
                with self._get_cursor() as cursor:
                    # Clean sensor readings
                    cursor.execute("DELETE FROM sensor_readings WHERE timestamp < ?", (cutoff_iso,))
                    counts['sensor_readings'] = cursor.rowcount

                    # Clean alert events (but keep unacknowledged alerts)
                    cursor.execute("""
                        DELETE FROM alert_events
                        WHERE timestamp < ? AND acknowledged = TRUE
                    """, (cutoff_iso,))
                    counts['alert_events'] = cursor.rowcount

                    # Clean old metric snapshots (but keep some for history)
                    old_cutoff_iso = (cutoff_time - timedelta(hours=24)).isoformat()
                    cursor.execute("DELETE FROM metric_snapshots WHERE timestamp < ?", (old_cutoff_iso,))
                    counts['metric_snapshots'] = cursor.rowcount

                    # Clean performance logs
                    cursor.execute("DELETE FROM performance_logs WHERE timestamp < ?", (cutoff_iso,))
                    counts['performance_logs'] = cursor.rowcount

            total_cleaned = sum(counts.values())
            if total_cleaned > 0:
                logger.info("Cleaned up old data", counts=counts, total=total_cleaned)

            return counts

        except Exception as e:
            logger.error("Failed to cleanup old data", error=str(e))
            return {}

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage performance and size statistics."""
        try:
            stats = {
                "database_path": self.database_path,
                "query_count": self.query_count,
                "insert_count": self.insert_count,
                "last_operation_duration_ms": self.last_operation_duration_ms,
                "retention_hours": self.max_retention_hours,
                "is_running": self.is_running
            }

            # Get table row counts
            if self.connection:
                with self._lock:
                    with self._get_cursor() as cursor:
                        for table in ['sensor_readings', 'alert_events', 'metric_snapshots']:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            stats[f"{table}_count"] = cursor.fetchone()[0]

                        # Get database file size (for file-based databases)
                        if self.database_path != ":memory:":
                            try:
                                db_path = Path(self.database_path)
                                if db_path.exists():
                                    stats["database_size_mb"] = db_path.stat().st_size / (1024 * 1024)
                            except Exception:
                                stats["database_size_mb"] = 0

            return stats

        except Exception as e:
            logger.error("Failed to get storage stats", error=str(e))
            return {"error": str(e)}

    async def _cleanup_loop(self) -> None:
        """Background cleanup task."""
        logger.info("Storage cleanup loop started")

        while self.is_running:
            try:
                # Perform cleanup
                await self.cleanup_old_data()

                # Sleep until next cleanup
                await asyncio.sleep(self.cleanup_interval_minutes * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))
                await asyncio.sleep(300)  # Wait 5 minutes on error

        logger.info("Storage cleanup loop stopped")

    async def export_session_data(self, output_path: str) -> bool:
        """Export all session data to a JSON file."""
        try:
            logger.info("Exporting session data", output_path=output_path)

            # Gather all data
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "retention_hours": self.max_retention_hours,
                "sensor_readings": await self.get_sensor_readings(limit=10000),
                "alert_events": await self.get_alert_events(limit=1000),
                "metrics_history": await self.get_metrics_history(limit=1000),
                "storage_stats": self.get_storage_stats()
            }

            # Write to file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info("Session data exported successfully",
                       output_path=output_path,
                       size_mb=output_file.stat().st_size / (1024 * 1024))

            return True

        except Exception as e:
            logger.error("Failed to export session data", error=str(e))
            return False


# Export the main component
__all__ = ["SessionStorage"]