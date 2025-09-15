"""Textual-based terminal display library for filament sensor monitoring.

This library provides a real-time terminal interface for monitoring dual filament
sensors via MCP2221A GPIO adapter. Features include:

- Split-screen layout for dual sensor monitoring
- Real-time status updates and metrics
- System health and connectivity monitoring
- Alert notifications and management
- Multiple display modes (split, compact, debug)
- Live ASCII graphs of sensor activity

Usage:
    from src.lib.display import SensorMonitorApp

    app = SensorMonitorApp()
    app.run()

CLI Usage:
    python -m src.lib.display --demo
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.driver import Driver
from textual.binding import Binding

from ...models.system_status import SystemStatus
from ...models.sensor_reading import SensorReading
from ...models.sensor_configuration import SensorConfiguration
from .layouts import DualSensorSplitLayout, CompactMonitorLayout, DebugLayout, LayoutManager
from .widgets import SensorStatusWidget, SystemHealthWidget, SessionMetricsWidget


class SensorMonitorApp(App):
    """Main Textual application for filament sensor monitoring."""

    CSS = """
    /* Main application styles */
    Screen {
        layout: vertical;
    }

    /* Sensor panel styles */
    .sensor-panel {
        height: 1fr;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    .left-panel {
        width: 1fr;
        margin-right: 1;
    }

    .right-panel {
        width: 1fr;
        margin-left: 1;
    }

    .sensor-row {
        height: 2fr;
    }

    .info-row {
        height: 1fr;
    }

    /* Widget specific styles */
    .sensor-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .sensor-status {
        text-align: center;
        text-style: bold;
        height: 3;
    }

    .sensor-metrics {
        text-align: center;
        height: 2;
    }

    .health-title, .metrics-title, .alerts-title {
        text-style: bold;
        color: $accent;
        height: 1;
        margin-bottom: 1;
    }

    .health-item, .metrics-item {
        height: 1;
        margin: 0 1;
    }

    .alert-summary {
        height: 1;
        text-style: bold;
        margin: 0 1;
    }

    .alert-list {
        height: 1fr;
        margin: 0 1;
        overflow-y: auto;
    }

    .graph-title {
        text-style: bold;
        color: $accent;
        height: 1;
    }

    .graph-display {
        height: 6;
        font-family: monospace;
        border: solid $secondary;
        padding: 1;
    }

    /* System info styles */
    .system-info {
        width: 1fr;
        border: solid $secondary;
        margin: 1;
        padding: 1;
    }

    .alerts-panel {
        width: 1fr;
        border: solid $secondary;
        margin: 1;
        padding: 1;
    }

    /* Status bar styles */
    .status-bar-container, .compact-status-bar {
        height: 1;
        background: $surface;
        color: $text;
        content-align: center middle;
    }

    /* Compact layout styles */
    .compact-sensor-row {
        height: 3;
    }

    .compact-sensor-status {
        width: 1fr;
        text-align: center;
        text-style: bold;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    .compact-system-status {
        width: 1fr;
        text-align: center;
        border: solid $secondary;
        margin: 1;
        padding: 1;
    }

    /* Debug layout styles */
    .debug-container {
        height: 1fr;
    }

    .debug-header {
        height: 1;
        text-style: bold;
        color: $warning;
        text-align: center;
    }

    .debug-raw-data, .debug-gpio, .debug-performance {
        height: 1fr;
        border: solid $secondary;
        margin: 1;
        padding: 1;
        overflow-y: auto;
        font-family: monospace;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "layout_split", "Split View"),
        Binding("2", "layout_compact", "Compact View"),
        Binding("3", "layout_debug", "Debug View"),
        Binding("a", "acknowledge_alerts", "Ack Alerts"),
        Binding("h", "toggle_help", "Help"),
    ]

    def __init__(
        self,
        system_status: Optional[SystemStatus] = None,
        update_callback: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.system_status = system_status or SystemStatus()
        self.update_callback = update_callback
        self.layout_manager = LayoutManager()
        self.current_layout_widget = None
        self.update_interval = 0.1  # 100ms updates
        self.demo_mode = False

    def compose(self) -> ComposeResult:
        """Compose the main application."""
        yield Header(show_clock=True)

        # Start with split layout
        self.current_layout_widget = DualSensorSplitLayout(id="main-layout")
        yield self.current_layout_widget

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the application after mounting."""
        self.title = "Filament Sensor Monitor"
        self.sub_title = f"Layout: {self.layout_manager.current_layout.title()}"

        # Start the update timer
        self.set_interval(self.update_interval, self.update_display)

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_refresh(self) -> None:
        """Force refresh of all displays."""
        self.update_display()

    def action_layout_split(self) -> None:
        """Switch to split screen layout."""
        self.switch_layout("split")

    def action_layout_compact(self) -> None:
        """Switch to compact layout."""
        self.switch_layout("compact")

    def action_layout_debug(self) -> None:
        """Switch to debug layout."""
        self.switch_layout("debug")

    def action_acknowledge_alerts(self) -> None:
        """Acknowledge all unacknowledged alerts."""
        if self.system_status:
            count = self.system_status.acknowledge_all_alerts()
            if count > 0:
                self.notify(f"Acknowledged {count} alerts", severity="info")

    def action_toggle_help(self) -> None:
        """Toggle help display."""
        # Could show a modal with keybinding help
        help_text = """
        Keybindings:
        q - Quit application
        r - Refresh display
        1 - Split screen view
        2 - Compact view
        3 - Debug view
        a - Acknowledge alerts
        h - This help
        """
        self.notify(help_text.strip(), timeout=5)

    def switch_layout(self, layout_name: str) -> None:
        """Switch to a different display layout."""
        if layout_name == self.layout_manager.current_layout:
            return

        try:
            # Update layout manager
            self.layout_manager.set_current_layout(layout_name)

            # Remove current layout
            if self.current_layout_widget:
                self.current_layout_widget.remove()

            # Create and mount new layout
            layout_class = self.layout_manager.get_layout_class(layout_name)
            self.current_layout_widget = layout_class(id="main-layout")

            # Mount new layout
            self.mount(self.current_layout_widget, before=self.query_one(Footer))

            # Update title
            self.sub_title = f"Layout: {layout_name.title()}"

            # Force update
            self.update_display()

            self.notify(f"Switched to {layout_name} layout", timeout=2)

        except Exception as e:
            self.notify(f"Failed to switch layout: {e}", severity="error")

    def update_display(self) -> None:
        """Update all display elements with current data."""
        if not self.system_status:
            return

        try:
            current_layout = self.layout_manager.current_layout

            if current_layout == "split":
                self._update_split_layout()
            elif current_layout == "compact":
                self._update_compact_layout()
            elif current_layout == "debug":
                self._update_debug_layout()

        except Exception as e:
            # Log error but don't crash the display
            self.notify(f"Display update error: {e}", severity="error")

    def _update_split_layout(self) -> None:
        """Update split screen layout."""
        if not isinstance(self.current_layout_widget, DualSensorSplitLayout):
            return

        try:
            # Update sensor panels
            for sensor_id in [1, 2]:
                sensor_panel = self.current_layout_widget.get_sensor_panel(sensor_id)
                reading = self.system_status.get_sensor_reading(sensor_id)

                # Update sensor status
                status_widget = sensor_panel.get_sensor_status_widget()
                status_widget.current_reading = reading

                # Update activity graph
                graph_widget = sensor_panel.get_graph_widget()
                if reading:
                    graph_widget.add_data_point(reading.pulse_count, reading.is_moving)

            # Update system info
            system_info = self.current_layout_widget.get_system_info_layout()
            health_widget = system_info.get_health_widget()
            health_widget.health = self.system_status.health

            metrics_widget = system_info.get_metrics_widget()
            metrics_widget.metrics = self.system_status.metrics
            metrics_widget.uptime_seconds = self.system_status.uptime_seconds

            # Update alerts
            alerts_layout = self.current_layout_widget.get_alerts_layout()
            alerts_widget = alerts_layout.get_alerts_widget()
            alerts_widget.recent_alerts = self.system_status.get_recent_alerts()
            alerts_widget.unacknowledged_count = self.system_status.get_unacknowledged_alert_count()

            # Update status bar
            status_bar = self.current_layout_widget.get_status_bar()
            self._update_status_bar(status_bar)

        except Exception as e:
            # Individual widget updates may fail, continue with others
            pass

    def _update_compact_layout(self) -> None:
        """Update compact layout."""
        if not isinstance(self.current_layout_widget, CompactMonitorLayout):
            return

        try:
            # Update sensor status
            for sensor_id in [1, 2]:
                reading = self.system_status.get_sensor_reading(sensor_id)
                self.current_layout_widget.update_sensor_compact(sensor_id, reading)

            # Update system status
            self.current_layout_widget.update_system_compact(self.system_status.health)

            # Update status bar
            status_bar = self.current_layout_widget.get_status_bar()
            self._update_status_bar(status_bar)

        except Exception as e:
            pass

    def _update_debug_layout(self) -> None:
        """Update debug layout."""
        if not isinstance(self.current_layout_widget, DebugLayout):
            return

        try:
            # Get raw GPIO data if available (mock for now)
            raw_gpio = {
                'gp0': 'HIGH' if self.system_status.get_sensor_reading(1) and self.system_status.get_sensor_reading(1).is_moving else 'LOW',
                'gp1': 'LOW' if self.system_status.get_sensor_reading(1) and self.system_status.get_sensor_reading(1).has_filament else 'HIGH',
                'gp2': 'HIGH' if self.system_status.get_sensor_reading(2) and self.system_status.get_sensor_reading(2).is_moving else 'LOW',
                'gp3': 'LOW' if self.system_status.get_sensor_reading(2) and self.system_status.get_sensor_reading(2).has_filament else 'HIGH',
            }

            # Performance metrics (mock for now)
            performance = {
                'polling_hz': 10.0,
                'ui_updates_per_sec': 10.0,
                'avg_api_response_ms': 2.5
            }

            self.current_layout_widget.update_debug_data(
                self.system_status,
                raw_gpio,
                performance
            )

        except Exception as e:
            pass

    def _update_status_bar(self, status_bar) -> None:
        """Update status bar widget."""
        status_bar.system_running = self.system_status.is_running
        status_bar.hardware_connected = self.system_status.health.hardware_connected
        status_bar.active_sensors = self.system_status.health.responsive_sensor_count
        status_bar.last_update = self.system_status.last_update

    def enable_demo_mode(self) -> None:
        """Enable demo mode with simulated data."""
        self.demo_mode = True
        self.set_interval(1.0, self._generate_demo_data)

    def _generate_demo_data(self) -> None:
        """Generate demo data for testing."""
        import random

        if not self.demo_mode:
            return

        # Generate mock sensor readings
        for sensor_id in [1, 2]:
            reading = SensorReading(
                sensor_id=sensor_id,
                has_filament=random.choice([True, True, True, False]),  # Mostly true
                is_moving=random.choice([True, False]),
                pulse_count=random.randint(100, 10000),
                distance_mm=random.uniform(100.0, 5000.0)
            )
            self.system_status.update_sensor_reading(reading)

        # Update hardware status
        self.system_status.update_hardware_status(True)

        # Occasionally add alerts
        if random.random() < 0.1:  # 10% chance
            from ...models.alert_event import AlertEvent, AlertType, AlertSeverity
            alert = AlertEvent(
                alert_type=AlertType.SENSOR_RUNOUT,
                severity=AlertSeverity.WARNING,
                message=f"Demo alert {datetime.now().strftime('%H:%M:%S')}"
            )
            self.system_status.add_alert(alert)

    def set_update_callback(self, callback: Callable) -> None:
        """Set callback function for external updates."""
        self.update_callback = callback

    def get_system_status(self) -> SystemStatus:
        """Get current system status."""
        return self.system_status