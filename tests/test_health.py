"""Tests for health check endpoint."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_check_sync(test_app: TestClient) -> None:
    """
    Test health check endpoint (synchronous).

    Args:
        test_app: Test client fixture
    """
    # Use the default test API key from config
    response = test_app.get(
        "/health", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ObsidianEcho-AI"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_check_async(async_client: AsyncClient) -> None:
    """
    Test health check endpoint (asynchronous).

    Args:
        async_client: Async test client fixture
    """
    # Use the default test API key from config
    response = await async_client.get(
        "/health", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ObsidianEcho-AI"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_health_check_response_schema(test_app: TestClient) -> None:
    """
    Test that health check response has correct schema.

    Args:
        test_app: Test client fixture
    """
    # Use the default test API key from config
    response = test_app.get(
        "/health", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
    )

    data = response.json()

    # Check all required fields are present
    required_fields = ["status", "timestamp", "service", "version"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Check field types
    assert isinstance(data["status"], str)
    assert isinstance(data["timestamp"], str)
    assert isinstance(data["service"], str)
    assert isinstance(data["version"], str)
