"""
Contract tests for the MCP2221A Filament Sensor Monitor API.

These tests verify that the API endpoints conform to their OpenAPI contracts
and handle both success and error cases correctly. All tests are designed to
fail initially (TDD approach) until the actual API implementation is created.

Test Categories:
- Status endpoint: Real-time sensor states and system status
- Configuration endpoint: System configuration retrieval and updates
- Alerts endpoint: System alerts with filtering capabilities
- Metrics endpoint: Session metrics and performance statistics

Usage:
    pytest tests/contract/ -m contract
    pytest tests/contract/test_status_endpoint.py::test_status_endpoint_returns_valid_schema
"""