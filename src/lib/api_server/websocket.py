"""WebSocket support for real-time sensor data streaming."""

import json
import asyncio
from typing import Set, Dict, Any, Optional, List
from datetime import datetime, timedelta
import weakref

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
import structlog

from ...models import SystemStatus, SensorReading

logger = structlog.get_logger(__name__)


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure."""

    type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict)


class SensorUpdateMessage(WebSocketMessage):
    """Sensor reading update message."""

    type: str = "sensor_update"


class SystemStatusMessage(WebSocketMessage):
    """System status update message."""

    type: str = "system_status"


class AlertMessage(WebSocketMessage):
    """Alert notification message."""

    type: str = "alert"


class ConnectionManager:
    """WebSocket connection manager for real-time updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self.last_sensor_data: Dict[int, Optional[SensorReading]] = {1: None, 2: None}
        self.last_system_status: Optional[Dict[str, Any]] = None
        self.broadcast_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

        self.connection_metadata[websocket] = {
            "client_id": client_id or f"client_{id(websocket)}",
            "connected_at": datetime.now(),
            "last_ping": datetime.now(),
            "subscriptions": ["sensor_updates", "system_status", "alerts"]  # Default subscriptions
        }

        logger.info("WebSocket connection established",
                   client_id=self.connection_metadata[websocket]["client_id"],
                   total_connections=len(self.active_connections))

        # Send initial data to new connection
        await self._send_initial_data(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            client_id = self.connection_metadata.get(websocket, {}).get("client_id", "unknown")
            self.active_connections.discard(websocket)

            logger.info("WebSocket connection closed",
                       client_id=client_id,
                       total_connections=len(self.active_connections))

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.error("Error sending personal message", error=str(e))
            self.disconnect(websocket)

    async def broadcast_message(self, message: Dict[str, Any], message_type: str = "broadcast") -> None:
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        disconnected = set()

        for websocket in self.active_connections.copy():
            try:
                # Check if client is subscribed to this message type
                metadata = self.connection_metadata.get(websocket, {})
                subscriptions = metadata.get("subscriptions", [])

                if message_type not in subscriptions and message_type != "system":
                    continue

                await websocket.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.warning("Error broadcasting to client", error=str(e))
                disconnected.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)

    async def broadcast_sensor_update(self, sensor_reading: SensorReading) -> None:
        """Broadcast sensor reading update to all clients."""
        # Check if this is a new reading (avoid duplicate broadcasts)
        if self.last_sensor_data.get(sensor_reading.sensor_id) == sensor_reading:
            return

        self.last_sensor_data[sensor_reading.sensor_id] = sensor_reading

        message = SensorUpdateMessage(
            data={
                "sensor_id": sensor_reading.sensor_id,
                "sensor_reading": sensor_reading.model_dump(),
                "filament_status": sensor_reading.filament_status,
                "distance_mm": sensor_reading.distance_mm,
                "is_moving": sensor_reading.is_moving,
                "has_filament": sensor_reading.has_filament
            }
        ).model_dump()

        await self.broadcast_message(message, "sensor_updates")

    async def broadcast_system_status(self, system_status: SystemStatus) -> None:
        """Broadcast system status update to all clients."""
        status_data = {
            "is_running": system_status.is_running,
            "uptime_seconds": system_status.uptime_seconds,
            "health": system_status.health.overall_health,
            "sensors_active": system_status.health.responsive_sensor_count,
            "hardware_connected": system_status.health.hardware_connected,
            "unacknowledged_alerts": system_status.get_unacknowledged_alert_count()
        }

        # Only broadcast if status has changed
        if self.last_system_status == status_data:
            return

        self.last_system_status = status_data

        message = SystemStatusMessage(
            data=status_data
        ).model_dump()

        await self.broadcast_message(message, "system_status")

    async def broadcast_alert(self, alert_data: Dict[str, Any]) -> None:
        """Broadcast alert notification to all clients."""
        message = AlertMessage(
            data=alert_data
        ).model_dump()

        await self.broadcast_message(message, "alerts")

    async def handle_client_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Handle incoming message from WebSocket client."""
        try:
            message_type = message.get("type")
            data = message.get("data", {})

            if message_type == "ping":
                # Update last ping time
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_ping"] = datetime.now()

                # Send pong response
                await self.send_personal_message({"type": "pong", "timestamp": datetime.now()}, websocket)

            elif message_type == "subscribe":
                # Update subscriptions
                subscriptions = data.get("subscriptions", [])
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["subscriptions"] = subscriptions
                    await self.send_personal_message({
                        "type": "subscription_updated",
                        "subscriptions": subscriptions
                    }, websocket)

            elif message_type == "get_status":
                # Send current status
                await self._send_initial_data(websocket)

            else:
                logger.warning("Unknown WebSocket message type", message_type=message_type)

        except Exception as e:
            logger.error("Error handling client message", error=str(e))

    async def _send_initial_data(self, websocket: WebSocket) -> None:
        """Send initial data to a newly connected client."""
        try:
            system_status = SystemStatus.get_instance()

            # Send current system status
            if system_status:
                status_data = {
                    "is_running": system_status.is_running,
                    "uptime_seconds": system_status.uptime_seconds,
                    "health": system_status.health.overall_health,
                    "sensors_active": system_status.health.responsive_sensor_count,
                    "hardware_connected": system_status.health.hardware_connected,
                    "unacknowledged_alerts": system_status.get_unacknowledged_alert_count()
                }

                await self.send_personal_message({
                    "type": "initial_system_status",
                    "timestamp": datetime.now(),
                    "data": status_data
                }, websocket)

                # Send current sensor readings
                for sensor_id in [1, 2]:
                    reading = system_status.get_sensor_reading(sensor_id)
                    if reading:
                        await self.send_personal_message({
                            "type": "initial_sensor_data",
                            "timestamp": datetime.now(),
                            "data": {
                                "sensor_id": sensor_id,
                                "sensor_reading": reading.model_dump(),
                                "filament_status": reading.filament_status,
                                "distance_mm": reading.distance_mm,
                                "is_moving": reading.is_moving,
                                "has_filament": reading.has_filament
                            }
                        }, websocket)

        except Exception as e:
            logger.error("Error sending initial data", error=str(e))

    def start_background_tasks(self) -> None:
        """Start background tasks for connection management."""
        if not self._running:
            self._running = True
            self.broadcast_task = asyncio.create_task(self._background_broadcaster())

    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        self._running = False
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass

    async def _background_broadcaster(self) -> None:
        """Background task to periodically broadcast updates."""
        while self._running:
            try:
                # Clean up stale connections
                await self._cleanup_stale_connections()

                # Broadcast periodic status updates
                system_status = SystemStatus.get_instance()
                if system_status and system_status.is_running:
                    await self.broadcast_system_status(system_status)

                # Wait before next broadcast cycle
                await asyncio.sleep(1.0)  # Broadcast every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in background broadcaster", error=str(e))
                await asyncio.sleep(5.0)  # Wait longer on error

    async def _cleanup_stale_connections(self) -> None:
        """Clean up connections that haven't sent a ping recently."""
        stale_connections = set()
        stale_threshold = datetime.now() - timedelta(minutes=5)

        for websocket in self.active_connections.copy():
            metadata = self.connection_metadata.get(websocket, {})
            last_ping = metadata.get("last_ping", datetime.now())

            if last_ping < stale_threshold:
                stale_connections.add(websocket)

        for websocket in stale_connections:
            try:
                await websocket.close()
            except Exception:
                pass  # Connection may already be closed
            self.disconnect(websocket)

    def get_connection_info(self) -> List[Dict[str, Any]]:
        """Get information about active connections."""
        connections = []
        for websocket in self.active_connections:
            metadata = self.connection_metadata.get(websocket, {})
            connections.append({
                "client_id": metadata.get("client_id", "unknown"),
                "connected_at": metadata.get("connected_at"),
                "last_ping": metadata.get("last_ping"),
                "subscriptions": metadata.get("subscriptions", [])
            })
        return connections


# Global connection manager instance
connection_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None) -> None:
    """WebSocket endpoint handler."""
    await connection_manager.connect(websocket, client_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await connection_manager.handle_client_message(websocket, message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from WebSocket client")
            except Exception as e:
                logger.error("Error processing WebSocket message", error=str(e))

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        connection_manager.disconnect(websocket)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return connection_manager


# Export the main components
__all__ = [
    "websocket_endpoint",
    "connection_manager",
    "get_connection_manager",
    "ConnectionManager",
    "WebSocketMessage",
    "SensorUpdateMessage",
    "SystemStatusMessage",
    "AlertMessage"
]