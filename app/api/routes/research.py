"""Research agent API endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from app.agents.research import ResearchAgent
from app.api.middleware import get_current_api_key
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.auth import APIKey
from app.models.research import ResearchRequest, ResearchResponse
from app.services.providers import (
    ProviderExecutionError,
    ProviderManager,
    ProviderNotConfiguredError,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])

settings = get_settings()
provider_manager = ProviderManager(settings.providers)
research_agent = ResearchAgent(provider_manager)


@router.post("/research", response_model=ResearchResponse)
async def research(
    request: ResearchRequest,
    api_key: APIKey = Depends(get_current_api_key),
) -> ResearchResponse:
    """Run synchronous research and return an Obsidian markdown note."""
    try:
        return await research_agent.research(
            topic=request.topic,
            depth=request.depth,
            provider=request.provider,
            focus_areas=request.focus_areas,
        )
    except ProviderNotConfiguredError as exc:
        logger.error("Research provider not configured", extra={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderExecutionError as exc:
        logger.error(
            "Research execution failed across providers",
            extra={
                "error": str(exc),
                "attempted_providers": [provider.value for provider in exc.attempted_providers],
            },
        )
        raise HTTPException(
            status_code=502, detail="All configured providers failed to execute research"
        ) from exc
    except Exception as exc:
        logger.error("Research request failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Research request failed") from exc
