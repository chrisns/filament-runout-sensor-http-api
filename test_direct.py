#!/usr/bin/env python3
"""
Direct test of MCP2221A GPIO reading using EasyMCP2221.
"""

import time
import EasyMCP2221

# Connect to MCP2221A
mcp = EasyMCP2221.Device()
print(f"Connected to MCP2221A")

# Try to get device info
try:
    print(f"  VID: 0x04D8")
    print(f"  PID: 0x00DD")
except:
    pass
print()

# Configure all GPIO pins as inputs
print("Configuring GPIO pins as inputs...")
try:
    # Set all pins as GPIO inputs
    mcp.set_pin_function(gp0='GPIO_IN', gp1='GPIO_IN', gp2='GPIO_IN', gp3='GPIO_IN')
    print("  ✓ All GPIO pins configured as inputs")
except Exception as e:
    print(f"  ✗ Error configuring pins: {e}")
print()

# Test reading GPIO values
print("Testing GPIO read...")
try:
    gpio_values = mcp.GPIO_read()
    print(f"  GPIO read successful: {gpio_values}")
    for pin in ['GP0', 'GP1', 'GP2', 'GP3']:
        if pin in gpio_values:
            value = gpio_values[pin].get('value', 'unknown')
            direction = 'INPUT' if gpio_values[pin].get('direction', 0) else 'OUTPUT'
            print(f"    {pin}: value={value}, direction={direction}")
except Exception as e:
    print(f"  ✗ Error reading GPIO: {e}")
print()

# Monitor GPIO states
print("Monitoring GPIO pins for 20 seconds...")
print("GP0: Sensor 1 Movement | GP1: Sensor 1 Runout")
print("GP2: Sensor 2 Movement | GP3: Sensor 2 Runout")
print("-" * 50)

last_values = [None, None, None, None]
pulse_counts = [0, 0]
start_time = time.time()

try:
    while time.time() - start_time < 20:
        try:
            # Read all GPIO pins
            gpio_state = mcp.GPIO_read()
            values = [
                gpio_state.get('GP0', {}).get('value'),
                gpio_state.get('GP1', {}).get('value'),
                gpio_state.get('GP2', {}).get('value'),
                gpio_state.get('GP3', {}).get('value')
            ]

            # Check for changes
            for i, (current, last) in enumerate(zip(values, last_values)):
                if current is not None and last is not None and current != last:
                    pin_names = ["S1 Movement", "S1 Runout", "S2 Movement", "S2 Runout"]

                    # Movement pins - detect falling edge (1→0 transition)
                    if i in [0, 2] and last == 1 and current == 0:
                        sensor_num = 1 if i == 0 else 2
                        pulse_counts[sensor_num - 1] += 1
                        distance_mm = pulse_counts[sensor_num - 1] * 2.88
                        print(f"  → PULSE on {pin_names[i]}: #{pulse_counts[sensor_num - 1]} (~{distance_mm:.2f}mm)")

                    # Runout pins - report state changes
                    elif i in [1, 3]:
                        state = "RUNOUT DETECTED!" if current == 1 else "Filament Present"
                        print(f"  → {pin_names[i]}: {state} (GPIO={current})")

            last_values = values

        except Exception as e:
            # Silently continue on read errors
            pass

        time.sleep(0.01)  # 10ms polling

except KeyboardInterrupt:
    print("\nStopped by user")

print()
print(f"Summary:")
print(f"  Sensor 1: {pulse_counts[0]} pulses (~{pulse_counts[0] * 2.88:.2f}mm)")
print(f"  Sensor 2: {pulse_counts[1]} pulses (~{pulse_counts[1] * 2.88:.2f}mm)")
print()

# Final GPIO state
try:
    print("Final GPIO states:")
    gpio_state = mcp.GPIO_read()
    for pin in ['GP0', 'GP1', 'GP2', 'GP3']:
        if pin in gpio_state:
            value = gpio_state[pin].get('value', 'unknown')
            print(f"  {pin}: {value}")
except Exception as e:
    print(f"  Error reading final state: {e}")