"""Tests for health check endpoint."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.config import Settings
from app.models.providers import ProviderHealth, ProviderType


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


def test_providers_health_check_healthy(test_app: TestClient, mocker) -> None:
    """Test provider health endpoint returns healthy when enabled providers are healthy."""
    mocker.patch("app.api.routes.health.get_settings", return_value=Settings())
    mocker.patch(
        "app.api.routes.health.ProviderManager.get_providers_health",
        return_value=[
            ProviderHealth(
                provider=ProviderType.OPENAI,
                enabled=True,
                model="gpt-4o",
                api_key_present=True,
                healthy=True,
                reason="Provider is ready",
            ),
            ProviderHealth(
                provider=ProviderType.XAI,
                enabled=False,
                model="grok-beta",
                api_key_present=False,
                healthy=False,
                reason="Provider disabled",
            ),
        ],
    )

    response = test_app.get(
        "/health/providers", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "checked_at" in data
    assert len(data["providers"]) == 2


def test_providers_health_check_degraded(test_app: TestClient, mocker) -> None:
    """Test provider health endpoint returns degraded when enabled provider is unhealthy."""
    mocker.patch("app.api.routes.health.get_settings", return_value=Settings())
    mocker.patch(
        "app.api.routes.health.ProviderManager.get_providers_health",
        return_value=[
            ProviderHealth(
                provider=ProviderType.OPENAI,
                enabled=True,
                model="gpt-4o",
                api_key_present=False,
                healthy=False,
                reason="Missing environment variable: OPENAI_API_KEY",
            ),
        ],
    )

    response = test_app.get(
        "/health/providers", headers={"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert len(data["providers"]) == 1
