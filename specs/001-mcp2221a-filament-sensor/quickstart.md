# Quick Start Guide: MCP2221A Dual Filament Sensor Monitor

## Prerequisites

### Hardware Requirements
- Windows 10/11 PC with available USB port
- MCP2221A USB-to-GPIO adapter
- 2x BIGTREETECH Smart Filament Sensor V2.0
- Connecting wires (4 per sensor)

### Software Requirements
- Python 3.11 or higher
- pip package manager
- Windows Terminal (recommended) or Command Prompt

## Installation

### 1. Clone or Download the Project
```bash
# Clone from repository
git clone [repository-url]
cd filament-sensor-monitor

# Or download and extract the ZIP file
```

### 2. Install Dependencies
```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Hardware Connection

Connect sensors to MCP2221A:
```
MCP2221A Pin | Sensor 1        | Sensor 2
-------------|-----------------|------------------
GP0          | Movement Signal | -
GP1          | Runout Signal   | -
GP2          | -               | Movement Signal
GP3          | -               | Runout Signal
VCC (3.3V)   | Power (+)       | Power (+)
GND          | Ground (-)      | Ground (-)
```

## Configuration

### 1. Create Configuration File
Create `config.yaml` in the project root:

```yaml
sensors:
  sensor_1:
    movement_pin: 0
    runout_pin: 1
    calibration_mm_per_pulse: 2.88
    enabled: true
  sensor_2:
    movement_pin: 2
    runout_pin: 3
    calibration_mm_per_pulse: 2.88
    enabled: true

polling:
  interval_ms: 100
  debounce_ms: 2

api:
  port: 5002
  host: "0.0.0.0"

display:
  refresh_rate_ms: 100
  show_graphs: true
```

### 2. Verify USB Connection
```bash
# Test MCP2221A connection
python -m mcp2221_sensor --test-connection

# Expected output:
# ✓ MCP2221A detected on USB
# ✓ Serial: [device-serial]
# ✓ GPIO pins configured successfully
```

## Running the Application

### 1. Start the Monitor
```bash
# Run the main application
python main.py

# Or with custom config
python main.py --config my-config.yaml
```

### 2. Verify Sensor Detection
The terminal should display:
```
╔══════════════════════════════════════════════════════╗
║       MCP2221A Dual Filament Sensor Monitor         ║
╠══════════════════════════════════════════════════════╣
║ System Status: Connected | Version: 0.1.0           ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║ ┌─── Sensor 1 ─────────────┐ ┌─── Sensor 2 ────────┐║
║ │ Status: ✓ Filament       │ │ Status: ✓ Filament  ║║
║ │ Moving: ● Active         │ │ Moving: ○ Idle      ║║
║ │ Usage:  1.234 m          │ │ Usage:  0.456 m     ║║
║ │ Speed:  45.2 mm/s        │ │ Speed:  0.0 mm/s    ║║
║ └───────────────────────────┘ └──────────────────────┘║
╚══════════════════════════════════════════════════════╝
```

### 3. Access Web API
Open a browser and navigate to:
- Status endpoint: http://localhost:5002/status
- API documentation: http://localhost:5002/docs

## Testing the System

### 1. Test Filament Detection
```bash
# Remove filament from Sensor 1
# Terminal should show:
# ⚠ ALERT: Sensor 1 - Filament Runout Detected!

# Insert filament back
# Terminal should show:
# ✓ Sensor 1 - Filament Inserted
```

### 2. Test Movement Detection
```bash
# Manually pull filament through Sensor 1
# Terminal should show movement indicator changing:
# Moving: ● Active (pulses detected)

# Stop pulling filament
# After 5 seconds, should show:
# Moving: ○ Idle
```

### 3. Test API Response
```bash
# In another terminal:
curl http://localhost:5002/status

