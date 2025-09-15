"""
Contract tests for POST /config endpoint.

Tests the API contract for updating system configuration including
validation of input data, error handling, and successful updates.
"""
import pytest
import httpx
from typing import Dict, Any


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_valid_configuration():
    """Test that POST /config accepts and validates correct configuration."""
    valid_config = {
        "polling_interval_ms": 200,
        "sensors": [
            {
                "id": "sensor_1",
                "name": "Extruder 1",
                "enabled": True,
                "gpio_pins": {
                    "movement": "GP0",
                    "runout": "GP1"
                }
            },
            {
                "id": "sensor_2",
                "name": "Extruder 2",
                "enabled": False,
                "gpio_pins": {
                    "movement": "GP2",
                    "runout": "GP3"
                }
            }
        ],
        "thresholds": {
            "movement_timeout_ms": 5000,
            "runout_debounce_ms": 100
        },
        "calibration": {
            "mm_per_pulse": 3.0
        },
        "logging": {
            "level": "DEBUG",
            "structured": True
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            json=valid_config
        )

        assert response.status_code == 200
        data = response.json()

        # Should return success message and updated configuration
        assert "message" in data
        assert "config" in data
        assert data["message"] == "Configuration updated successfully"

        # Returned config should match the input
        returned_config = data["config"]
        assert returned_config["polling_interval_ms"] == 200
        assert returned_config["sensors"][0]["name"] == "Extruder 1"
        assert returned_config["sensors"][1]["enabled"] is False
        assert returned_config["thresholds"]["movement_timeout_ms"] == 5000
        assert returned_config["calibration"]["mm_per_pulse"] == 3.0
        assert returned_config["logging"]["level"] == "DEBUG"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_partial_configuration():
    """Test that POST /config accepts partial configuration updates."""
    partial_config = {
        "polling_interval_ms": 150,
        "thresholds": {
            "movement_timeout_ms": 3000
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            json=partial_config
        )

        assert response.status_code == 200
        data = response.json()

        # Should return success message
        assert data["message"] == "Configuration updated successfully"

        # Should merge with existing configuration
        returned_config = data["config"]
        assert returned_config["polling_interval_ms"] == 150
        assert returned_config["thresholds"]["movement_timeout_ms"] == 3000

        # Other values should remain unchanged (default values)
        assert "sensors" in returned_config
        assert "calibration" in returned_config
        assert "logging" in returned_config


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_invalid_polling_interval():
    """Test that POST /config rejects invalid polling intervals."""
    invalid_configs = [
        {"polling_interval_ms": 5},      # Too small (minimum 10ms)
        {"polling_interval_ms": 50000},  # Too large (maximum 10000ms)
        {"polling_interval_ms": -100},   # Negative
        {"polling_interval_ms": "100"},  # Wrong type (string)
        {"polling_interval_ms": 100.5},  # Float instead of int
    ]

    for invalid_config in invalid_configs:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/config",
                json=invalid_config
            )

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data
            assert "polling_interval_ms" in str(data).lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_invalid_gpio_pins():
    """Test that POST /config rejects invalid GPIO pin assignments."""
    invalid_configs = [
        {
            "sensors": [
                {
                    "id": "sensor_1",
                    "gpio_pins": {
                        "movement": "GP5",  # Invalid pin (only GP0-GP3 exist)
                        "runout": "GP1"
                    }
                }
            ]
        },
        {
            "sensors": [
                {
                    "id": "sensor_1",
                    "gpio_pins": {
                        "movement": "GP0",
                        "runout": "GP0"  # Same pin used twice
                    }
                }
            ]
        },
        {
            "sensors": [
                {
                    "id": "sensor_1",
                    "gpio_pins": {
                        "movement": "GP0",
                        "runout": "GP1"
                    }
                },
                {
                    "id": "sensor_2",
                    "gpio_pins": {
                        "movement": "GP0",  # Pin already used by sensor_1
                        "runout": "GP2"
                    }
                }
            ]
        }
    ]

    for invalid_config in invalid_configs:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/config",
                json=invalid_config
            )

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_invalid_thresholds():
    """Test that POST /config rejects invalid threshold values."""
    invalid_configs = [
        {"thresholds": {"movement_timeout_ms": -1000}},      # Negative timeout
        {"thresholds": {"runout_debounce_ms": -500}},        # Negative debounce
        {"thresholds": {"movement_timeout_ms": 100000}},     # Too large timeout
        {"thresholds": {"runout_debounce_ms": "100"}},       # Wrong type
    ]

    for invalid_config in invalid_configs:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/config",
                json=invalid_config
            )

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_invalid_calibration():
    """Test that POST /config rejects invalid calibration values."""
    invalid_configs = [
        {"calibration": {"mm_per_pulse": 0}},        # Zero value
        {"calibration": {"mm_per_pulse": -1.5}},     # Negative value
        {"calibration": {"mm_per_pulse": 50.0}},     # Too large
        {"calibration": {"mm_per_pulse": "2.88"}},   # Wrong type
    ]

    for invalid_config in invalid_configs:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/config",
                json=invalid_config
            )

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_invalid_logging_level():
    """Test that POST /config rejects invalid logging levels."""
    invalid_configs = [
        {"logging": {"level": "TRACE"}},     # Invalid level
        {"logging": {"level": "info"}},      # Wrong case
        {"logging": {"level": 123}},         # Wrong type
        {"logging": {"structured": "true"}}, # Wrong type for structured
    ]

    for invalid_config in invalid_configs:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5002/config",
                json=invalid_config
            )

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_malformed_json():
    """Test that POST /config handles malformed JSON gracefully."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            content="{ invalid json }"  # Malformed JSON
        )

        assert response.status_code == 400  # Bad request
        data = response.json()
        assert "error" in data
        assert "json" in data["error"].lower() or "parse" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_missing_content_type():
    """Test that POST /config requires correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            content='{"polling_interval_ms": 200}',
            headers={"Content-Type": "text/plain"}  # Wrong content type
        )

        assert response.status_code == 415  # Unsupported Media Type
        data = response.json()
        assert "error" in data
        assert "content-type" in data["error"].lower() or "media type" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_empty_payload():
    """Test that POST /config handles empty payload."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            json={}  # Empty configuration
        )

        # Empty config should be valid (no changes made)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Configuration updated successfully"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_error_when_service_down():
    """Test that config update returns error when service is not running."""
    # This test should fail initially since no service is running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:5002/config",
                json={"polling_interval_ms": 200}
            )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_content_type():
    """Test that config update returns correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            json={"polling_interval_ms": 200}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_cors_headers():
    """Test that config update includes CORS headers."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5002/config",
            json={"polling_interval_ms": 200}
        )

        assert response.status_code == 200
        # CORS headers should be present for web client access
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_update_immediate_effect():
    """Test that configuration changes take effect immediately."""
    # First, get current config
    async with httpx.AsyncClient() as client:
        get_response = await client.get("http://localhost:5002/config")
        assert get_response.status_code == 200
        original_config = get_response.json()

        # Update polling interval
        new_interval = 250
        update_response = await client.post(
            "http://localhost:5002/config",
            json={"polling_interval_ms": new_interval}
        )
        assert update_response.status_code == 200

        # Verify change is immediately reflected
        get_response_after = await client.get("http://localhost:5002/config")
        assert get_response_after.status_code == 200
        updated_config = get_response_after.json()

        assert updated_config["polling_interval_ms"] == new_interval
        assert updated_config["polling_interval_ms"] != original_config["polling_interval_ms"]