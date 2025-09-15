#!/usr/bin/env python3
"""
Simple test of MCP2221A GPIO reading for filament sensors.
"""

import time
import EasyMCP2221

print("MCP2221A Filament Sensor Test")
print("=" * 40)

# Connect to MCP2221A
try:
    mcp = EasyMCP2221.Device()
    print("[OK] Connected to MCP2221A")
except Exception as e:
    print(f"[ERROR] Could not connect: {e}")
    exit(1)

# Configure GPIO pins as inputs
print("\nConfiguring GPIO pins...")
try:
    mcp.set_pin_function(gp0='GPIO_IN', gp1='GPIO_IN', gp2='GPIO_IN', gp3='GPIO_IN')
    print("[OK] GPIO pins configured as inputs")
except Exception as e:
    print(f"[ERROR] Failed to configure: {e}")

# Read initial state
print("\nInitial GPIO states:")
try:
    gpio = mcp.GPIO_read()
    print(f"  GP0 (S1 Movement): {gpio.get('GP0', {}).get('value', '?')}")
    print(f"  GP1 (S1 Runout):   {gpio.get('GP1', {}).get('value', '?')}")
    print(f"  GP2 (S2 Movement): {gpio.get('GP2', {}).get('value', '?')}")
    print(f"  GP3 (S2 Runout):   {gpio.get('GP3', {}).get('value', '?')}")
except Exception as e:
    print(f"[ERROR] Could not read GPIO: {e}")

# Monitor for changes
print("\n" + "=" * 40)
print("MONITORING FOR 30 SECONDS")
print("Pull filament through sensors to test")
print("=" * 40 + "\n")

last = [None, None, None, None]
pulses = [0, 0]
start = time.time()

try:
    while time.time() - start < 30:
        try:
            gpio = mcp.GPIO_read()
            current = [
                gpio.get('GP0', {}).get('value'),
                gpio.get('GP1', {}).get('value'),
                gpio.get('GP2', {}).get('value'),
                gpio.get('GP3', {}).get('value')
            ]

            # Check for changes
            for i in range(4):
                if current[i] is not None and last[i] is not None:
                    if current[i] != last[i]:
                        names = ["S1 Move", "S1 Runout", "S2 Move", "S2 Runout"]

                        # Movement pins - count falling edges
                        if i in [0, 2] and last[i] == 1 and current[i] == 0:
                            sensor = 1 if i == 0 else 2
                            pulses[sensor - 1] += 1
                            mm = pulses[sensor - 1] * 2.88
                            print(f"[PULSE] Sensor {sensor}: #{pulses[sensor - 1]} ({mm:.1f}mm)")

                        # Runout pins - report state
                        elif i in [1, 3]:
                            sensor = 1 if i == 1 else 2
                            if current[i] == 1:
                                print(f"[ALERT] Sensor {sensor}: RUNOUT DETECTED!")
                            else:
                                print(f"[INFO] Sensor {sensor}: Filament present")

            last = current
            time.sleep(0.01)

        except:
            pass

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user")

# Summary
print("\n" + "=" * 40)
print("SUMMARY")
print("=" * 40)
print(f"Sensor 1: {pulses[0]} pulses ({pulses[0] * 2.88:.1f}mm)")
print(f"Sensor 2: {pulses[1]} pulses ({pulses[1] * 2.88:.1f}mm)")

# Final state
try:
    gpio = mcp.GPIO_read()
    print("\nFinal GPIO states:")
    print(f"  GP0: {gpio.get('GP0', {}).get('value', '?')}")
    print(f"  GP1: {gpio.get('GP1', {}).get('value', '?')}")
    print(f"  GP2: {gpio.get('GP2', {}).get('value', '?')}")
    print(f"  GP3: {gpio.get('GP3', {}).get('value', '?')}")
except:
    pass

print("\n[OK] Test complete")