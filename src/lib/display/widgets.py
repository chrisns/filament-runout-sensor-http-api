"""Real-time status widgets for filament sensor monitoring display."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from textual.widgets import Static, ProgressBar, Label
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.text import Text
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from ...models.sensor_reading import SensorReading
from ...models.system_status import SystemStatus, SystemHealth
from ...models.session_metrics import SessionMetrics


class SensorStatusWidget(Static):
    """Widget displaying real-time status for a single sensor."""

    sensor_id: reactive[int] = reactive(1)
    current_reading: reactive[Optional[SensorReading]] = reactive(None)

    def __init__(self, sensor_id: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.sensor_id = sensor_id
        self.current_reading = None

    def compose(self) -> ComposeResult:
        """Compose the sensor status widget."""
        yield Static(f"Sensor {self.sensor_id}", classes="sensor-title")
        yield Static("", id=f"sensor-{self.sensor_id}-status", classes="sensor-status")
        yield Static("", id=f"sensor-{self.sensor_id}-metrics", classes="sensor-metrics")

    def watch_current_reading(self, reading: Optional[SensorReading]) -> None:
        """Update display when sensor reading changes."""
        self.update_display(reading)

    def update_display(self, reading: Optional[SensorReading]) -> None:
        """Update the widget display with current sensor data."""
        status_widget = self.query_one(f"#sensor-{self.sensor_id}-status")
        metrics_widget = self.query_one(f"#sensor-{self.sensor_id}-metrics")

        if reading is None:
            status_widget.update("[red]No Data[/red]")
            metrics_widget.update("Pulses: -- | Distance: -- mm")
            return

        # Status display with color coding
        status_color = self._get_status_color(reading.filament_status)
        age_text = f" ({reading.age_seconds:.1f}s)" if reading.age_seconds > 0.5 else ""

        status_text = f"[{status_color}]{reading.filament_status.upper()}[/{status_color}]{age_text}"
        if reading.is_stale():
            status_text += " [yellow](STALE)[/yellow]"

        status_widget.update(status_text)

        # Metrics display
        metrics_text = f"Pulses: {reading.pulse_count:,} | Distance: {reading.distance_mm:.1f} mm"
        if reading.is_moving:
            metrics_text += " [green]⟲[/green]"

        metrics_widget.update(metrics_text)

    def _get_status_color(self, status: str) -> str:
        """Get color for filament status."""
        color_map = {
            "runout": "red",
            "feeding": "green",
            "present": "yellow"
        }
        return color_map.get(status, "white")


class SystemHealthWidget(Static):
    """Widget displaying overall system health and connectivity."""

    health: reactive[Optional[SystemHealth]] = reactive(None)

    def compose(self) -> ComposeResult:
        """Compose the system health widget."""
        yield Static("System Health", classes="health-title")
        yield Static("", id="hardware-status", classes="health-item")
        yield Static("", id="sensor-status", classes="health-item")
        yield Static("", id="error-status", classes="health-item")

    def watch_health(self, health: Optional[SystemHealth]) -> None:
        """Update display when health status changes."""
        self.update_display(health)

    def update_display(self, health: Optional[SystemHealth]) -> None:
        """Update health status display."""
        hardware_widget = self.query_one("#hardware-status")
        sensor_widget = self.query_one("#sensor-status")
        error_widget = self.query_one("#error-status")

        if health is None:
            hardware_widget.update("Hardware: [red]Unknown[/red]")
            sensor_widget.update("Sensors: [red]Unknown[/red]")
            error_widget.update("Errors: --")
            return

        # Hardware status
        hw_color = "green" if health.hardware_connected else "red"
        hw_status = "Connected" if health.hardware_connected else "Disconnected"
        hardware_widget.update(f"Hardware: [{hw_color}]{hw_status}[/{hw_color}]")

        # Sensor status
        responsive_count = health.responsive_sensor_count
        sensor_color = "green" if responsive_count == 2 else "yellow" if responsive_count == 1 else "red"
        sensor_widget.update(f"Sensors: [{sensor_color}]{responsive_count}/2 Active[/{sensor_color}]")

        # Error status
        error_color = "red" if health.error_count_24h > 10 else "yellow" if health.error_count_24h > 0 else "green"
        error_widget.update(f"Errors (24h): [{error_color}]{health.error_count_24h}[/{error_color}]")


class SessionMetricsWidget(Static):
    """Widget displaying session-level metrics and statistics."""

    metrics: reactive[Optional[SessionMetrics]] = reactive(None)
    uptime_seconds: reactive[float] = reactive(0.0)

    def compose(self) -> ComposeResult:
        """Compose the session metrics widget."""
        yield Static("Session Metrics", classes="metrics-title")
        yield Static("", id="uptime-display", classes="metrics-item")
        yield Static("", id="total-distance", classes="metrics-item")
        yield Static("", id="activity-summary", classes="metrics-item")

    def watch_metrics(self, metrics: Optional[SessionMetrics]) -> None:
        """Update display when metrics change."""
        self.update_display(metrics)

    def watch_uptime_seconds(self, uptime: float) -> None:
        """Update uptime display."""
        self.update_uptime_display(uptime)

    def update_display(self, metrics: Optional[SessionMetrics]) -> None:
        """Update metrics display."""
        distance_widget = self.query_one("#total-distance")
        activity_widget = self.query_one("#activity-summary")

        if metrics is None:
            distance_widget.update("Total Distance: -- m")
            activity_widget.update("Activity: --")
            return

        # Total distance
        distance_widget.update(f"Total Distance: {metrics.total_distance_m:.2f} m")

        # Activity summary
        s1_pulses = metrics.sensor1.total_pulses
        s2_pulses = metrics.sensor2.total_pulses
        activity_widget.update(f"S1: {s1_pulses:,}p | S2: {s2_pulses:,}p")

    def update_uptime_display(self, uptime_seconds: float) -> None:
        """Update uptime display."""
        uptime_widget = self.query_one("#uptime-display")

        if uptime_seconds < 60:
            uptime_text = f"{uptime_seconds:.1f}s"
        elif uptime_seconds < 3600:
            minutes = uptime_seconds / 60
            uptime_text = f"{minutes:.1f}m"
        else:
            hours = uptime_seconds / 3600
            uptime_text = f"{hours:.1f}h"

        uptime_widget.update(f"Uptime: {uptime_text}")


class AlertsPanelWidget(Static):
    """Widget displaying recent alerts and notifications."""

    recent_alerts: reactive[list] = reactive([])
    unacknowledged_count: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        """Compose the alerts panel widget."""
        yield Static("Recent Alerts", classes="alerts-title")
        yield Static("", id="alert-summary", classes="alert-summary")
        yield Static("", id="alert-list", classes="alert-list")

    def watch_recent_alerts(self, alerts: list) -> None:
        """Update display when alerts change."""
        self.update_display(alerts)

    def watch_unacknowledged_count(self, count: int) -> None:
        """Update unacknowledged alert count."""
        self.update_summary(count)

    def update_summary(self, unack_count: int) -> None:
        """Update alert summary."""
        summary_widget = self.query_one("#alert-summary")

        if unack_count == 0:
            summary_widget.update("[green]No unacknowledged alerts[/green]")
        else:
            color = "red" if unack_count > 5 else "yellow"
            summary_widget.update(f"[{color}]{unack_count} unacknowledged[/{color}]")

    def update_display(self, alerts: list) -> None:
        """Update alerts list display."""
        alerts_widget = self.query_one("#alert-list")

        if not alerts:
            alerts_widget.update("No recent alerts")
            return

        # Show last 3 alerts
        alert_lines = []
        for alert in alerts[:3]:
            timestamp = alert.timestamp.strftime("%H:%M:%S") if hasattr(alert, 'timestamp') else "??:??:??"
            severity_color = self._get_severity_color(getattr(alert, 'severity', 'INFO'))
            message = getattr(alert, 'message', 'Unknown alert')[:40] + "..." if len(getattr(alert, 'message', '')) > 40 else getattr(alert, 'message', 'Unknown alert')

            ack_indicator = "✓" if getattr(alert, 'acknowledged', False) else "!"
            alert_lines.append(f"[{severity_color}]{timestamp} {ack_indicator} {message}[/{severity_color}]")

        alerts_widget.update("\n".join(alert_lines))

    def _get_severity_color(self, severity: str) -> str:
        """Get color for alert severity."""
        color_map = {
            "CRITICAL": "red bold",
            "ERROR": "red",
            "WARNING": "yellow",
            "INFO": "blue"
        }
        return color_map.get(severity.upper(), "white")


class StatusBarWidget(Static):
    """Bottom status bar showing key system information."""

    system_running: reactive[bool] = reactive(False)
    hardware_connected: reactive[bool] = reactive(False)
    active_sensors: reactive[int] = reactive(0)
    last_update: reactive[Optional[datetime]] = reactive(None)

    def compose(self) -> ComposeResult:
        """Compose the status bar."""
        yield Static("", id="status-bar-content", classes="status-bar")

    def watch_system_running(self, running: bool) -> None:
        """Update when system running state changes."""
        self.update_status_bar()

    def watch_hardware_connected(self, connected: bool) -> None:
        """Update when hardware connection changes."""
        self.update_status_bar()

    def watch_active_sensors(self, count: int) -> None:
        """Update when active sensor count changes."""
        self.update_status_bar()

    def watch_last_update(self, timestamp: Optional[datetime]) -> None:
        """Update when last update timestamp changes."""
        self.update_status_bar()

    def update_status_bar(self) -> None:
        """Update the status bar content."""
        status_widget = self.query_one("#status-bar-content")

        # System status
        system_color = "green" if self.system_running else "red"
        system_text = "RUNNING" if self.system_running else "STOPPED"

        # Hardware status
        hw_color = "green" if self.hardware_connected else "red"
        hw_text = "HW:OK" if self.hardware_connected else "HW:DISC"

        # Sensor status
        sensor_color = "green" if self.active_sensors == 2 else "yellow" if self.active_sensors == 1 else "red"
        sensor_text = f"SENS:{self.active_sensors}/2"

        # Last update
        if self.last_update:
            update_age = (datetime.now() - self.last_update).total_seconds()
            if update_age < 2:
                update_color = "green"
                update_text = "LIVE"
            elif update_age < 10:
                update_color = "yellow"
                update_text = f"{update_age:.0f}s"
            else:
                update_color = "red"
                update_text = "STALE"
        else:
            update_color = "red"
            update_text = "NO DATA"

        # Compose status bar
        status_text = (
            f"[{system_color}]{system_text}[/{system_color}] | "
            f"[{hw_color}]{hw_text}[/{hw_color}] | "
            f"[{sensor_color}]{sensor_text}[/{sensor_color}] | "
            f"[{update_color}]{update_text}[/{update_color}]"
        )

        current_time = datetime.now().strftime("%H:%M:%S")
        full_status = f"{status_text} | {current_time}"

        status_widget.update(full_status)


class LiveGraphWidget(Static):
    """Widget showing a simple ASCII graph of filament movement."""

    def __init__(self, sensor_id: int, **kwargs):
        super().__init__(**kwargs)
        self.sensor_id = sensor_id
        self.history: list[float] = []
        self.max_points = 50

    def compose(self) -> ComposeResult:
        """Compose the live graph widget."""
        yield Static(f"Sensor {self.sensor_id} Activity", classes="graph-title")
        yield Static("", id=f"graph-{self.sensor_id}", classes="graph-display")

    def add_data_point(self, pulse_count: int, is_moving: bool) -> None:
        """Add a new data point to the graph."""
        # Simple activity level: 1 if moving, 0 if not
        activity = 1.0 if is_moving else 0.0

        self.history.append(activity)
        if len(self.history) > self.max_points:
            self.history.pop(0)

        self.update_graph()

    def update_graph(self) -> None:
        """Update the ASCII graph display."""
        graph_widget = self.query_one(f"#graph-{self.sensor_id}")

        if not self.history:
            graph_widget.update("No data")
            return

        # Create simple ASCII graph
        width = min(50, len(self.history))
        height = 5

        # Normalize data to height
        graph_lines = []
        for row in range(height):
            line = ""
            threshold = (height - row) / height

            for i in range(width):
                if i < len(self.history):
                    value = self.history[-(width-i)]
                    char = "█" if value >= threshold else " "
                else:
                    char = " "
                line += char
            graph_lines.append(line)

        # Add axis labels
        graph_text = "\n".join(graph_lines)
        graph_text += "\n" + "─" * width

        graph_widget.update(graph_text)