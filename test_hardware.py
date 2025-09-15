#!/usr/bin/env python3
"""
Simple hardware test script for MCP2221A filament sensors.
Tests the basic connection and sensor reading without full application dependencies.
"""

import sys
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mcp2221_connection():
    """Test basic MCP2221A connection and GPIO setup."""
    try:
        # Try to import EasyMCP2221
        try:
            import EasyMCP2221
            logger.info("✓ EasyMCP2221 library imported successfully")
        except ImportError as e:
            logger.error(f"✗ Failed to import EasyMCP2221: {e}")
            logger.info("Install with: pip install EasyMCP2221")
            return False

        # Try to connect to MCP2221A
        try:
            mcp = EasyMCP2221.Device()
            logger.info("✓ Connected to MCP2221A device")
        except Exception as e:
            logger.error(f"✗ Failed to connect to MCP2221A: {e}")
            logger.info("Please check:")
            logger.info("  - MCP2221A is connected via USB")
            logger.info("  - Device drivers are installed")
            logger.info("  - No other application is using the device")
            return False

        # Get device info
        try:
            # Try to read manufacturer string (may not be available)
            logger.info(f"Device info:")
            logger.info(f"  - VID: 0x04D8")
            logger.info(f"  - PID: 0x00DD")
        except:
            pass

        # Configure GPIO pins as inputs with pull-ups
        logger.info("\nConfiguring GPIO pins...")
        gpio_config = {
            0: "Sensor 1 Movement",
            1: "Sensor 1 Runout",
            2: "Sensor 2 Movement",
            3: "Sensor 2 Runout"
        }

        for pin, description in gpio_config.items():
            try:
                # Configure as GPIO input with pull-up
                setattr(mcp, f'GP{pin}', 1)  # Set as input
                logger.info(f"  ✓ GP{pin} configured as input ({description})")
            except Exception as e:
                logger.warning(f"  ⚠ Could not configure GP{pin}: {e}")

        return mcp

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def monitor_sensors(mcp, duration=10):
    """Monitor sensor states for specified duration."""
    logger.info(f"\nMonitoring sensors for {duration} seconds...")
    logger.info("Pull filament through sensors to test movement detection")
    logger.info("Remove filament to test runout detection\n")

    start_time = time.time()
    last_states = [None, None, None, None]
    pulse_counts = [0, 0]  # Movement pulse counts for sensor 1 and 2

    try:
        while time.time() - start_time < duration:
            # Read all GPIO pins
            states = []
            for pin in range(4):
                try:
                    # Read pin state (1 = high/no filament, 0 = low/filament present)
                    state = getattr(mcp, f'GP{pin}', None)
                    if state is not None:
                        state = state.read()
                    states.append(state)
                except:
                    states.append(None)

            # Check for changes
            for i, (current, last) in enumerate(zip(states, last_states)):
                if current is not None and current != last:
                    pin_name = ["S1 Movement", "S1 Runout", "S2 Movement", "S2 Runout"][i]

                    # Movement pins (0 and 2) - count falling edges as pulses
                    if i in [0, 2] and last == 1 and current == 0:
                        sensor_num = 1 if i == 0 else 2
                        pulse_counts[sensor_num - 1] += 1
                        distance_mm = pulse_counts[sensor_num - 1] * 2.88
                        logger.info(f"  → Sensor {sensor_num} pulse #{pulse_counts[sensor_num - 1]} "
                                  f"(~{distance_mm:.2f}mm total)")

                    # Runout pins (1 and 3) - report state changes
                    elif i in [1, 3]:
                        sensor_num = 1 if i == 1 else 2
                        state_text = "RUNOUT DETECTED" if current == 1 else "Filament Present"
                        symbol = "⚠" if current == 1 else "✓"
                        logger.info(f"  {symbol} Sensor {sensor_num}: {state_text}")

                    # General state change
                    state_text = "HIGH" if current == 1 else "LOW"
                    logger.debug(f"  {pin_name}: {last} → {current} ({state_text})")

            last_states = states
            time.sleep(0.01)  # 10ms polling interval

    except KeyboardInterrupt:
        logger.info("\nMonitoring stopped by user")

    # Summary
    logger.info(f"\n📊 Summary:")
    logger.info(f"  Sensor 1: {pulse_counts[0]} pulses (~{pulse_counts[0] * 2.88:.2f}mm)")
    logger.info(f"  Sensor 2: {pulse_counts[1]} pulses (~{pulse_counts[1] * 2.88:.2f}mm)")

def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("MCP2221A Filament Sensor Hardware Test")
    logger.info("=" * 60)

    # Test connection
    mcp = test_mcp2221_connection()
    if not mcp:
        logger.error("\n❌ Hardware test failed - cannot connect to MCP2221A")
        return 1

    logger.info("\n✅ Hardware connection successful!")

    # Monitor sensors
    try:
        logger.info("\nStarting sensor monitoring...")
        logger.info("Press Ctrl+C to stop\n")

        # Initial state reading
        logger.info("Initial GPIO states:")
        for pin in range(4):
            try:
                gpio_pin = getattr(mcp, f'GP{pin}', None)
                if gpio_pin is not None:
                    state = gpio_pin.read()
                else:
                    state = None

                if state is not None:
                    pin_name = ["S1 Movement", "S1 Runout", "S2 Movement", "S2 Runout"][pin]
                    state_text = "HIGH (no signal)" if state == 1 else "LOW (signal present)"
                    logger.info(f"  GP{pin} ({pin_name}): {state_text}")
                else:
                    logger.warning(f"  GP{pin}: Could not read")
            except Exception as e:
                logger.warning(f"  GP{pin}: Could not read - {e}")

        # Monitor for changes
        monitor_sensors(mcp, duration=30)

    except Exception as e:
        logger.error(f"\n❌ Error during monitoring: {e}")
        return 1

    logger.info("\n✅ Hardware test completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())