"""Layout definitions for split-screen dual sensor monitoring display."""

from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Static, Header, Footer
from textual.app import ComposeResult
from textual.css.query import NoMatches

from .widgets import (
    SensorStatusWidget,
    SystemHealthWidget,
    SessionMetricsWidget,
    AlertsPanelWidget,
    StatusBarWidget,
    LiveGraphWidget
)


class SensorPanelLayout(Container):
    """Layout for a single sensor's information panel."""

    def __init__(self, sensor_id: int, **kwargs):
        super().__init__(**kwargs)
        self.sensor_id = sensor_id

    def compose(self) -> ComposeResult:
        """Compose the sensor panel layout."""
        with Vertical(classes="sensor-panel"):
            # Main sensor status
            yield SensorStatusWidget(
                sensor_id=self.sensor_id,
                id=f"sensor-status-{self.sensor_id}",
                classes="sensor-status-main"
            )

            # Activity graph
            yield LiveGraphWidget(
                sensor_id=self.sensor_id,
                id=f"sensor-graph-{self.sensor_id}",
                classes="sensor-graph"
            )

    def get_sensor_status_widget(self) -> SensorStatusWidget:
        """Get the sensor status widget for this panel."""
        return self.query_one(f"#sensor-status-{self.sensor_id}")

    def get_graph_widget(self) -> LiveGraphWidget:
        """Get the graph widget for this panel."""
        return self.query_one(f"#sensor-graph-{self.sensor_id}")


class SystemInfoLayout(Container):
    """Layout for system information and metrics."""

    def compose(self) -> ComposeResult:
        """Compose the system info layout."""
        with Vertical(classes="system-info"):
            # System health status
            yield SystemHealthWidget(
                id="system-health",
                classes="system-health-widget"
            )

            # Session metrics
            yield SessionMetricsWidget(
                id="session-metrics",
                classes="session-metrics-widget"
            )

    def get_health_widget(self) -> SystemHealthWidget:
        """Get the system health widget."""
        return self.query_one("#system-health")

    def get_metrics_widget(self) -> SessionMetricsWidget:
        """Get the session metrics widget."""
        return self.query_one("#session-metrics")


class AlertsLayout(Container):
    """Layout for alerts and notifications panel."""

    def compose(self) -> ComposeResult:
        """Compose the alerts layout."""
        with Vertical(classes="alerts-panel"):
            yield AlertsPanelWidget(
                id="alerts-panel",
                classes="alerts-panel-widget"
            )

    def get_alerts_widget(self) -> AlertsPanelWidget:
        """Get the alerts panel widget."""
        return self.query_one("#alerts-panel")


class DualSensorSplitLayout(Container):
    """Main split-screen layout for dual sensor monitoring."""

    def compose(self) -> ComposeResult:
        """Compose the dual sensor split layout."""
        # Top section: Dual sensor panels
        with Horizontal(classes="sensor-row"):
            yield SensorPanelLayout(
                sensor_id=1,
                id="sensor-panel-1",
                classes="sensor-panel-container left-panel"
            )
            yield SensorPanelLayout(
                sensor_id=2,
                id="sensor-panel-2",
                classes="sensor-panel-container right-panel"
            )

        # Middle section: System info and alerts
        with Horizontal(classes="info-row"):
            yield SystemInfoLayout(
                id="system-info-layout",
                classes="system-info-container"
            )
            yield AlertsLayout(
                id="alerts-layout",
                classes="alerts-container"
            )

        # Bottom section: Status bar
        yield StatusBarWidget(
            id="status-bar",
            classes="status-bar-container"
        )

    def get_sensor_panel(self, sensor_id: int) -> SensorPanelLayout:
        """Get sensor panel for specific sensor."""
        if sensor_id not in [1, 2]:
            raise ValueError("sensor_id must be 1 or 2")
        return self.query_one(f"#sensor-panel-{sensor_id}")

    def get_system_info_layout(self) -> SystemInfoLayout:
        """Get system info layout."""
        return self.query_one("#system-info-layout")

    def get_alerts_layout(self) -> AlertsLayout:
        """Get alerts layout."""
        return self.query_one("#alerts-layout")

    def get_status_bar(self) -> StatusBarWidget:
        """Get status bar widget."""
        return self.query_one("#status-bar")