# Expected JSON response:
{
  "timestamp": "2025-09-15T10:30:00Z",
  "system": {
    "connected": true,
    "version": "0.1.0",
    "uptime_seconds": 120
  },
  "sensors": [
    {
      "id": 1,
      "has_filament": true,
      "is_moving": false,
      "usage_meters": 0.0,
      "last_movement": null
    },
    {
      "id": 2,
      "has_filament": true,
      "is_moving": false,
      "usage_meters": 0.0,
      "last_movement": null
    }
  ]
}
```

### 4. Test Configuration Update
```bash
# Update calibration via API
curl -X POST http://localhost:5002/config \
  -H "Content-Type: application/json" \
  -d '{
    "sensors": [{
      "id": 1,
      "movement_pin": 0,
      "runout_pin": 1,
      "calibration_mm_per_pulse": 3.0,
      "enabled": true
    }]
  }'

# Verify change in terminal display
```

## Troubleshooting

### Issue: MCP2221A Not Detected
```bash
# Check Device Manager (Windows)
# Look for: Human Interface Devices > MCP2221 USB-I2C/UART Combo

# Try different USB port
# Avoid USB hubs initially

# Reinstall driver if needed:
# Download from: https://www.microchip.com/mcp2221
```

### Issue: No Sensor Response
```bash
# Verify wiring connections
# Check power LED on sensor (if available)
# Test with multimeter: should see 3.3V between VCC and GND

# Enable debug logging:
python main.py --debug

# Check GPIO readings:
python -m mcp2221_sensor --read-pins
```

### Issue: Incorrect Distance Measurements
```bash
# Calibrate sensor:
# 1. Mark 100mm of filament
# 2. Pull through sensor
# 3. Note pulse count in logs
# 4. Calculate: calibration = 100 / pulse_count
# 5. Update config.yaml with new value
```

### Issue: API Connection Refused
```bash
# Check if port 5002 is available:
netstat -an | findstr 5002

# Try different port in config.yaml:
api:
  port: 5003

# Check Windows Firewall settings
# May need to allow Python through firewall
```

## Command-Line Options

```bash
# Display help
python main.py --help

# Run with specific config
python main.py --config production.yaml

# Enable debug logging
python main.py --debug

# Disable API server
python main.py --no-api

# Run in demo mode (no hardware)
python main.py --demo

# Export current config
python main.py --export-config > my-config.yaml
```

## Keyboard Shortcuts

While the monitor is running:
- `q` or `Ctrl+C`: Quit application
- `r`: Reset session metrics
- `c`: Clear alert history
- `d`: Toggle debug display
- `1`: Toggle Sensor 1 enabled/disabled
- `2`: Toggle Sensor 2 enabled/disabled
- `h`: Show help panel

## Advanced Features

### WebSocket Live Data
```javascript
// Connect to WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:5002/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Sensor update:', data);
};
```

### Metrics Export
```bash
# Export session metrics to CSV
python -m tools.export_metrics --format csv > metrics.csv

# Export to JSON
python -m tools.export_metrics --format json > metrics.json
```

### Integration with OctoPrint
```bash
# Install OctoPrint plugin (future feature)
# pip install octoprint-filament-sensor-monitor

# Configure in OctoPrint settings:
# - API URL: http://localhost:5002
# - Polling interval: 1000ms
```

## Performance Validation

### 1. Pulse Detection Test
```bash
# Generate test pulses at known frequency
python -m tests.pulse_generator --frequency 100 --duration 10

# Expected: 1000 pulses detected (100Hz × 10s)
# Actual: Check session metrics
# Accuracy should be >99%
```

### 2. Response Time Test
```bash
# Measure sensor-to-display latency
python -m tests.latency_test

# Expected: <10ms average latency
# Maximum: <50ms
```

### 3. Load Test
```bash
# Simulate rapid sensor changes
python -m tests.load_test --sensors 2 --duration 60

# Monitor CPU and memory usage
# CPU should stay <10%
# Memory should stay <50MB
```

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs in `logs/` directory
3. Visit project repository for issue tracker
4. Contact support with:
   - System info: `python main.py --system-info`
   - Debug log: `python main.py --debug > debug.log 2>&1`
   - Configuration file (remove sensitive data)

## Next Steps

1. **Production Deployment**
   - Set up as Windows Service
   - Configure automatic startup
   - Set up monitoring alerts

2. **Customization**
   - Modify terminal UI layout
   - Add custom alert rules
   - Integrate with 3D printer firmware

3. **Data Analysis**
   - Export metrics for analysis
   - Create usage reports
   - Predict filament requirements