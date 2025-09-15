"""
Contract tests for GET /metrics endpoint.

Tests the API contract for the metrics endpoint which should return
session metrics including filament usage, sensor activity statistics,
system uptime, and performance metrics.
"""
import pytest
import httpx
from typing import Dict, Any
from datetime import datetime, timedelta


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_returns_valid_schema():
    """Test that GET /metrics returns MetricsResponse schema."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")

        assert response.status_code == 200
        data = response.json()

        # Validate MetricsResponse schema
        assert "session" in data
        assert "sensors" in data
        assert "system" in data
        assert "performance" in data

        # Validate session metrics
        session = data["session"]
        assert "started_at" in session
        assert "uptime_seconds" in session
        assert "total_alerts" in session
        assert "active_alerts" in session

        # Validate timestamp format
        datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
        assert isinstance(session["uptime_seconds"], (int, float))
        assert session["uptime_seconds"] >= 0
        assert isinstance(session["total_alerts"], int)
        assert session["total_alerts"] >= 0
        assert isinstance(session["active_alerts"], int)
        assert session["active_alerts"] >= 0

        # Validate sensors metrics
        sensors = data["sensors"]
        assert isinstance(sensors, list)
        assert len(sensors) == 2

        for i, sensor in enumerate(sensors):
            assert sensor["id"] == f"sensor_{i+1}"
            assert "total_usage_mm" in sensor
            assert "movement_events" in sensor
            assert "runout_events" in sensor
            assert "last_activity" in sensor

            assert isinstance(sensor["total_usage_mm"], (int, float))
            assert sensor["total_usage_mm"] >= 0
            assert isinstance(sensor["movement_events"], int)
            assert sensor["movement_events"] >= 0
            assert isinstance(sensor["runout_events"], int)
            assert sensor["runout_events"] >= 0

            if sensor["last_activity"] is not None:
                datetime.fromisoformat(sensor["last_activity"].replace("Z", "+00:00"))

        # Validate system metrics
        system = data["system"]
        assert "polling_cycles" in system
        assert "missed_cycles" in system
        assert "error_count" in system
        assert "mcp2221_reconnects" in system

        assert isinstance(system["polling_cycles"], int)
        assert system["polling_cycles"] >= 0
        assert isinstance(system["missed_cycles"], int)
        assert system["missed_cycles"] >= 0
        assert isinstance(system["error_count"], int)
        assert system["error_count"] >= 0
        assert isinstance(system["mcp2221_reconnects"], int)
        assert system["mcp2221_reconnects"] >= 0

        # Validate performance metrics
        performance = data["performance"]
        assert "avg_polling_time_ms" in performance
        assert "max_polling_time_ms" in performance
        assert "memory_usage_mb" in performance
        assert "api_requests" in performance

        assert isinstance(performance["avg_polling_time_ms"], (int, float))
        assert performance["avg_polling_time_ms"] >= 0
        assert isinstance(performance["max_polling_time_ms"], (int, float))
        assert performance["max_polling_time_ms"] >= 0
        assert isinstance(performance["memory_usage_mb"], (int, float))
        assert performance["memory_usage_mb"] > 0
        assert isinstance(performance["api_requests"], int)
        assert performance["api_requests"] >= 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_sensor_details():
    """Test that metrics endpoint returns detailed sensor statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics?detailed=true")

        assert response.status_code == 200
        data = response.json()

        # Detailed sensor metrics should include additional fields
        for sensor in data["sensors"]:
            # Basic fields should still be present
            assert "total_usage_mm" in sensor
            assert "movement_events" in sensor
            assert "runout_events" in sensor

            # Detailed fields should be added
            assert "hourly_usage" in sensor
            assert "avg_pulse_interval_ms" in sensor
            assert "status_changes" in sensor

            # Validate hourly_usage array (last 24 hours)
            hourly_usage = sensor["hourly_usage"]
            assert isinstance(hourly_usage, list)
            assert len(hourly_usage) <= 24  # Up to 24 hours

            for hour_data in hourly_usage:
                assert "hour" in hour_data
                assert "usage_mm" in hour_data
                assert isinstance(hour_data["usage_mm"], (int, float))
                assert hour_data["usage_mm"] >= 0
                datetime.fromisoformat(hour_data["hour"].replace("Z", "+00:00"))

            # Validate performance metrics
            if sensor["avg_pulse_interval_ms"] is not None:
                assert isinstance(sensor["avg_pulse_interval_ms"], (int, float))
                assert sensor["avg_pulse_interval_ms"] > 0

            assert isinstance(sensor["status_changes"], int)
            assert sensor["status_changes"] >= 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_time_range_filter():
    """Test that metrics endpoint supports time range filtering."""
    # Test with last hour
    since = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:5002/metrics?since={since}")

        assert response.status_code == 200
        data = response.json()

        # Should return metrics for the specified time range
        # Session start time should be considered in calculations
        session_start = datetime.fromisoformat(data["session"]["started_at"].replace("Z", "+00:00"))
        filter_start = datetime.fromisoformat(since.replace("Z", "+00:00"))

        # If session started after filter time, uptime should match
        if session_start >= filter_start:
            # Metrics should reflect the actual session time
            assert data["session"]["uptime_seconds"] >= 0
        else:
            # Metrics should be filtered to the requested time range
            max_uptime = (datetime.utcnow().replace(tzinfo=None) - filter_start.replace(tzinfo=None)).total_seconds()
            assert data["session"]["uptime_seconds"] <= max_uptime + 60  # Allow 60s tolerance


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_sensor_filter():
    """Test that metrics endpoint supports sensor-specific filtering."""
    test_sensor_ids = ["sensor_1", "sensor_2"]

    for sensor_id in test_sensor_ids:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:5002/metrics?sensor_id={sensor_id}")

            assert response.status_code == 200
            data = response.json()

            # Should only return metrics for the specified sensor
            sensors = data["sensors"]
            assert len(sensors) == 1
            assert sensors[0]["id"] == sensor_id

            # Other sections should still be present
            assert "session" in data
            assert "system" in data
            assert "performance" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_reset_parameter():
    """Test that metrics endpoint supports reset parameter."""
    async with httpx.AsyncClient() as client:
        # Get current metrics
        response1 = await client.get("http://localhost:5002/metrics")
        assert response1.status_code == 200
        data1 = response1.json()

        # Reset metrics (this should be a separate endpoint in practice)
        # But for contract testing, we test the parameter handling
        response2 = await client.get("http://localhost:5002/metrics?reset=true")
        assert response2.status_code == 200
        data2 = response2.json()

        # After reset, some counters should be reset
        # Session should have a new start time
        session1_start = datetime.fromisoformat(data1["session"]["started_at"].replace("Z", "+00:00"))
        session2_start = datetime.fromisoformat(data2["session"]["started_at"].replace("Z", "+00:00"))

        # New session should have started recently
        time_diff = (datetime.utcnow().replace(tzinfo=None) - session2_start.replace(tzinfo=None)).total_seconds()
        assert time_diff < 60  # Should be within last minute


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_performance_targets():
    """Test that system performance meets specified targets."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")

        assert response.status_code == 200
        data = response.json()

        performance = data["performance"]

        # Performance targets from specification
        assert performance["avg_polling_time_ms"] <= 10.0, "Average polling time should be ≤10ms"
        assert performance["memory_usage_mb"] <= 50.0, "Memory usage should be ≤50MB for 24-hour session"

        # API response time target is tested separately in response_time test
        # but we can check that API requests are being tracked
        assert performance["api_requests"] > 0, "API requests should be tracked"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_consistency():
    """Test that metrics are internally consistent."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")

        assert response.status_code == 200
        data = response.json()

        # Active alerts should not exceed total alerts
        session = data["session"]
        assert session["active_alerts"] <= session["total_alerts"]

        # Missed cycles should not exceed total cycles
        system = data["system"]
        assert system["missed_cycles"] <= system["polling_cycles"]

        # Max polling time should be >= average polling time
        performance = data["performance"]
        assert performance["max_polling_time_ms"] >= performance["avg_polling_time_ms"]

        # Sensor usage should be non-decreasing over time
        for sensor in data["sensors"]:
            assert sensor["total_usage_mm"] >= 0
            assert sensor["movement_events"] >= 0
            assert sensor["runout_events"] >= 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_invalid_parameters():
    """Test that metrics endpoint rejects invalid parameters."""
    invalid_requests = [
        "http://localhost:5002/metrics?since=invalid-date",
        "http://localhost:5002/metrics?sensor_id=invalid_sensor",
        "http://localhost:5002/metrics?detailed=invalid_boolean",
        "http://localhost:5002/metrics?reset=invalid_boolean"
    ]

    for invalid_url in invalid_requests:
        async with httpx.AsyncClient() as client:
            response = await client.get(invalid_url)

            assert response.status_code == 422  # Validation error
            data = response.json()
            assert "error" in data
            assert "validation_errors" in data or "invalid" in data["error"].lower()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_error_when_service_down():
    """Test that metrics endpoint returns error when service is not running."""
    # This test should fail initially since no service is running
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as client:
            await client.get("http://localhost:5002/metrics")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_content_type():
    """Test that metrics endpoint returns correct content type."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_cors_headers():
    """Test that metrics endpoint includes CORS headers."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")

        assert response.status_code == 200
        # CORS headers should be present for web client access
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_response_time():
    """Test that metrics endpoint responds within performance target (<5ms)."""
    import time

    async with httpx.AsyncClient() as client:
        start_time = time.time()
        response = await client.get("http://localhost:5002/metrics")
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        assert response.status_code == 200
        assert response_time < 5.0, f"Response time {response_time:.2f}ms exceeds 5ms target"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_concurrent_requests():
    """Test that metrics endpoint handles concurrent requests correctly."""
    import asyncio

    async def make_request():
        async with httpx.AsyncClient() as client:
            return await client.get("http://localhost:5002/metrics")

    # Make 5 concurrent requests
    tasks = [make_request() for _ in range(5)]
    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for response in responses:
        assert response.status_code == 200
        data = response.json()

        # Basic schema validation
        assert "session" in data
        assert "sensors" in data
        assert "system" in data
        assert "performance" in data

        # API request counter should be incrementing
        assert data["performance"]["api_requests"] > 0


@pytest.mark.contract
@pytest.mark.asyncio
async def test_metrics_endpoint_export_format():
    """Test that metrics endpoint supports different export formats."""
    # Test JSON format (default)
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    # Test CSV format (if supported)
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5002/metrics?format=csv")

        # CSV format might not be implemented yet, so accept both 200 and 422
        if response.status_code == 200:
            assert "text/csv" in response.headers["content-type"]
        else:
            assert response.status_code == 422  # Format not supported yet