#!/usr/bin/env python3
"""
MCP2221A Filament Sensor Test with correct pin mapping:
- GP0: Sensor 1 Motion (movement detection)
- GP1: Sensor 1 Runout (filament presence)
- GP2: Sensor 2 Motion (movement detection)
- GP3: Sensor 2 Runout (filament presence)
"""

import time
import EasyMCP2221

print("MCP2221A Filament Sensor Test")
print("=" * 50)
print("Pin Mapping:")
print("  GP0 = Sensor 1 Motion")
print("  GP1 = Sensor 1 Runout")
print("  GP2 = Sensor 2 Motion")
print("  GP3 = Sensor 2 Runout")
print("=" * 50)

# Connect to MCP2221A
try:
    mcp = EasyMCP2221.Device()
    print("[OK] Connected to MCP2221A")
except Exception as e:
    print(f"[ERROR] Could not connect: {e}")
    exit(1)

# Configure GPIO pins as inputs
print("\nConfiguring GPIO pins as inputs...")
try:
    mcp.set_pin_function(gp0='GPIO_IN', gp1='GPIO_IN', gp2='GPIO_IN', gp3='GPIO_IN')
    print("[OK] All GPIO pins configured")
except Exception as e:
    print(f"[ERROR] Configuration failed: {e}")

# First, let's see what GPIO_read() actually returns
print("\nChecking GPIO read format...")
try:
    result = mcp.GPIO_read()
    print(f"GPIO_read() returns type: {type(result)}")
    if isinstance(result, tuple):
        print(f"  Tuple length: {len(result)}")
        for i, val in enumerate(result):
            print(f"  Index {i}: {val}")
    elif isinstance(result, dict):
        print(f"  Dictionary keys: {result.keys()}")
    else:
        print(f"  Raw value: {result}")
except Exception as e:
    print(f"[ERROR] GPIO read failed: {e}")

print("\n" + "=" * 50)
print("MONITORING SENSORS (30 seconds)")
print("Actions to test:")
print("  1. Pull filament through sensor 1 - should see motion pulses")
print("  2. Pull filament through sensor 2 - should see motion pulses")
print("  3. Remove filament from sensor 1 - should see runout")
print("  4. Remove filament from sensor 2 - should see runout")
print("=" * 50 + "\n")

# Initialize tracking variables
last_values = [None, None, None, None]
pulse_counts = [0, 0]  # For sensor 1 and 2
start_time = time.time()

try:
    while time.time() - start_time < 30:
        try:
            # Read GPIO - handle both tuple and dict formats
            gpio_raw = mcp.GPIO_read()

            if isinstance(gpio_raw, tuple) and len(gpio_raw) >= 4:
                # If it returns a tuple, use indices
                current_values = list(gpio_raw[:4])
            elif isinstance(gpio_raw, dict):
                # If it returns a dict, extract values
                current_values = [
                    gpio_raw.get('GP0', {}).get('value'),
                    gpio_raw.get('GP1', {}).get('value'),
                    gpio_raw.get('GP2', {}).get('value'),
                    gpio_raw.get('GP3', {}).get('value')
                ]
            else:
                # Unknown format, skip
                continue

            # Check for changes on each pin
            for pin in range(4):
                if current_values[pin] is not None and last_values[pin] is not None:
                    if current_values[pin] != last_values[pin]:
                        # Determine which sensor and what type
                        if pin == 0:  # Sensor 1 Motion
                            if last_values[pin] == 1 and current_values[pin] == 0:
                                pulse_counts[0] += 1
                                distance = pulse_counts[0] * 2.88
                                print(f"[MOTION] Sensor 1: Pulse #{pulse_counts[0]} ({distance:.1f}mm total)")

                        elif pin == 1:  # Sensor 1 Runout
                            if current_values[pin] == 1:
                                print(f"[RUNOUT] Sensor 1: NO FILAMENT DETECTED!")
                            else:
                                print(f"[OK] Sensor 1: Filament present")

                        elif pin == 2:  # Sensor 2 Motion
                            if last_values[pin] == 1 and current_values[pin] == 0:
                                pulse_counts[1] += 1
                                distance = pulse_counts[1] * 2.88
                                print(f"[MOTION] Sensor 2: Pulse #{pulse_counts[1]} ({distance:.1f}mm total)")

                        elif pin == 3:  # Sensor 2 Runout
                            if current_values[pin] == 1:
                                print(f"[RUNOUT] Sensor 2: NO FILAMENT DETECTED!")
                            else:
                                print(f"[OK] Sensor 2: Filament present")

            last_values = current_values
            time.sleep(0.01)  # 10ms polling

        except Exception as e:
            # Continue monitoring even if there's an error
            pass

except KeyboardInterrupt:
    print("\n[INFO] Monitoring stopped by user")

# Print summary
elapsed = time.time() - start_time
print("\n" + "=" * 50)
print("MONITORING SUMMARY")
print("=" * 50)
print(f"Duration: {elapsed:.1f} seconds")
print(f"\nSensor 1:")
print(f"  Motion pulses: {pulse_counts[0]}")
print(f"  Distance: {pulse_counts[0] * 2.88:.1f}mm")
print(f"  Average speed: {(pulse_counts[0] * 2.88 / elapsed):.1f}mm/s" if elapsed > 0 else "  Average speed: 0mm/s")

print(f"\nSensor 2:")
print(f"  Motion pulses: {pulse_counts[1]}")
print(f"  Distance: {pulse_counts[1] * 2.88:.1f}mm")
print(f"  Average speed: {(pulse_counts[1] * 2.88 / elapsed):.1f}mm/s" if elapsed > 0 else "  Average speed: 0mm/s")

# Check final state
print("\nFinal sensor states:")
try:
    gpio_raw = mcp.GPIO_read()
    if isinstance(gpio_raw, tuple) and len(gpio_raw) >= 4:
        values = gpio_raw[:4]
    else:
        values = [None, None, None, None]

    print(f"  Sensor 1 - Motion (GP0): {'Moving' if values[0] == 0 else 'Idle'}")
    print(f"  Sensor 1 - Runout (GP1): {'NO FILAMENT' if values[1] == 1 else 'Filament OK'}")
    print(f"  Sensor 2 - Motion (GP2): {'Moving' if values[2] == 0 else 'Idle'}")
    print(f"  Sensor 2 - Runout (GP3): {'NO FILAMENT' if values[3] == 1 else 'Filament OK'}")
except:
    print("  [Could not read final state]")

print("\n[DONE] Test complete")