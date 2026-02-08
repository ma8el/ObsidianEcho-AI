"""Health check endpoint."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.middleware import get_current_api_key
from app.core.config import Settings, get_settings
from app.models.auth import APIKey

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(
    settings: Settings = Depends(get_settings),
    api_key: APIKey = Depends(get_current_api_key),
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
