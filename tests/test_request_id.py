"""Tests for request ID middleware."""

import pytest
from fastapi.testclient import TestClient

from app.api.middleware.request_id import get_request_id
from app.core.config import AuthConfig, Settings
from app.main import create_app


@pytest.fixture
def disabled_auth_config():
    """Create auth configuration with auth disabled for easier testing."""
    return AuthConfig(enabled=False, api_keys=[])


class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    def test_request_id_in_response_headers(self, mocker, disabled_auth_config):
        """Test that request ID is added to response headers."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.core.config.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")

    def test_request_id_format(self, mocker, disabled_auth_config):
        """Test that request ID has correct format."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.core.config.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        request_id = response.headers["X-Request-ID"]
        assert request_id.startswith("req_")
        assert len(request_id) == 36  # req_ (4) + 32 hex chars

    def test_custom_request_id_preserved(self, mocker, disabled_auth_config):
        """Test that custom request ID from client is preserved."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.core.config.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        custom_id = "req_custom123456789012345678901234"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_request_id_unique_per_request(self, mocker, disabled_auth_config):
        """Test that each request gets a unique request ID."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.core.config.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response1 = client.get("/health")
        response2 = client.get("/health")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        assert id1 != id2

    def test_request_id_on_error_response(self, mocker, disabled_auth_config):
        """Test that request ID is present even on error responses."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.core.config.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        # Request non-existent endpoint
        response = client.get("/nonexistent")
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")


class TestRequestIDContext:
    """Tests for request ID context variable."""

    def test_get_request_id_outside_context(self):
        """Test that get_request_id returns empty string outside request context."""
        # Outside of any request context
        request_id = get_request_id()
        assert request_id == ""
