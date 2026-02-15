"""Health check endpoint."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.middleware import get_authenticated_api_key
from app.core.config import Settings, get_settings
from app.models.auth import APIKey
from app.models.providers import ProviderHealth
from app.services.providers import ProviderManager

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime
    service: str
    version: str


class ProviderHealthResponse(BaseModel):
    """Provider health response model."""

    status: str
    checked_at: datetime
    providers: list[ProviderHealth]


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(
    settings: Settings = Depends(get_settings),
    api_key: APIKey = Depends(get_authenticated_api_key),
) -> HealthResponse:
    """
    Health check endpoint.

    Returns the current status of the service.

    Args:
        settings: Application settings (injected)
        api_key: API key from authentication (injected)
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        service=settings.app_name,
        version=settings.version,
    )


@router.get("/health/providers", response_model=ProviderHealthResponse, tags=["System"])
async def providers_health_check(
    settings: Settings = Depends(get_settings),
    api_key: APIKey = Depends(get_authenticated_api_key),
) -> ProviderHealthResponse:
    """
    Provider health check endpoint.

    Returns readiness information for configured AI providers.

    Args:
        settings: Application settings (injected)
        api_key: API key from authentication (injected)
    """
    provider_manager = ProviderManager(settings.providers)
    providers = provider_manager.get_providers_health(include_disabled=True)
    enabled_providers = [provider for provider in providers if provider.enabled]

    if not enabled_providers:
        overall_status = "no_providers_enabled"
    elif all(provider.healthy for provider in enabled_providers):
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    return ProviderHealthResponse(
        status=overall_status,
        checked_at=datetime.now(UTC),
        providers=providers,
    )
