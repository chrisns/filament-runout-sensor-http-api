#!/usr/bin/env python3
"""
Test the HTTP API endpoint for the filament monitor
"""

import requests
import json
import time

def test_api():
    """Test the API endpoint."""
    url = "http://localhost:5002/status"

    print("Testing API endpoint...")
    print(f"URL: {url}")
    print("-" * 40)

    try:
        # Try to connect to the API
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            print("[OK] API is responding")
            print("\nResponse:")
            data = response.json()
            print(json.dumps(data, indent=2))

            # Check sensor data
            print("\n" + "-" * 40)
            print("Sensor Summary:")
            for sensor in data.get('sensors', []):
                print(f"\nSensor {sensor['id']}:")
                print(f"  Has filament: {sensor['has_filament']}")
                print(f"  Is moving: {sensor['is_moving']}")

                # Session metrics
                print(f"  Session usage: {sensor['session_usage_meters']:.3f}m")
                print(f"  Session pulses: {sensor['session_pulse_count']}")

                # Total metrics (persistent)
                print(f"  Total usage: {sensor['total_usage_meters']:.3f}m")
                print(f"  Total pulses: {sensor['total_pulse_count']}")

                # Other metrics
                print(f"  Speed: {sensor.get('speed_mm_per_s', 0):.1f}mm/s")
                print(f"  Runout events: {sensor.get('runout_events', 0)}")

            # Check system info
            if 'system' in data:
                print(f"\nSystem:")
                print(f"  Connected: {data['system'].get('connected', False)}")
                print(f"  Version: {data['system'].get('version', 'unknown')}")

            print(f"\nUptime: {data.get('uptime_seconds', 0)} seconds")
        else:
            print(f"[ERROR] API returned status code: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("[ERROR] Could not connect to API")
        print("Make sure monitor.py is running")
    except requests.exceptions.Timeout:
        print("[ERROR] API request timed out")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    test_api()