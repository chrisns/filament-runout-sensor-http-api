"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    from src.models import SystemStatus

    # Reset SystemStatus singleton
    SystemStatus._instance = None

    yield

    # Clean up after test
    SystemStatus._instance = None


@pytest.fixture
def mock_hardware():
    """Mock hardware for testing without physical device."""
    from unittest.mock import Mock, patch

    with patch('src.lib.mcp2221_sensor.connection.MCP2221') as mock_mcp:
        # Configure mock
        mock_device = Mock()
        mock_device.GPIO_Init.return_value = None
        mock_device.GPIO_Read.return_value = [0, 0, 0, 0]
        mock_mcp.return_value = mock_device

        yield mock_device