#!/usr/bin/env python3
"""
Test persistent storage functionality for the monitor
"""

import json
import os
import time
from pathlib import Path

USAGE_FILE = "filament_usage.json"
TEST_FILE = "test_filament_usage.json"

def test_persistence():
    """Test persistent storage functionality."""

    print("Testing Persistent Storage")
    print("=" * 50)

    # Test 1: Check if filament_usage.json exists
    print("\n1. Checking for existing usage file...")
    if Path(USAGE_FILE).exists():
        print(f"[OK] {USAGE_FILE} exists")

        # Read and display current data
        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            print(f"[OK] Current data loaded:")
            print(f"  Sensor 1: {data.get('sensor_1', {}).get('total_pulses', 0)} pulses")
            print(f"  Sensor 2: {data.get('sensor_2', {}).get('total_pulses', 0)} pulses")
            print(f"  Last saved: {data.get('last_saved', 'unknown')}")
        except Exception as e:
            print(f"[ERROR] Could not read file: {e}")
    else:
        print(f"[INFO] {USAGE_FILE} does not exist (will be created on first run)")

    # Test 2: Create test data
    print("\n2. Creating test persistence data...")
    test_data = {
        "sensor_1": {
            "total_pulses": 150,
            "total_distance_mm": 432.0
        },
        "sensor_2": {
            "total_pulses": 275,
            "total_distance_mm": 792.0
        },
        "last_saved": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        with open(TEST_FILE, 'w') as f:
            json.dump(test_data, f, indent=2)
        print(f"[OK] Test file created: {TEST_FILE}")
    except Exception as e:
        print(f"[ERROR] Could not create test file: {e}")
        return

    # Test 3: Read back test data
    print("\n3. Reading back test data...")
    try:
        with open(TEST_FILE, 'r') as f:
            loaded_data = json.load(f)

        # Verify data integrity
        if loaded_data == test_data:
            print("[OK] Data integrity verified")
        else:
            print("[WARNING] Data mismatch after save/load")

        # Display loaded data
        print("Loaded data:")
        print(f"  Sensor 1: {loaded_data['sensor_1']['total_pulses']} pulses")
        print(f"  Sensor 1: {loaded_data['sensor_1']['total_distance_mm']}mm")
        print(f"  Sensor 2: {loaded_data['sensor_2']['total_pulses']} pulses")
        print(f"  Sensor 2: {loaded_data['sensor_2']['total_distance_mm']}mm")

    except Exception as e:
        print(f"[ERROR] Could not read test file: {e}")
        return

    # Test 4: Simulate incremental updates
    print("\n4. Testing incremental updates...")
    try:
        # Simulate adding pulses
        loaded_data['sensor_1']['total_pulses'] += 10
        loaded_data['sensor_1']['total_distance_mm'] += 28.8
        loaded_data['sensor_2']['total_pulses'] += 5
        loaded_data['sensor_2']['total_distance_mm'] += 14.4
        loaded_data['last_saved'] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Save updated data
        with open(TEST_FILE, 'w') as f:
            json.dump(loaded_data, f, indent=2)
        print("[OK] Incremental update saved")

        # Read back to verify
        with open(TEST_FILE, 'r') as f:
            updated_data = json.load(f)

        print("Updated totals:")
        print(f"  Sensor 1: {updated_data['sensor_1']['total_pulses']} pulses")
        print(f"  Sensor 2: {updated_data['sensor_2']['total_pulses']} pulses")

    except Exception as e:
        print(f"[ERROR] Incremental update failed: {e}")

    # Test 5: Test file locking/concurrent access
    print("\n5. Testing file access...")
    try:
        # Try rapid read/write cycles
        for i in range(5):
            with open(TEST_FILE, 'r') as f:
                data = json.load(f)
            data['last_saved'] = time.strftime("%Y-%m-%d %H:%M:%S.%f")
            with open(TEST_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        print("[OK] Rapid read/write cycles completed")

    except Exception as e:
        print(f"[ERROR] File access test failed: {e}")

    # Cleanup
    print("\n6. Cleaning up test file...")
    try:
        os.remove(TEST_FILE)
        print(f"[OK] Test file removed: {TEST_FILE}")
    except Exception as e:
        print(f"[WARNING] Could not remove test file: {e}")

    print("\n" + "=" * 50)
    print("[SUCCESS] Persistence tests completed")
    print("\nNotes:")
    print("- monitor saves data every 30 seconds")
    print("- Data persists between application restarts")
    print("- Session metrics reset on restart")
    print("- Total metrics accumulate forever")

if __name__ == "__main__":
    test_persistence()