class CompactMonitorLayout(Container):
    """Compact layout for smaller terminals or minimal display mode."""

    def compose(self) -> ComposeResult:
        """Compose the compact layout."""
        # Single row with sensor status
        with Horizontal(classes="compact-sensor-row"):
            yield Static(
                "S1: --",
                id="compact-sensor-1",
                classes="compact-sensor-status"
            )
            yield Static(
                "S2: --",
                id="compact-sensor-2",
                classes="compact-sensor-status"
            )
            yield Static(
                "System: --",
                id="compact-system-status",
                classes="compact-system-status"
            )

        # Status bar
        yield StatusBarWidget(
            id="compact-status-bar",
            classes="compact-status-bar"
        )

    def update_sensor_compact(self, sensor_id: int, reading) -> None:
        """Update compact sensor display."""
        try:
            widget = self.query_one(f"#compact-sensor-{sensor_id}")
            if reading:
                status_text = f"S{sensor_id}: {reading.filament_status[:4].upper()}"
                if reading.is_moving:
                    status_text += " ⟲"
                widget.update(status_text)
            else:
                widget.update(f"S{sensor_id}: --")
        except NoMatches:
            pass  # Widget not found, ignore

    def update_system_compact(self, health) -> None:
        """Update compact system status."""
        try:
            widget = self.query_one("#compact-system-status")
            if health:
                hw_status = "HW:OK" if health.hardware_connected else "HW:DISC"
                sensor_count = health.responsive_sensor_count
                widget.update(f"{hw_status} {sensor_count}/2")
            else:
                widget.update("System: --")
        except NoMatches:
            pass  # Widget not found, ignore

    def get_status_bar(self) -> StatusBarWidget:
        """Get status bar widget."""
        return self.query_one("#compact-status-bar")


class DebugLayout(Container):
    """Debug layout with detailed system information."""

    def compose(self) -> ComposeResult:
        """Compose the debug layout."""
        with Vertical(classes="debug-container"):
            # Debug info header
            yield Static("DEBUG MODE", classes="debug-header")

            # Raw system data
            yield Static("", id="debug-raw-data", classes="debug-raw-data")

            # GPIO pin states
            yield Static("", id="debug-gpio-states", classes="debug-gpio")

            # Performance metrics
            yield Static("", id="debug-performance", classes="debug-performance")

    def update_debug_data(self, system_status, raw_gpio=None, performance=None) -> None:
        """Update debug display with system data."""
        # Raw system data
        try:
            raw_widget = self.query_one("#debug-raw-data")
            if system_status:
                debug_text = f"""
Current Readings:
  Sensor 1: {system_status.current_readings.get(1)}
  Sensor 2: {system_status.current_readings.get(2)}

Health Status:
  Hardware: {system_status.health.hardware_connected}
  Sensors: {system_status.health.sensors_responding}
  Errors (24h): {system_status.health.error_count_24h}
                """.strip()
                raw_widget.update(debug_text)
            else:
                raw_widget.update("No system status available")
        except NoMatches:
            pass

        # GPIO states
        try:
            gpio_widget = self.query_one("#debug-gpio-states")
            if raw_gpio:
                gpio_text = f"""
GPIO Pin States:
  GP0: {raw_gpio.get('gp0', 'Unknown')} (Sensor 1 Movement)
  GP1: {raw_gpio.get('gp1', 'Unknown')} (Sensor 1 Runout)
  GP2: {raw_gpio.get('gp2', 'Unknown')} (Sensor 2 Movement)
  GP3: {raw_gpio.get('gp3', 'Unknown')} (Sensor 2 Runout)
                """.strip()
                gpio_widget.update(gpio_text)
            else:
                gpio_widget.update("GPIO data not available")
        except NoMatches:
            pass

        # Performance metrics
        try:
            perf_widget = self.query_one("#debug-performance")
            if performance:
                perf_text = f"""
Performance Metrics:
  Polling Rate: {performance.get('polling_hz', 'Unknown')} Hz
  UI Updates: {performance.get('ui_updates_per_sec', 'Unknown')}/s
  API Response: {performance.get('avg_api_response_ms', 'Unknown')} ms
                """.strip()
                perf_widget.update(perf_text)
            else:
                perf_widget.update("Performance data not available")
        except NoMatches:
            pass


class LayoutManager:
    """Manager for switching between different display layouts."""

    def __init__(self):
        self.current_layout = "split"
        self.available_layouts = {
            "split": DualSensorSplitLayout,
            "compact": CompactMonitorLayout,
            "debug": DebugLayout
        }

    def get_layout_class(self, layout_name: str = None):
        """Get layout class by name."""
        if layout_name is None:
            layout_name = self.current_layout

        if layout_name not in self.available_layouts:
            raise ValueError(f"Unknown layout: {layout_name}")

        return self.available_layouts[layout_name]

    def set_current_layout(self, layout_name: str) -> None:
        """Set the current active layout."""
        if layout_name not in self.available_layouts:
            raise ValueError(f"Unknown layout: {layout_name}")
        self.current_layout = layout_name

    def get_layout_names(self) -> list[str]:
        """Get list of available layout names."""
        return list(self.available_layouts.keys())

    def create_layout(self, layout_name: str = None, **kwargs):
        """Create instance of specified layout."""
        layout_class = self.get_layout_class(layout_name)
        return layout_class(**kwargs)