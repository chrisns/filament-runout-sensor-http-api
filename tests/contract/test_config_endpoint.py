"""
Contract tests for GET /config endpoint.

Tests the API contract for the configuration endpoint which should return
current system configuration including polling intervals, sensor settings,
and calibration values.
"""
import pytest
import httpx
from typing import Dict, Any


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_returns_valid_schema():
    """Test that GET /config returns ConfigurationResponse schema."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        # Validate ConfigurationResponse schema
        assert "polling_interval_ms" in data
        assert "sensors" in data
        assert "thresholds" in data
        assert "calibration" in data
        assert "logging" in data

        # Validate polling_interval_ms
        polling_interval = data["polling_interval_ms"]
        assert isinstance(polling_interval, int)
        assert 10 <= polling_interval <= 10000  # Reasonable range

        # Validate sensors configuration
        sensors = data["sensors"]
        assert isinstance(sensors, list)
        assert len(sensors) == 2

        for i, sensor in enumerate(sensors):
            assert sensor["id"] == f"sensor_{i+1}"
            assert "name" in sensor
            assert "enabled" in sensor
            assert isinstance(sensor["enabled"], bool)
            assert "gpio_pins" in sensor

            gpio_pins = sensor["gpio_pins"]
            assert "movement" in gpio_pins
            assert "runout" in gpio_pins
            assert gpio_pins["movement"] in ["GP0", "GP1", "GP2", "GP3"]
            assert gpio_pins["runout"] in ["GP0", "GP1", "GP2", "GP3"]

        # Validate thresholds
        thresholds = data["thresholds"]
        assert "movement_timeout_ms" in thresholds
        assert "runout_debounce_ms" in thresholds
        assert isinstance(thresholds["movement_timeout_ms"], int)
        assert isinstance(thresholds["runout_debounce_ms"], int)
        assert thresholds["movement_timeout_ms"] > 0
        assert thresholds["runout_debounce_ms"] >= 0

        # Validate calibration
        calibration = data["calibration"]
        assert "mm_per_pulse" in calibration
        assert isinstance(calibration["mm_per_pulse"], (int, float))
        assert calibration["mm_per_pulse"] > 0

        # Validate logging
        logging_config = data["logging"]
        assert "level" in logging_config
        assert "structured" in logging_config
        assert logging_config["level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert isinstance(logging_config["structured"], bool)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_default_values():
    """Test that config endpoint returns expected default values."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        # Test default values match specification
        assert data["polling_interval_ms"] == 100  # Default from spec
        assert data["calibration"]["mm_per_pulse"] == 2.88  # Default from spec

        # Test default GPIO pin assignments
        sensor_1 = next(s for s in data["sensors"] if s["id"] == "sensor_1")
        sensor_2 = next(s for s in data["sensors"] if s["id"] == "sensor_2")

        assert sensor_1["gpio_pins"]["movement"] == "GP0"
        assert sensor_1["gpio_pins"]["runout"] == "GP1"
        assert sensor_2["gpio_pins"]["movement"] == "GP2"
        assert sensor_2["gpio_pins"]["runout"] == "GP3"

        # Both sensors should be enabled by default
        assert sensor_1["enabled"] is True
        assert sensor_2["enabled"] is True


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_error_when_service_down():
    """Test that config endpoint returns error when service is not running."""
    # This test should fail initially since no service is running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.get("http://localhost:5002/config")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_content_type():
    """Test that config endpoint returns correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_cors_headers():
    """Test that config endpoint includes CORS headers."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        # CORS headers should be present for web client access
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_response_time():
    """Test that config endpoint responds within performance target (<5ms)."""
    import time

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get("http://localhost:5002/config")
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        assert response.status_code == 200
        assert response_time < 5.0, f"Response time {response_time:.2f}ms exceeds 5ms target"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_sensor_names():
    """Test that config endpoint returns configurable sensor names."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        for sensor in data["sensors"]:
            assert "name" in sensor
            assert isinstance(sensor["name"], str)
            assert len(sensor["name"]) > 0  # Name should not be empty


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_gpio_pin_uniqueness():
    """Test that config endpoint ensures GPIO pins are uniquely assigned."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        # Collect all assigned GPIO pins
        assigned_pins = []
        for sensor in data["sensors"]:
            assigned_pins.append(sensor["gpio_pins"]["movement"])
            assigned_pins.append(sensor["gpio_pins"]["runout"])

        # All pins should be unique (no duplicates)
        assert len(assigned_pins) == len(set(assigned_pins)), "GPIO pins must be uniquely assigned"

        # All pins should be valid MCP2221A GPIO pins
        valid_pins = {"GP0", "GP1", "GP2", "GP3"}
        for pin in assigned_pins:
            assert pin in valid_pins, f"Invalid GPIO pin: {pin}"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_threshold_validation():
    """Test that config endpoint returns valid threshold values."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        thresholds = data["thresholds"]

        # Movement timeout should be reasonable (not too small or too large)
        movement_timeout = thresholds["movement_timeout_ms"]
        assert 100 <= movement_timeout <= 60000, "Movement timeout should be between 100ms and 60s"

        # Runout debounce should be reasonable
        runout_debounce = thresholds["runout_debounce_ms"]
        assert 0 <= runout_debounce <= 5000, "Runout debounce should be between 0ms and 5s"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_calibration_validation():
    """Test that config endpoint returns valid calibration values."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        calibration = data["calibration"]

        # mm_per_pulse should be a positive number within reasonable bounds
        mm_per_pulse = calibration["mm_per_pulse"]
        assert 0.1 <= mm_per_pulse <= 10.0, "mm_per_pulse should be between 0.1 and 10.0"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_endpoint_logging_levels():
    """Test that config endpoint returns valid logging configuration."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/config")

        assert response.status_code == 200
        data = response.json()

        logging_config = data["logging"]

        # Level should be one of standard logging levels
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert logging_config["level"] in valid_levels

        # Structured logging should be boolean
        assert isinstance(logging_config["structured"], bool)