"""Pytest configuration and fixtures."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import AuthConfig, Settings
from app.main import app
from app.models.auth import APIKeyConfig, APIKeyStatus

TEST_API_KEY = "oea_0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Provide deterministic settings for tests.

    CI does not include config/main.yaml (it's gitignored), so tests
    should not depend on local configuration files.
    """
    settings = Settings()
    settings.auth = AuthConfig(
        enabled=True,
        api_keys=[
            APIKeyConfig(
                key_id="test-key-1",
                name="Test Key",
                key=TEST_API_KEY,
                status=APIKeyStatus.ACTIVE,
            ),
        ],
    )
    monkeypatch.setattr("app.api.middleware.auth.get_settings", lambda: settings)


@pytest.fixture(scope="session")
def test_app() -> Iterator[TestClient]:
    """
    Create a test client for the FastAPI app.

    Yields:
        TestClient for making requests to the app
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client() -> AsyncIterator[AsyncClient]:
    """
    Create an async test client for the FastAPI app.

    Yields:
        AsyncClient for making async requests to the app
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
