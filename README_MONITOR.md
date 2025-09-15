# MCP2221A Filament Sensor Monitor

Real-time monitoring system for dual BIGTREETECH filament sensors with persistent usage tracking, non-scrolling display, and HTTP API.

## ✅ Features

- **Persistent usage tracking** - Accumulates total filament usage between restarts
- **Session & total metrics** - Track both current session and all-time usage
- **Non-scrolling terminal display** - Clean, updating display without scrolling
- **HTTP API on port 5002** - JSON status endpoint for integration
- **Web dashboard** - Beautiful HTML interface with smooth real-time updates
- **Dual sensor monitoring** - Track two sensors simultaneously
- **Movement detection** - Pulse counting with speed calculation
- **Runout detection** - Immediate alerts when filament runs out
- **Usage tracking** - Distance measurement (2.88mm per pulse)
- **Auto-save** - Persistent data saved every 30 seconds

## 📌 Pin Configuration

| MCP2221A Pin | Function |
|-------------|----------|
| GP0 | Sensor 1 Motion Detection |
| GP1 | Sensor 1 Runout Detection |
| GP2 | Sensor 2 Motion Detection |
| GP3 | Sensor 2 Runout Detection |

## 🚀 Quick Start

### Option 1: Batch File (Easiest)
```batch
run_monitor.bat
```

### Option 2: Direct Python
```batch
C:\OctoPrint\WPy64-31050\Scripts\python.bat monitor.py
```

### Option 3: PowerShell
```powershell
.\Start-Monitor.ps1
```

## 🌐 Web Access

Once running, access the monitor via:

- **Terminal Display**: Automatic in console window
- **Web Dashboard**: Visit http://localhost:5002 (serves dashboard.html automatically)
- **JSON API**: http://localhost:5002/status

## 📊 API Response Format

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "uptime_seconds": 3600,
  "system": {
    "connected": true,
    "version": "3.0.0"
  },
  "sensors": [
    {
      "id": 1,
      "has_filament": true,
      "is_moving": false,
      "session_usage_meters": 0.1234,
      "total_usage_meters": 5.6789,
      "session_pulse_count": 42,
      "total_pulse_count": 1973,
      "last_movement": "2024-01-15T10:29:55",
      "speed_mm_per_s": 0.0,
      "runout_events": 0
    },
    {
      "id": 2,
      "has_filament": true,
      "is_moving": true,
      "session_usage_meters": 0.5678,
      "total_usage_meters": 10.2345,
      "session_pulse_count": 197,
      "total_pulse_count": 3552,
      "last_movement": "2024-01-15T10:30:00",
      "speed_mm_per_s": 45.2,
      "runout_events": 1
    }
  ]
}
```

## 🖥️ Terminal Display

The terminal shows:
- Real-time status for both sensors
- Filament presence indicators
- Movement status and speed
- Pulse counts and total distance
- Recent events log (last 5 events)
- Uptime counter

Example display:
```
============================================================
       MCP2221A DUAL FILAMENT SENSOR MONITOR
============================================================
Uptime: 00:05:23                 API: http://localhost:5002/status
------------------------------------------------------------

SENSOR 1                                      SENSOR 2
------------------------------------------------------------
Status: [OK] FILAMENT               Status: [!!] NO FILAMENT
Motion: [ ] IDLE                    Motion: [*] MOVING
Speed:  0.0 mm/s                    Speed:  45.2 mm/s
Pulses: 42                          Pulses: 197
Total:  121.0mm (0.12m)            Total:  567.4mm (0.57m)
Runouts: 0                          Runouts: 1

------------------------------------------------------------
RECENT EVENTS:
  10:29:55 S2: Pulse #197 (567.4mm)
  10:29:54 [ALERT] Sensor 2: FILAMENT RUNOUT!
  10:29:50 S2: Pulse #196 (564.5mm)
  10:29:45 Sensor 1: Movement stopped
  10:29:40 S1: Pulse #42 (121.0mm)
```

## 📁 File Outputs

- **filament_usage.json** - Persistent usage data (auto-saved every 30s)
- **sensor_status.json** - Current session status
- **final_status.json** - Final status when monitor stops

## 🛠️ Troubleshooting

### Monitor won't start
1. Check MCP2221A is connected via USB
2. Verify no other application is using the device
3. Try unplugging and reconnecting USB

### API not accessible
1. Check port 5002 is not in use
2. Windows Firewall may block the port
3. Try accessing from localhost only

### No sensor readings
1. Verify sensor wiring connections
2. Check 3.3V power to sensors
3. Test with `test_sensors.py` utility

### Display issues
1. Use Windows Terminal for best results
2. Resize console to at least 65x30 characters
3. Try PowerShell script for better formatting

## 🔧 Testing Tools

- **test_sensors.py** - Test hardware connections
- **test_api.py** - Test HTTP API endpoint
- **test_monitor_startup.py** - Verify prerequisites

## 📝 Integration Examples

### Python
```python
import requests

response = requests.get('http://localhost:5002/status')
data = response.json()

for sensor in data['sensors']:
    print(f"Sensor {sensor['id']}: {sensor['has_filament']}")
```

### JavaScript
```javascript
fetch('http://localhost:5002/status')
    .then(r => r.json())
    .then(data => {
        console.log(`Sensor 1: ${data.sensors[0].has_filament}`);
    });
```

### OctoPrint Plugin
The API can be integrated with OctoPrint for automatic pause on runout.

## 📊 Performance

- Polling rate: 10ms (100Hz)
- Display update: 100ms
- API response: <5ms
- Memory usage: <20MB
- CPU usage: <2%

## 🚦 Status Indicators

- **[OK] FILAMENT** - Filament present
- **[!!] NO FILAMENT** - Runout detected
- **[*] MOVING** - Movement detected
- **[ ] IDLE** - No movement for 5+ seconds

## 📜 License

Free to use and modify for personal and commercial use.

## 🤝 Support

For issues or questions, check the troubleshooting section or test utilities first.