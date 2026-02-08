"""Authentication middleware."""

from datetime import UTC, datetime

from fastapi import Header, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_api_key, validate_api_key_format
from app.models.auth import APIKey, APIKeyStatus

logger = get_logger(__name__)

# FastAPI security scheme for API key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> APIKey:
    """
    Validate API key from request headers.

    Checks both X-API-Key header and Authorization header (Bearer scheme).

    Args:
        x_api_key: API key from X-API-Key header
        authorization: Authorization header value

    Returns:
        Valid API key model

    Raises:
        HTTPException: 401 if key is missing or invalid, 403 if revoked
    """
    settings = get_settings()

    # Skip authentication if disabled (useful for development)
    if not settings.auth.enabled:
        logger.debug("Authentication is disabled")
        return APIKey(
            key_id="dev",
            name="Development",
            key_hash="",
            status=APIKeyStatus.ACTIVE,
        )

    # Extract API key from headers
    api_key = None
    if x_api_key:
        api_key = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]  # Remove "Bearer " prefix

    # Check if key is provided
    if not api_key:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Provide it via X-API-Key header or Authorization: Bearer <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Validate key format
    if not validate_api_key_format(api_key):
        logger.warning("Invalid API key format", extra={"key_prefix": api_key[:10]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Hash the provided key
    key_hash = hash_api_key(api_key)

    # Find matching key in configuration
    stored_key = None
    for key_config in settings.auth.api_keys:
        config_hash = hash_api_key(key_config.key)
        if config_hash == key_hash:
            stored_key = APIKey(
                key_id=key_config.key_id,
                name=key_config.name,
                key_hash=config_hash,
                status=key_config.status,
                last_used_at=datetime.now(UTC),
            )
            break

    if not stored_key:
        logger.warning("API key not found", extra={"key_hash": key_hash[:16]})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check if key is revoked
    if stored_key.status == APIKeyStatus.REVOKED:
        logger.warning(
            "Revoked API key used",
            extra={"key_id": stored_key.key_id, "key_name": stored_key.name},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has been revoked",
        )

    logger.debug(
        "API key validated",
        extra={"key_id": stored_key.key_id, "key_name": stored_key.name},
    )

    return stored_key
