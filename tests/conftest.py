"""Pytest configuration and fixtures."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app


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
