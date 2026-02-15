"""Authentication middleware."""

from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_api_key, validate_api_key_format
from app.models.auth import APIKey, APIKeyStatus

logger = get_logger(__name__)
api_key_id_context: ContextVar[str] = ContextVar("api_key_id", default="")

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
    # Prevent leaking key IDs across requests in case of auth failures.
    api_key_id_context.set("")

    # Skip authentication if disabled (useful for development)
    if not settings.auth.enabled:
        logger.debug("Authentication is disabled")
        dev_key = APIKey(
            key_id="dev",
            name="Development",
            key_hash="",
            status=APIKeyStatus.ACTIVE,
        )
        api_key_id_context.set(dev_key.key_id)
        return dev_key

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
        config_hash = key_config.key_hash
        if config_hash is None:
            if key_config.key is None:
                continue
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

    api_key_id_context.set(stored_key.key_id)

    return stored_key


def get_api_key_id() -> str:
    """
    Get current request API key id from context.

    Returns:
        API key id if available, else empty string
    """
    return api_key_id_context.get()


async def get_authenticated_api_key(
    request: Request,
    response: Response,
    api_key: APIKey = Depends(get_current_api_key),
) -> APIKey:
    """
    Validate API key and store its ID on request state for downstream middleware.
    """
    request.state.api_key_id = api_key.key_id

    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    if rate_limiter is not None:
        agent = _resolve_rate_limit_agent(request.url.path)
        decision = await rate_limiter.consume_request(
            api_key_id=api_key.key_id,
            agent=agent,
        )
        headers = rate_limiter.build_headers(decision)
        request.state.rate_limit_headers = headers

        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        if decision is not None and not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=decision.detail,
                headers=headers,
            )

    return api_key


def _resolve_rate_limit_agent(path: str) -> str:
    """Map request path to agent-specific rate limit scope."""
    if path.startswith("/chat"):
        return "chat"
    if path.startswith("/agents/research"):
        return "research"
    if path.startswith("/tasks"):
        return "tasks"
    if path.startswith("/history"):
        return "history"
    if path.startswith("/health"):
        return "health"
    return "default"
