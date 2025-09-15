"""
Integration tests for the MCP2221A filament sensor system.

This package contains integration tests that validate hardware interfaces,
sensor monitoring, configuration management, and system integration points.

Test Categories:
- Hardware Interface: MCP2221A USB device and GPIO configuration
- Dual Sensors: Simultaneous monitoring of two filament sensors
- Pulse Detection: Edge detection, debouncing, and movement calculation
- Runout Detection: Filament presence/absence and state management
- Configuration: YAML persistence, validation, and migration

All tests follow TDD principles and will initially fail until
the corresponding implementation modules are created.
"""

# Integration test configuration
INTEGRATION_TEST_CONFIG = {
    "hardware_simulation": True,
    "mock_gpio_responses": True,
    "test_timeout_seconds": 30,
    "temp_config_cleanup": True,
    "thread_safety_tests": True
}