#!/usr/bin/env python3
"""
Test monitor startup and basic functionality
"""

import EasyMCP2221
import time
import json
import os
from pathlib import Path

print("Testing MCP2221A connection for monitor...")

try:
    # Test basic connection
    mcp = EasyMCP2221.Device()
    print("[OK] Connected to MCP2221A")

    # Configure GPIO
    mcp.set_pin_function(
        gp0='GPIO_IN',
        gp1='GPIO_IN',
        gp2='GPIO_IN',
        gp3='GPIO_IN'
    )
    print("[OK] GPIO configured")

    # Read GPIO
    gpio = mcp.GPIO_read()
    print(f"[OK] GPIO read: {gpio}")

    # Test HTTP server
    print("\nTesting HTTP server...")
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class TestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            pass

    server = HTTPServer(('0.0.0.0', 5002), TestHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    time.sleep(1)
    print("[OK] HTTP server can bind to port 5002")

    # Test persistent storage
    print("\nTesting persistent storage...")
    test_file = "test_filament_usage.json"
    test_data = {
        "sensor_1": {
            "total_pulses": 100,
            "total_distance_mm": 288.0
        },
        "sensor_2": {
            "total_pulses": 200,
            "total_distance_mm": 576.0
        },
        "last_saved": "2025-01-15T10:00:00"
    }

    # Test write
    with open(test_file, 'w') as f:
        json.dump(test_data, f, indent=2)
    print(f"[OK] Can write JSON file: {test_file}")

    # Test read
    with open(test_file, 'r') as f:
        loaded = json.load(f)
    if loaded == test_data:
        print("[OK] Can read and parse JSON file")
    else:
        print("[WARNING] JSON data mismatch")

    # Clean up
    os.remove(test_file)
    print("[OK] File operations working")

    print("\n[SUCCESS] All tests passed - monitor should work")

except Exception as e:
    print(f"[ERROR] Test failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check MCP2221A is connected")
    print("2. Check no other app is using the device")
    print("3. Check port 5002 is not in use")
    print("4. Check write permissions in current directory")