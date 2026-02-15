"""Tests for request history and execution tracking."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.main import create_app
from app.main import settings as app_settings
from app.models.chat import ChatResponse
from app.models.providers import ProviderType

TEST_HEADERS = {"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}


@pytest.fixture
def history_client(tmp_path) -> Iterator[TestClient]:
    """Create test client with isolated history storage."""
    original_enabled = app_settings.history.enabled
    original_storage = app_settings.history.storage_dir
    original_retention = app_settings.history.retention_days

    app_settings.history.enabled = True
    app_settings.history.storage_dir = str(tmp_path / "history")
    app_settings.history.retention_days = 14

    app = create_app()
    with TestClient(app) as client:
        yield client

    app_settings.history.enabled = original_enabled
    app_settings.history.storage_dir = original_storage
    app_settings.history.retention_days = original_retention


def test_history_records_requests(history_client: TestClient) -> None:
    """Request middleware should persist request history records."""
    response = history_client.get("/health", headers=TEST_HEADERS)
    assert response.status_code == 200

    history = history_client.get(
        "/history/requests",
        params={"path_contains": "/health", "limit": 20},
        headers=TEST_HEADERS,
    )
    assert history.status_code == 200

    payload = history.json()
    assert payload["total"] >= 1
    assert any(item["path"] == "/health" for item in payload["items"])


def test_history_records_chat_execution(history_client: TestClient, mocker: MockerFixture) -> None:
    """Chat endpoint should record execution history entries."""
    mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
    mock_chat.return_value = ChatResponse(
        reply="hi",
        provider=ProviderType.OPENAI,
        model="gpt-4o",
    )

    response = history_client.post(
        "/chat",
        json={"message": "hello"},
        headers=TEST_HEADERS,
    )
    assert response.status_code == 200

    executions = history_client.get(
        "/history/executions",
        params={"agent": "chat", "limit": 20},
        headers=TEST_HEADERS,
    )
    assert executions.status_code == 200

    payload = executions.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["agent"] == "chat"
    assert payload["items"][0]["status"] == "completed"


def test_history_stats_aggregates(history_client: TestClient, mocker: MockerFixture) -> None:
    """Stats endpoint should aggregate request and execution metrics."""
    mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
    mock_chat.return_value = ChatResponse(
        reply="hi",
        provider=ProviderType.OPENAI,
        model="gpt-4o",
    )

    history_client.get("/health", headers=TEST_HEADERS)
    history_client.post(
        "/chat",
        json={"message": "hello"},
        headers=TEST_HEADERS,
    )

    stats = history_client.get("/history/stats", headers=TEST_HEADERS)
    assert stats.status_code == 200

    payload = stats.json()
    assert payload["request_count"] >= 2
    assert payload["execution_count"] >= 1
    assert payload["execution_success_count"] >= 1
