"""
Contract tests for GET /alerts endpoint.

Tests the API contract for the alerts endpoint which should return
system alerts and warnings with filtering capabilities by severity,
sensor, and time range.
"""
import pytest
import httpx
from typing import Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_returns_valid_schema():
    """Test that GET /alerts returns AlertsResponse schema."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts")

        assert response.status_code == 200
        data = response.json()

        # Validate AlertsResponse schema
        assert "alerts" in data
        assert "total_count" in data
        assert "filters_applied" in data

        # Validate alerts array
        alerts = data["alerts"]
        assert isinstance(alerts, list)

        for alert in alerts:
            # Required fields
            assert "id" in alert
            assert "timestamp" in alert
            assert "severity" in alert
            assert "message" in alert
            assert "source" in alert

            # Optional fields
            if "sensor_id" in alert:
                assert alert["sensor_id"] in ["sensor_1", "sensor_2", "system"]

            if "acknowledged" in alert:
                assert isinstance(alert["acknowledged"], bool)

            if "acknowledged_at" in alert and alert["acknowledged_at"]:
                datetime.fromisoformat(alert["acknowledged_at"].replace("Z", "+00:00"))

            # Validate field types and values
            assert isinstance(alert["id"], str)
            datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00"))
            assert alert["severity"] in ["info", "warning", "error", "critical"]
            assert isinstance(alert["message"], str)
            assert len(alert["message"]) > 0
            assert alert["source"] in ["sensor", "hardware", "system", "configuration"]

        # Validate total_count
        total_count = data["total_count"]
        assert isinstance(total_count, int)
        assert total_count >= len(alerts)  # Total might be larger if pagination applied

        # Validate filters_applied
        filters_applied = data["filters_applied"]
        assert isinstance(filters_applied, dict)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_severity_filter():
    """Test that GET /alerts filters by severity level."""
    test_severities = ["info", "warning", "error", "critical"]

    for severity in test_severities:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:5002/alerts?severity={severity}")

            assert response.status_code == 200
            data = response.json()

            # All returned alerts should have the requested severity
            for alert in data["alerts"]:
                assert alert["severity"] == severity

            # Filters should be recorded
            assert data["filters_applied"]["severity"] == severity


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_multiple_severity_filter():
    """Test that GET /alerts filters by multiple severity levels."""
    severities = ["warning", "error"]
    query_params = urlencode([("severity", s) for s in severities])

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:5002/alerts?{query_params}")

        assert response.status_code == 200
        data = response.json()

        # All returned alerts should have one of the requested severities
        for alert in data["alerts"]:
            assert alert["severity"] in severities

        # Filters should be recorded
        assert data["filters_applied"]["severity"] == severities


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_sensor_filter():
    """Test that GET /alerts filters by sensor ID."""
    test_sensor_ids = ["sensor_1", "sensor_2", "system"]

    for sensor_id in test_sensor_ids:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:5002/alerts?sensor_id={sensor_id}")

            assert response.status_code == 200
            data = response.json()

            # All returned alerts should be for the requested sensor
            for alert in data["alerts"]:
                if "sensor_id" in alert:
                    assert alert["sensor_id"] == sensor_id

            # Filters should be recorded
            assert data["filters_applied"]["sensor_id"] == sensor_id


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_time_range_filter():
    """Test that GET /alerts filters by time range."""
    # Test with relative time ranges
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)

    # Format timestamps for URL
    since_param = one_hour_ago.isoformat() + "Z"
    until_param = now.isoformat() + "Z"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:5002/alerts?since={since_param}&until={until_param}"
        )

        assert response.status_code == 200
        data = response.json()

        # All returned alerts should be within the time range
        for alert in data["alerts"]:
            alert_time = datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00"))
            assert one_hour_ago <= alert_time.replace(tzinfo=None) <= now

        # Filters should be recorded
        filters = data["filters_applied"]
        assert "since" in filters
        assert "until" in filters


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_acknowledged_filter():
    """Test that GET /alerts filters by acknowledgment status."""
    # Test acknowledged alerts
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts?acknowledged=true")

        assert response.status_code == 200
        data = response.json()

        # All returned alerts should be acknowledged
        for alert in data["alerts"]:
            assert alert.get("acknowledged", False) is True

        # Filters should be recorded
        assert data["filters_applied"]["acknowledged"] is True

    # Test unacknowledged alerts
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts?acknowledged=false")

        assert response.status_code == 200
        data = response.json()

        # All returned alerts should be unacknowledged
        for alert in data["alerts"]:
            assert alert.get("acknowledged", False) is False

        # Filters should be recorded
        assert data["filters_applied"]["acknowledged"] is False


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_limit_filter():
    """Test that GET /alerts respects limit parameter."""
    test_limits = [1, 5, 10, 50]

    for limit in test_limits:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:5002/alerts?limit={limit}")

            assert response.status_code == 200
            data = response.json()

            # Should return at most 'limit' alerts
            assert len(data["alerts"]) <= limit

            # Filters should be recorded
            assert data["filters_applied"]["limit"] == limit


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_offset_pagination():
    """Test that GET /alerts supports offset-based pagination."""
    async with httpx.AsyncClient() as client:
        # Get first page
        response1 = await client.get("http://localhost:5002/alerts?limit=5&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        response2 = await client.get("http://localhost:5002/alerts?limit=5&offset=5")
        assert response2.status_code == 200
        data2 = response2.json()

        # Pages should be different (if enough alerts exist)
        if data1["total_count"] > 5:
            alert_ids_1 = {alert["id"] for alert in data1["alerts"]}
            alert_ids_2 = {alert["id"] for alert in data2["alerts"]}
            assert alert_ids_1.isdisjoint(alert_ids_2), "Pages should contain different alerts"

        # Filters should be recorded
        assert data1["filters_applied"]["limit"] == 5
        assert data1["filters_applied"]["offset"] == 0
        assert data2["filters_applied"]["offset"] == 5


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_combined_filters():
    """Test that GET /alerts handles multiple filters simultaneously."""
    query_params = urlencode({
        "severity": "error",
        "sensor_id": "sensor_1",
        "acknowledged": "false",
        "limit": "10"
    })

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:5002/alerts?{query_params}")

        assert response.status_code == 200
        data = response.json()

        # All filters should be applied simultaneously
        for alert in data["alerts"]:
            assert alert["severity"] == "error"
            if "sensor_id" in alert:
                assert alert["sensor_id"] == "sensor_1"
            assert alert.get("acknowledged", False) is False

        # Should return at most 10 alerts
        assert len(data["alerts"]) <= 10

        # All filters should be recorded
        filters = data["filters_applied"]
        assert filters["severity"] == "error"
        assert filters["sensor_id"] == "sensor_1"
        assert filters["acknowledged"] is False
        assert filters["limit"] == 10


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_invalid_severity():
    """Test that GET /alerts rejects invalid severity values."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts?severity=invalid")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "error" in data
        assert "severity" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_invalid_time_format():
    """Test that GET /alerts rejects invalid timestamp formats."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts?since=invalid-date")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "error" in data
        assert "timestamp" in data["error"].lower() or "date" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_invalid_limit():
    """Test that GET /alerts rejects invalid limit values."""
    invalid_limits = [-1, 0, 1001, "abc"]  # Negative, zero, too large, non-numeric

    for invalid_limit in invalid_limits:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:5002/alerts?limit={invalid_limit}")

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "limit" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_error_when_service_down():
    """Test that alerts endpoint returns error when service is not running."""
    # This test should fail initially since no service is running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.get("http://localhost:5002/alerts")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_content_type():
    """Test that alerts endpoint returns correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_cors_headers():
    """Test that alerts endpoint includes CORS headers."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/alerts")

        assert response.status_code == 200
        # CORS headers should be present for web client access
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_response_time():
    """Test that alerts endpoint responds within performance target (<5ms)."""
    import time

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get("http://localhost:5002/alerts")
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        assert response.status_code == 200
        assert response_time < 5.0, f"Response time {response_time:.2f}ms exceeds 5ms target"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_alerts_endpoint_empty_result():
    """Test that alerts endpoint handles empty results gracefully."""
    # Filter for alerts that shouldn't exist
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:5002/alerts?since={future_date}")

        assert response.status_code == 200
        data = response.json()

        # Should return empty array but valid schema
        assert data["alerts"] == []
        assert data["total_count"] == 0
        assert "filters_applied" in data