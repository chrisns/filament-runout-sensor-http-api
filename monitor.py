#!/usr/bin/env python3
"""
MCP2221A Dual Filament Sensor Monitor
- Persistent filament usage tracking
- Non-scrolling terminal display
- HTTP API on port 5002
- Web dashboard with real-time updates
"""

import time
import json
import threading
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import EasyMCP2221

# Persistent storage file
USAGE_FILE = "filament_usage.json"

class FilamentMonitor:
    """Filament sensor monitor with display, API, and persistent storage."""

    def __init__(self):
        self.running = False
        self.mcp = None

        # Initialize persistent data structures first
        self.total_pulses = {1: 0, 2: 0}
        self.total_distance_mm = {1: 0.0, 2: 0.0}
        self.total_runout_events = {1: 0, 2: 0}
        self.first_use_date = datetime.now().isoformat()
        self.last_update_date = datetime.now().isoformat()

        # Current session data
        self.session_start_time = datetime.now()
        self.session_pulses = {1: 0, 2: 0}

        # Real-time sensor state
        self.sensor_data = {
            1: {
                'has_filament': True,
                'is_moving': False,
                'runout_events': 0,
                'speed_mm_per_s': 0.0,
                'last_movement': None
            },
            2: {
                'has_filament': True,
                'is_moving': False,
                'runout_events': 0,
                'speed_mm_per_s': 0.0,
                'last_movement': None
            }
        }

        self.last_gpio = [None, None, None, None]
        self.last_movement_time = [None, None]
        self.last_pulse_time = [None, None]
        self.calibration_mm_per_pulse = 2.88
        self.last_display_update = 0
        self.status_messages = []
        self.max_messages = 5
        self.last_save_time = time.time()

        # Now load persistent data after all attributes are initialized
        self.load_persistent_data()

    def load_persistent_data(self):
        """Load persistent usage data from file."""
        try:
            if Path(USAGE_FILE).exists():
                with open(USAGE_FILE, 'r') as f:
                    data = json.load(f)
                    self.total_pulses = {
                        1: data.get('sensor_1', {}).get('total_pulses', 0),
                        2: data.get('sensor_2', {}).get('total_pulses', 0)
                    }
                    self.total_distance_mm = {
                        1: data.get('sensor_1', {}).get('total_distance_mm', 0.0),
                        2: data.get('sensor_2', {}).get('total_distance_mm', 0.0)
                    }
                    self.total_runout_events = {
                        1: data.get('sensor_1', {}).get('total_runout_events', 0),
                        2: data.get('sensor_2', {}).get('total_runout_events', 0)
                    }
                    self.first_use_date = data.get('first_use_date', datetime.now().isoformat())
                    self.last_update_date = data.get('last_update_date', datetime.now().isoformat())
                    self.add_message(f"[OK] Loaded usage history: S1={self.total_distance_mm[1]:.1f}mm, S2={self.total_distance_mm[2]:.1f}mm")
            else:
                # Initialize new data
                self.total_pulses = {1: 0, 2: 0}
                self.total_distance_mm = {1: 0.0, 2: 0.0}
                self.total_runout_events = {1: 0, 2: 0}
                self.first_use_date = datetime.now().isoformat()
                self.last_update_date = datetime.now().isoformat()
                self.save_persistent_data()
                self.add_message("[OK] Created new usage history file")
        except Exception as e:
            self.add_message(f"[WARN] Could not load history: {e}")
            # Initialize with defaults
            self.total_pulses = {1: 0, 2: 0}
            self.total_distance_mm = {1: 0.0, 2: 0.0}
            self.total_runout_events = {1: 0, 2: 0}
            self.first_use_date = datetime.now().isoformat()
            self.last_update_date = datetime.now().isoformat()

    def save_persistent_data(self):
        """Save persistent usage data to file."""
        try:
            data = {
                'sensor_1': {
                    'total_pulses': self.total_pulses[1],
                    'total_distance_mm': self.total_distance_mm[1],
                    'total_distance_m': self.total_distance_mm[1] / 1000,
                    'total_runout_events': self.total_runout_events[1]
                },
                'sensor_2': {
                    'total_pulses': self.total_pulses[2],
                    'total_distance_mm': self.total_distance_mm[2],
                    'total_distance_m': self.total_distance_mm[2] / 1000,
                    'total_runout_events': self.total_runout_events[2]
                },
                'first_use_date': self.first_use_date,
                'last_update_date': datetime.now().isoformat(),
                'total_distance_all_mm': self.total_distance_mm[1] + self.total_distance_mm[2],
                'total_distance_all_m': (self.total_distance_mm[1] + self.total_distance_mm[2]) / 1000
            }

            with open(USAGE_FILE, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            self.add_message(f"[ERROR] Could not save history: {e}")

    def connect(self):
        """Connect to MCP2221A."""
        try:
            self.mcp = EasyMCP2221.Device()
            self.mcp.set_pin_function(
                gp0='GPIO_IN',  # Sensor 1 Motion
                gp1='GPIO_IN',  # Sensor 1 Runout
                gp2='GPIO_IN',  # Sensor 2 Motion
                gp3='GPIO_IN'   # Sensor 2 Runout
            )
            self.add_message("[OK] Connected to MCP2221A")

            # Read initial GPIO state to set correct filament status
            initial_gpio = self.read_sensors()
            if initial_gpio[1] is not None:  # GP1 = Sensor 1 Runout
                self.sensor_data[1]['has_filament'] = (initial_gpio[1] == 1)  # HIGH = filament present
                if not self.sensor_data[1]['has_filament']:
                    self.add_message("[INIT] Sensor 1: No filament detected")
            if initial_gpio[3] is not None:  # GP3 = Sensor 2 Runout
                self.sensor_data[2]['has_filament'] = (initial_gpio[3] == 1)  # HIGH = filament present
                if not self.sensor_data[2]['has_filament']:
                    self.add_message("[INIT] Sensor 2: No filament detected")

            # Store initial state to avoid false change detections
            self.last_gpio = initial_gpio

            return True
        except Exception as e:
            self.add_message(f"[ERROR] Could not connect: {e}")
            return False

    def add_message(self, msg):
        """Add a status message to the rolling buffer."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_messages.append(f"{timestamp} {msg}")
        if len(self.status_messages) > self.max_messages:
            self.status_messages.pop(0)

    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def read_sensors(self):
        """Read all sensor states."""
        try:
            gpio = self.mcp.GPIO_read()
            if isinstance(gpio, tuple) and len(gpio) >= 4:
                return list(gpio[:4])
            return [None, None, None, None]
        except:
            return [None, None, None, None]

    def monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                current_gpio = self.read_sensors()
                current_time = time.time()

                # Always update filament status directly from GPIO
                if current_gpio[1] is not None:  # GP1 = Sensor 1 Runout
                    self.sensor_data[1]['has_filament'] = (current_gpio[1] == 1)  # HIGH = filament present
                if current_gpio[3] is not None:  # GP3 = Sensor 2 Runout
                    self.sensor_data[2]['has_filament'] = (current_gpio[3] == 1)  # HIGH = filament present

                # Process each GPIO pin for changes (motion detection and runout events)
                for pin in range(4):
                    if current_gpio[pin] is not None and self.last_gpio[pin] is not None:
                        if current_gpio[pin] != self.last_gpio[pin]:
                            self.process_gpio_change(pin, self.last_gpio[pin], current_gpio[pin], current_time)

                # Update movement status based on timeout (5 seconds)
                for sensor_id in [1, 2]:
                    if self.last_movement_time[sensor_id - 1]:
                        if current_time - self.last_movement_time[sensor_id - 1] > 5:
                            if self.sensor_data[sensor_id]['is_moving']:
                                self.sensor_data[sensor_id]['is_moving'] = False
                                self.sensor_data[sensor_id]['speed_mm_per_s'] = 0.0
                                self.add_message(f"Sensor {sensor_id}: Movement stopped")

                self.last_gpio = current_gpio

                # Update display every 100ms
                if current_time - self.last_display_update > 0.1:
                    self.update_display()
                    self.last_display_update = current_time

                # Auto-save every 30 seconds
                if current_time - self.last_save_time > 30:
                    self.save_persistent_data()
                    self.last_save_time = current_time

                time.sleep(0.01)  # 10ms polling

            except Exception as e:
                self.add_message(f"[ERROR] Monitor: {e}")
                time.sleep(0.1)

    def process_gpio_change(self, pin, old_value, new_value, timestamp):
        """Process GPIO pin state change."""
        if pin == 0:  # Sensor 1 Motion
            if old_value == 1 and new_value == 0:  # Falling edge = pulse
                self.session_pulses[1] += 1
                self.total_pulses[1] += 1
                self.total_distance_mm[1] += self.calibration_mm_per_pulse

                self.sensor_data[1]['is_moving'] = True
                self.sensor_data[1]['last_movement'] = datetime.now().isoformat()

                # Calculate speed
                if self.last_pulse_time[0]:
                    time_diff = timestamp - self.last_pulse_time[0]
                    if time_diff > 0:
                        self.sensor_data[1]['speed_mm_per_s'] = self.calibration_mm_per_pulse / time_diff

                self.last_pulse_time[0] = timestamp
                self.last_movement_time[0] = timestamp
                self.add_message(f"S1: Pulse #{self.total_pulses[1]} ({self.total_distance_mm[1]:.1f}mm total)")

        elif pin == 1:  # Sensor 1 Runout
            # Track runout events when filament goes from present to absent
            if old_value == 1 and new_value == 0:  # HIGH to LOW = filament removed
                self.sensor_data[1]['runout_events'] += 1
                self.total_runout_events[1] += 1
                self.add_message("[ALERT] Sensor 1: FILAMENT RUNOUT!")
            elif old_value == 0 and new_value == 1:  # LOW to HIGH = filament inserted
                self.add_message("Sensor 1: Filament inserted")

        elif pin == 2:  # Sensor 2 Motion
            if old_value == 1 and new_value == 0:  # Falling edge = pulse
                self.session_pulses[2] += 1
                self.total_pulses[2] += 1
                self.total_distance_mm[2] += self.calibration_mm_per_pulse

                self.sensor_data[2]['is_moving'] = True
                self.sensor_data[2]['last_movement'] = datetime.now().isoformat()

                # Calculate speed
                if self.last_pulse_time[1]:
                    time_diff = timestamp - self.last_pulse_time[1]
                    if time_diff > 0:
                        self.sensor_data[2]['speed_mm_per_s'] = self.calibration_mm_per_pulse / time_diff

                self.last_pulse_time[1] = timestamp
                self.last_movement_time[1] = timestamp
                self.add_message(f"S2: Pulse #{self.total_pulses[2]} ({self.total_distance_mm[2]:.1f}mm total)")

        elif pin == 3:  # Sensor 2 Runout
            # Track runout events when filament goes from present to absent
            if old_value == 1 and new_value == 0:  # HIGH to LOW = filament removed
                self.sensor_data[2]['runout_events'] += 1
                self.total_runout_events[2] += 1
                self.add_message("[ALERT] Sensor 2: FILAMENT RUNOUT!")
            elif old_value == 0 and new_value == 1:  # LOW to HIGH = filament inserted
                self.add_message("Sensor 2: Filament inserted")

    def update_display(self):
        """Update the terminal display (non-scrolling)."""
        uptime = (datetime.now() - self.session_start_time).total_seconds()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        # Build entire display in memory first
        lines = []
        lines.append("=" * 60)
        lines.append("MCP2221A DUAL FILAMENT SENSOR MONITOR v3".center(60))
        lines.append("=" * 60)
        lines.append(f"Session: {hours:02d}:{minutes:02d}:{seconds:02d}".ljust(30) + f"API: http://localhost:5002/status".rjust(30))
        lines.append(f"Since: {self.first_use_date[:10]}".ljust(30) + f"Saved: {USAGE_FILE}".rjust(30))
        lines.append("-" * 60)
        lines.append("")

        # Sensor headers
        lines.append("SENSOR 1".ljust(30) + "SENSOR 2".rjust(30))
        lines.append("-" * 60)

        # Sensor data
        for sensor_id in [1, 2]:
            if sensor_id == 1:
                pos = "ljust"
            else:
                pos = "rjust"

        # Filament status
        s1 = self.sensor_data[1]
        s2 = self.sensor_data[2]
        s1_fil = "[OK] FILAMENT" if s1['has_filament'] else "[!!] NO FILAMENT"
        s2_fil = "[OK] FILAMENT" if s2['has_filament'] else "[!!] NO FILAMENT"
        lines.append(f"Status: {s1_fil}".ljust(30) + f"Status: {s2_fil}".rjust(30))

        # Movement status
        s1_move = "[*] MOVING" if s1['is_moving'] else "[ ] IDLE"
        s2_move = "[*] MOVING" if s2['is_moving'] else "[ ] IDLE"
        lines.append(f"Motion: {s1_move}".ljust(30) + f"Motion: {s2_move}".rjust(30))

        # Speed
        lines.append(f"Speed:  {s1['speed_mm_per_s']:.1f} mm/s".ljust(30) +
                    f"Speed:  {s2['speed_mm_per_s']:.1f} mm/s".rjust(30))

        # Session stats
        lines.append(f"Session: {self.session_pulses[1]} pulses".ljust(30) +
                    f"Session: {self.session_pulses[2]} pulses".rjust(30))

        # Total distance (persistent)
        lines.append(f"TOTAL:  {self.total_distance_mm[1]:.1f}mm ({self.total_distance_mm[1]/1000:.2f}m)".ljust(30) +
                    f"TOTAL:  {self.total_distance_mm[2]:.1f}mm ({self.total_distance_mm[2]/1000:.2f}m)".rjust(30))

        # Total pulses (persistent)
        lines.append(f"Pulses: {self.total_pulses[1]} all-time".ljust(30) +
                    f"Pulses: {self.total_pulses[2]} all-time".rjust(30))

        # Runout events
        lines.append(f"Runouts: {self.total_runout_events[1]} total".ljust(30) +
                    f"Runouts: {self.total_runout_events[2]} total".rjust(30))

        lines.append("")
        lines.append("-" * 60)
        lines.append("RECENT EVENTS:")
        for msg in self.status_messages:
            lines.append(f"  {msg}")

        # Combined totals
        lines.append("")
        lines.append("-" * 60)
        total_all = self.total_distance_mm[1] + self.total_distance_mm[2]
        lines.append(f"COMBINED TOTAL: {total_all:.1f}mm ({total_all/1000:.3f}m)")

        # Pad to fixed height
        while len(lines) < 28:
            lines.append("")

        lines.append("-" * 60)
        lines.append("Ctrl+C to stop | Auto-saves every 30 seconds")

        # Build complete frame
        output = '\n'.join(lines[:30])

        # Use cursor positioning to overwrite previous display without clearing
        if os.name == 'nt':  # Windows
            # Move cursor to home position without clearing
            print('\033[H', end='')
        else:
            # Move cursor to home position
            print('\033[H', end='')

        # Write entire frame at once
        print(output, end='')

        # Clear any remaining lines from previous frame
        print('\033[J', end='')

        sys.stdout.flush()

    def get_status_json(self):
        """Get current status as JSON."""
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.session_start_time).total_seconds(),
            'system': {
                'connected': self.mcp is not None,
                'version': '3.0.0',
                'first_use_date': self.first_use_date,
                'last_update_date': self.last_update_date
            },
            'sensors': [
                {
                    'id': 1,
                    'has_filament': self.sensor_data[1]['has_filament'],
                    'is_moving': self.sensor_data[1]['is_moving'],
                    'usage_meters': self.total_distance_mm[1] / 1000,
                    'session_meters': (self.session_pulses[1] * self.calibration_mm_per_pulse) / 1000,
                    'last_movement': self.sensor_data[1]['last_movement'],
                    'pulse_count': self.total_pulses[1],
                    'session_pulses': self.session_pulses[1],
                    'speed_mm_per_s': self.sensor_data[1]['speed_mm_per_s'],
                    'runout_events': self.total_runout_events[1]
                },
                {
                    'id': 2,
                    'has_filament': self.sensor_data[2]['has_filament'],
                    'is_moving': self.sensor_data[2]['is_moving'],
                    'usage_meters': self.total_distance_mm[2] / 1000,
                    'session_meters': (self.session_pulses[2] * self.calibration_mm_per_pulse) / 1000,
                    'last_movement': self.sensor_data[2]['last_movement'],
                    'pulse_count': self.total_pulses[2],
                    'session_pulses': self.session_pulses[2],
                    'speed_mm_per_s': self.sensor_data[2]['speed_mm_per_s'],
                    'runout_events': self.total_runout_events[2]
                }
            ],
            'totals': {
                'all_time_meters': (self.total_distance_mm[1] + self.total_distance_mm[2]) / 1000,
                'session_meters': ((self.session_pulses[1] + self.session_pulses[2]) * self.calibration_mm_per_pulse) / 1000
            }
        }

    def start(self):
        """Start monitoring."""
        if not self.connect():
            return False

        self.running = True

        # Enable ANSI escape codes on Windows
        if os.name == 'nt':
            os.system('')  # Enables ANSI codes in Windows terminal

        # Initial screen clear
        self.clear_screen()

        monitor_thread = threading.Thread(target=self.monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()

        return True

    def stop(self):
        """Stop monitoring and save data."""
        self.running = False
        self.save_persistent_data()
        self.add_message("Monitor stopped, data saved")


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for API."""
    monitor = None

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if self.monitor:
                response = self.monitor.get_status_json()
            else:
                response = {'error': 'Monitor not initialized'}

            self.wfile.write(json.dumps(response, indent=2).encode())

        elif self.path == '/' or self.path == '/dashboard.html':
            # Serve the dashboard.html file
            dashboard_file = Path('dashboard.html')
            if dashboard_file.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                with open(dashboard_file, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                html = """
                <html>
                <head>
                    <title>Error</title>
                </head>
                <body>
                    <h1>Dashboard Not Found</h1>
                    <p>The dashboard.html file was not found in the current directory.</p>
                </body>
                </html>
                """
                self.wfile.write(html.encode())

        else:
            self.send_response(404)
            self.end_headers()


def run_api_server(monitor, port=5002):
    """Run the HTTP API server."""
    APIHandler.monitor = monitor
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    monitor.add_message(f"API server started on port {port}")
    server.serve_forever()


def main():
    """Main entry point."""
    monitor = FilamentMonitor()

    if not monitor.start():
        print("[ERROR] Failed to start monitor")
        return 1

    # Start API server in background
    api_thread = threading.Thread(target=run_api_server, args=(monitor, 5002))
    api_thread.daemon = True
    api_thread.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        monitor.add_message("Shutdown requested")

    monitor.stop()
    monitor.clear_screen()

    print("\n" + "=" * 60)
    print("MONITOR STOPPED")
    print("=" * 60)
    print(f"Total usage saved to: {USAGE_FILE}")
    print(f"  Sensor 1: {monitor.total_distance_mm[1]:.1f}mm ({monitor.total_distance_mm[1]/1000:.3f}m)")
    print(f"  Sensor 2: {monitor.total_distance_mm[2]:.1f}mm ({monitor.total_distance_mm[2]/1000:.3f}m)")
    print(f"  Combined: {(monitor.total_distance_mm[1] + monitor.total_distance_mm[2]):.1f}mm")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
