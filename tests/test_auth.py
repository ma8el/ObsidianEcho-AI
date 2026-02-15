"""Tests for authentication middleware."""

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.middleware.auth import get_current_api_key
from app.core.config import AuthConfig, Settings
from app.core.security import generate_api_key, hash_api_key
from app.main import create_app
from app.models.auth import APIKeyConfig, APIKeyStatus


@pytest.fixture
def test_api_key():
    """Generate a test API key."""
    return generate_api_key()


@pytest.fixture
def auth_config(test_api_key):
    """Create test auth configuration."""
    return AuthConfig(
        enabled=True,
        api_keys=[
            APIKeyConfig(
                key_id="test-key-1",
                name="Test Key 1",
                key=test_api_key,
                status=APIKeyStatus.ACTIVE,
            ),
        ],
    )


@pytest.fixture
def auth_config_hashed(test_api_key):
    """Create test auth configuration with hashed API key storage."""
    return AuthConfig(
        enabled=True,
        api_keys=[
            APIKeyConfig(
                key_id="test-key-hashed",
                name="Test Key Hashed",
                key_hash=hash_api_key(test_api_key),
                status=APIKeyStatus.ACTIVE,
            ),
        ],
    )


@pytest.fixture
def auth_config_with_revoked_key(test_api_key):
    """Create auth configuration with revoked key."""
    return AuthConfig(
        enabled=True,
        api_keys=[
            APIKeyConfig(
                key_id="revoked-key",
                name="Revoked Key",
                key=test_api_key,
                status=APIKeyStatus.REVOKED,
            ),
        ],
    )


@pytest.fixture
def disabled_auth_config():
    """Create auth configuration with auth disabled."""
    return AuthConfig(enabled=False, api_keys=[])


class TestAuthenticationMiddleware:
    """Tests for authentication middleware."""

    @pytest.mark.asyncio
    async def test_valid_api_key_x_api_key_header(self, mocker, test_api_key, auth_config):
        """Test authentication with valid API key in X-API-Key header."""
        settings = Settings()
        settings.auth = auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        result = await get_current_api_key(x_api_key=test_api_key)
        assert result.key_id == "test-key-1"
        assert result.name == "Test Key 1"
        assert result.status == APIKeyStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_valid_api_key_with_hashed_storage(
        self, mocker, test_api_key, auth_config_hashed
    ):
        """Test authentication with API key stored as hash."""
        settings = Settings()
        settings.auth = auth_config_hashed
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        result = await get_current_api_key(x_api_key=test_api_key)
        assert result.key_id == "test-key-hashed"
        assert result.name == "Test Key Hashed"
        assert result.status == APIKeyStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_valid_api_key_authorization_header(self, mocker, test_api_key, auth_config):
        """Test authentication with valid API key in Authorization header."""
        settings = Settings()
        settings.auth = auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        authorization = f"Bearer {test_api_key}"
        result = await get_current_api_key(x_api_key=None, authorization=authorization)
        assert result.key_id == "test-key-1"
        assert result.name == "Test Key 1"
        assert result.status == APIKeyStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_missing_api_key(self, mocker, auth_config):
        """Test authentication fails when API key is missing."""
        settings = Settings()
        settings.auth = auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(x_api_key=None, authorization=None)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "API key is required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_api_key_format(self, mocker, auth_config):
        """Test authentication fails for invalid key format."""
        settings = Settings()
        settings.auth = auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(x_api_key="invalid_key_format")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_unknown_api_key(self, mocker, auth_config):
        """Test authentication fails for unknown API key."""
        settings = Settings()
        settings.auth = auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        unknown_key = generate_api_key()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(x_api_key=unknown_key)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_revoked_api_key(self, mocker, test_api_key, auth_config_with_revoked_key):
        """Test authentication fails for revoked API key."""
        settings = Settings()
        settings.auth = auth_config_with_revoked_key
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(x_api_key=test_api_key)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_auth_disabled(self, mocker, disabled_auth_config):
        """Test authentication is bypassed when disabled."""
        settings = Settings()
        settings.auth = disabled_auth_config
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)

        result = await get_current_api_key()
        assert result.key_id == "dev"
        assert result.name == "Development"


class TestAuthenticationIntegration:
    """Integration tests for authentication with FastAPI."""

    def test_health_endpoint_with_valid_key(self, mocker, test_api_key, auth_config):
        """Test health endpoint with valid API key."""
        settings = Settings()
        settings.auth = auth_config
        # Patch get_settings in all locations
        mocker.patch("app.core.config.get_settings", return_value=settings)
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)
        mocker.patch("app.api.routes.health.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health", headers={"X-API-Key": test_api_key})
        assert response.status_code == 200
        # Check that request ID is in response headers
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")

    def test_health_endpoint_without_key(self, mocker, auth_config):
        """Test health endpoint without API key returns 401."""
        settings = Settings()
        settings.auth = auth_config
        # Patch get_settings in all locations
        mocker.patch("app.core.config.get_settings", return_value=settings)
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)
        mocker.patch("app.api.routes.health.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 401
        # Request ID should still be present
        assert "X-Request-ID" in response.headers

    def test_health_endpoint_with_invalid_key(self, mocker, auth_config):
        """Test health endpoint with invalid API key returns 401."""
        settings = Settings()
        settings.auth = auth_config
        # Patch get_settings in all locations
        mocker.patch("app.core.config.get_settings", return_value=settings)
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)
        mocker.patch("app.api.routes.health.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401

    def test_health_endpoint_auth_disabled(self, mocker, disabled_auth_config):
        """Test health endpoint works without key when auth is disabled."""
        settings = Settings()
        settings.auth = disabled_auth_config
        # Patch get_settings in all locations
        mocker.patch("app.core.config.get_settings", return_value=settings)
        mocker.patch("app.api.middleware.auth.get_settings", return_value=settings)
        mocker.patch("app.api.routes.health.get_settings", return_value=settings)

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200


class TestAPIKeyConfigValidation:
    """Validation tests for API key configuration model."""

    def test_accepts_hashed_key(self) -> None:
        """APIKeyConfig should accept a SHA-256 key hash."""
        config = APIKeyConfig(
            key_id="hashed",
            name="Hashed Key",
            key_hash="A" * 64,
            status=APIKeyStatus.ACTIVE,
        )
        assert config.key is None
        assert config.key_hash == "a" * 64

    def test_rejects_missing_key_material(self) -> None:
        """APIKeyConfig should reject entries with no key material."""
        with pytest.raises(ValidationError):
            APIKeyConfig(
                key_id="missing",
                name="Missing",
                status=APIKeyStatus.ACTIVE,
            )

    def test_rejects_both_key_and_key_hash(self) -> None:
        """APIKeyConfig should reject entries with both key and key_hash."""
        with pytest.raises(ValidationError):
            APIKeyConfig(
                key_id="both",
                name="Both",
                key="oea_0123456789abcdef0123456789abcdef",
                key_hash="a" * 64,
                status=APIKeyStatus.ACTIVE,
            )
