"""
Contract tests for GET /status endpoint.

Tests the API contract for the status endpoint which should return
current sensor states, connection status, and real-time readings.
"""
import pytest
import httpx
from typing import Dict, Any
from datetime import datetime


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_returns_valid_schema():
    """Test that GET /status returns StatusResponse schema."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/status")

        assert response.status_code == 200
        data = response.json()

        # Validate StatusResponse schema
        assert "timestamp" in data
        assert "system_status" in data
        assert "sensors" in data
        assert "connection" in data

        # Validate timestamp format (ISO 8601)
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        # Validate system_status
        system_status = data["system_status"]
        assert system_status["status"] in ["running", "stopped", "error"]
        assert isinstance(system_status["uptime_seconds"], (int, float))
        assert "polling_interval_ms" in system_status

        # Validate sensors array (should have 2 sensors)
        sensors = data["sensors"]
        assert isinstance(sensors, list)
        assert len(sensors) == 2

        for i, sensor in enumerate(sensors):
            assert sensor["id"] == f"sensor_{i+1}"
            assert sensor["name"] in [f"Sensor {i+1}", f"sensor_{i+1}"]
            assert sensor["status"] in ["active", "inactive", "error"]
            assert "filament_present" in sensor
            assert isinstance(sensor["filament_present"], bool)
            assert "movement_detected" in sensor
            assert isinstance(sensor["movement_detected"], bool)
            assert "total_usage_mm" in sensor
            assert isinstance(sensor["total_usage_mm"], (int, float))
            assert "last_movement" in sensor
            if sensor["last_movement"] is not None:
                datetime.fromisoformat(sensor["last_movement"].replace("Z", "+00:00"))

        # Validate connection
        connection = data["connection"]
        assert "mcp2221_connected" in connection
        assert isinstance(connection["mcp2221_connected"], bool)
        assert "device_serial" in connection
        assert "gpio_status" in connection

        gpio_status = connection["gpio_status"]
        assert len(gpio_status) == 4  # GP0-GP3
        for gpio in gpio_status:
            assert gpio["pin"] in ["GP0", "GP1", "GP2", "GP3"]
            assert gpio["function"] in ["movement", "runout"]
            assert gpio["sensor_id"] in ["sensor_1", "sensor_2"]
            assert isinstance(gpio["value"], bool)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_error_when_service_down():
    """Test that status endpoint returns error when service is not running."""
    # This test should fail initially since no service is running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.get("http://localhost:5002/status")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_content_type():
    """Test that status endpoint returns correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/status")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_cors_headers():
    """Test that status endpoint includes CORS headers."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/status")

        assert response.status_code == 200
        # CORS headers should be present for web client access
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_response_time():
    """Test that status endpoint responds within performance target (<5ms)."""
    import time

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get("http://localhost:5002/status")
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        assert response.status_code == 200
        assert response_time < 5.0, f"Response time {response_time:.2f}ms exceeds 5ms target"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_sensor_states():
    """Test that status endpoint returns all possible sensor states."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/status")

        assert response.status_code == 200
        data = response.json()

        # Test that sensor status can handle all valid states
        for sensor in data["sensors"]:
            assert sensor["status"] in ["active", "inactive", "error"]

            # Filament presence should be boolean
            assert isinstance(sensor["filament_present"], bool)

            # Movement detection should be boolean
            assert isinstance(sensor["movement_detected"], bool)

            # Usage should be non-negative number
            assert sensor["total_usage_mm"] >= 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_status_endpoint_mcp2221_connection():
    """Test that status endpoint reports MCP2221A connection status correctly."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/status")

        assert response.status_code == 200
        data = response.json()

        connection = data["connection"]

        # When MCP2221A is connected
        if connection["mcp2221_connected"]:
            assert connection["device_serial"] is not None
            assert isinstance(connection["device_serial"], str)
            assert len(connection["device_serial"]) > 0

            # GPIO status should be available
            assert len(connection["gpio_status"]) == 4

        # When MCP2221A is disconnected
        else:
            # Device serial might be null or cached value
            # GPIO status should reflect disconnected state
            for gpio in connection["gpio_status"]:
                # GPIO values might be None or False when disconnected
                assert gpio["value"] in [True, False, None]