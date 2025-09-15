"""
CLI Interface for MCP2221 Sensor Library.

Provides command-line interface for testing and managing MCP2221A hardware
interface, including connection testing, GPIO monitoring, and pulse detection.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Any

from . import MCP2221Manager, GPIOState
from .pulse_detector import PulseDetector, create_sensor_pulse_detector
from .connection import ConnectionManager, create_mcp2221_connection_manager, ConnectionState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection() -> bool:
    """
    Test MCP2221A device connection and basic functionality.

    Returns:
        bool: True if all tests pass
    """
    print("=== MCP2221A Connection Test ===")
    print()

    # Test device detection
    print("1. Testing device detection...")
    manager = MCP2221Manager()

    if not manager.detect_device():
        print("❌ FAIL: MCP2221A device not detected")
        print("   Check that device is connected and drivers are installed")
        return False

    print("✅ PASS: MCP2221A device detected")
    device_info = manager.device_info
    print(f"   Device: VID={device_info['VID']:04X}, PID={device_info['PID']:04X}")
    print()

    # Test GPIO configuration
    print("2. Testing GPIO configuration...")
    test_config = {
        "sensor1": {
            "movement_pin": 0,
            "runout_pin": 1,
            "mm_per_pulse": 2.88,
            "debounce_ms": 2
        },
        "sensor2": {
            "movement_pin": 2,
            "runout_pin": 3,
            "mm_per_pulse": 2.88,
            "debounce_ms": 2
        },
        "polling_interval_ms": 100
    }

    try:
        manager.configure_gpio(test_config)
        print("✅ PASS: GPIO pins configured successfully")
    except Exception as e:
        print(f"❌ FAIL: GPIO configuration failed - {e}")
        return False

    print()

    # Test GPIO reading
    print("3. Testing GPIO state reading...")
    try:
        states = manager.read_gpio_states()
        print("✅ PASS: GPIO states read successfully")
        print(f"   Pin states: {states}")

        # Read structured state
        gpio_state = manager.read_gpio_state_object()
        print(f"   Structured state: {gpio_state}")
    except Exception as e:
        print(f"❌ FAIL: GPIO reading failed - {e}")
        return False

    print()

    # Test connection manager
    print("4. Testing connection manager...")
    try:
        conn_manager = create_mcp2221_connection_manager(manager)
        if conn_manager.connect():
            print("✅ PASS: Connection manager working")
            stats = conn_manager.get_stats()
            print(f"   Connection stats: {stats.success_rate:.2%} success rate")
        else:
            print("❌ FAIL: Connection manager failed")
            return False
    except Exception as e:
        print(f"❌ FAIL: Connection manager error - {e}")
        return False

    print()
    print("=== All Tests Passed ✅ ===")
    return True


def monitor_gpio(duration: int = 30, show_pulses: bool = False) -> None:
    """
    Monitor GPIO pins for state changes.

    Args:
        duration: Monitoring duration in seconds
        show_pulses: Whether to show pulse detection
    """
    print(f"=== GPIO Monitoring ({duration}s) ===")
    print()

    # Initialize hardware
    manager = MCP2221Manager()
    if not manager.detect_device():
        print("❌ MCP2221A device not detected")
        return

    # Configure for dual sensors
    config = {
        "sensor1": {"movement_pin": 0, "runout_pin": 1, "debounce_ms": 2},
        "sensor2": {"movement_pin": 2, "runout_pin": 3, "debounce_ms": 2}
    }

    try:
        manager.configure_gpio(config)
        print("GPIO pins configured for monitoring")
        print("Sensor 1: Movement=GP0, Runout=GP1")
        print("Sensor 2: Movement=GP2, Runout=GP3")
        print("(1=High/Present, 0=Low/Triggered)")
        print()
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return

    # Setup pulse detection if requested
    pulse_detector = None
    if show_pulses:
        pulse_detector = create_sensor_pulse_detector([0, 2], debounce_ms=2)

        def pulse_callback(event):
            print(f"   PULSE: Pin {event.pin} at {event.timestamp.strftime('%H:%M:%S.%f')[:-3]}")

        pulse_detector.register_pulse_callback(0, pulse_callback)
        pulse_detector.register_pulse_callback(2, pulse_callback)

        print("Pulse detection enabled (2ms debouncing)")
        print()

    # Monitor GPIO states
    start_time = time.time()
    last_states = None
    update_count = 0

    try:
        while (time.time() - start_time) < duration:
            try:
                # Read current states
                current_states = manager.read_gpio_states()
                current_time = datetime.now()

                # Check for changes
                if current_states != last_states:
                    print(f"[{current_time.strftime('%H:%M:%S.%f')[:-3]}] "
                          f"GP0={current_states['GP0']} GP1={current_states['GP1']} "
                          f"GP2={current_states['GP2']} GP3={current_states['GP3']}")

                    last_states = current_states.copy()
                    update_count += 1

                # Update pulse detector
                if pulse_detector:
                    pulse_detector.update_all_pins(current_states)

                # Brief pause
                time.sleep(0.01)  # 10ms polling

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                break

        print()
        print(f"Monitoring completed: {update_count} state changes detected")

        # Show pulse statistics
        if pulse_detector:
            print("\nPulse Statistics:")
            for pin in [0, 2]:
                stats = pulse_detector.get_statistics(pin)
                if stats:
                    sensor_name = "Sensor 1" if pin == 0 else "Sensor 2"
                    print(f"  {sensor_name}: {stats.debounced_pulses} pulses, "
                          f"{stats.pulse_rate_hz:.1f} Hz")

    except Exception as e:
        print(f"❌ Monitoring failed: {e}")


def device_info() -> None:
    """Display detailed device information."""
    print("=== MCP2221A Device Information ===")
    print()

    # Enumerate all devices
    print("1. Device Enumeration:")
    devices = MCP2221Manager.enumerate_devices()
    if not devices:
        print("   No MCP2221A devices found")
        return

    for i, device in enumerate(devices):
        print(f"   Device {i+1}:")
        print(f"     VID/PID: {device['vendor_id']:04X}:{device['product_id']:04X}")
        print(f"     Serial: {device['serial_number']}")
        print(f"     Path: {device['path']}")
    print()

    # Connect to first device and get details
    print("2. Device Details:")
    manager = MCP2221Manager()
    if manager.detect_device():
        info = manager.device_info
        print(f"   VID: 0x{info['VID']:04X}")
        print(f"   PID: 0x{info['PID']:04X}")
        print(f"   Connected: {info['connected']}")
        print(f"   Configured: {info['configured']}")
        print()

        # Test basic functionality
        print("3. Functionality Test:")
        try:
            test_config = {
                "sensor1": {"movement_pin": 0, "runout_pin": 1},
                "sensor2": {"movement_pin": 2, "runout_pin": 3}
            }
            manager.configure_gpio(test_config)

            states = manager.read_gpio_states()
            print(f"   GPIO States: {states}")
            print("   ✅ Device functioning correctly")

        except Exception as e:
            print(f"   ❌ Device test failed: {e}")
    else:
        print("   ❌ Failed to connect to device")


def pulse_test(duration: int = 10, pin: int = 0) -> None:
    """
    Test pulse detection on specific pin.

    Args:
        duration: Test duration in seconds
        pin: GPIO pin to monitor (0-3)
    """
    print(f"=== Pulse Detection Test (Pin {pin}, {duration}s) ===")
    print()

    if pin not in range(4):
        print(f"❌ Invalid pin number: {pin} (must be 0-3)")
        return

    # Initialize hardware
    manager = MCP2221Manager()
    if not manager.detect_device():
        print("❌ MCP2221A device not detected")
        return

    try:
        # Configure GPIO
        config = {"test_sensor": {"movement_pin": pin, "runout_pin": (pin + 1) % 4}}
        manager.configure_gpio(config)

        # Setup pulse detector
        detector = PulseDetector(debounce_ms=2)
        detector.register_pin(pin, initial_state=True)

        print(f"Monitoring pin {pin} for pulses...")
        print("Connect/disconnect signal to generate pulses")
        print("Press Ctrl+C to stop")
        print()

        start_time = time.time()
        pulse_count = 0

        def pulse_callback(event):
            nonlocal pulse_count
            pulse_count += 1
            print(f"Pulse #{pulse_count}: Pin {event.pin} at "
                  f"{event.timestamp.strftime('%H:%M:%S.%f')[:-3]} "
                  f"({event.previous_state} -> {event.current_state})")

        detector.register_pulse_callback(pin, pulse_callback)

        # Monitor for pulses
        while (time.time() - start_time) < duration:
            try:
                states = manager.read_gpio_states()
                detector.update_all_pins(states)
                time.sleep(0.001)  # 1ms polling
            except KeyboardInterrupt:
                break

        print()
        print(f"Test completed: {pulse_count} pulses detected")

        # Show statistics
        stats = detector.get_statistics(pin)
        if stats:
            print(f"Pulse rate: {stats.pulse_rate_hz:.2f} Hz")
            if stats.time_since_last_pulse:
                print(f"Time since last pulse: {stats.time_since_last_pulse.total_seconds():.3f}s")

    except Exception as e:
        print(f"❌ Pulse test failed: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MCP2221A Sensor Library CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Test connection command
    test_parser = subparsers.add_parser('test-connection', help='Test device connection')

    # Monitor GPIO command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor GPIO pins')
    monitor_parser.add_argument('--duration', '-d', type=int, default=30,
                               help='Monitoring duration in seconds (default: 30)')
    monitor_parser.add_argument('--pulses', '-p', action='store_true',
                               help='Enable pulse detection')

    # Device info command
    info_parser = subparsers.add_parser('info', help='Show device information')

    # Pulse test command
    pulse_parser = subparsers.add_parser('pulse-test', help='Test pulse detection')
    pulse_parser.add_argument('--duration', '-d', type=int, default=10,
                             help='Test duration in seconds (default: 10)')
    pulse_parser.add_argument('--pin', '-p', type=int, default=0,
                             help='GPIO pin to test (0-3, default: 0)')

    # Debug options
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode')

    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    # Execute commands
    if args.command == 'test-connection':
        success = test_connection()
        sys.exit(0 if success else 1)

    elif args.command == 'monitor':
        monitor_gpio(duration=args.duration, show_pulses=args.pulses)

    elif args.command == 'info':
        device_info()

    elif args.command == 'pulse-test':
        pulse_test(duration=args.duration, pin=args.pin)

    else:
        # Default behavior - show help and run connection test
        parser.print_help()
        print()
        print("Running default connection test...")
        print()
        success = test_connection()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()