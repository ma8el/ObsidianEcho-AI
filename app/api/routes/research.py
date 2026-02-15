"""Research agent API endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.agents.research import ResearchAgent
from app.api.middleware import get_authenticated_api_key
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
    payload: ResearchRequest,
    http_request: Request,
    as_markdown: bool = False,
    api_key: APIKey = Depends(get_authenticated_api_key),
) -> ResearchResponse | PlainTextResponse:
    """Run synchronous research and return an Obsidian markdown note."""
    history_service = getattr(http_request.app.state, "history_service", None)
    request_id = getattr(http_request.state, "request_id", None)

    try:
        response = await research_agent.research(
            topic=payload.topic,
            depth=payload.depth,
            provider=payload.provider,
            focus_areas=payload.focus_areas,
        )

        if history_service is not None:
            await history_service.record_execution(
                request_id=request_id,
                api_key_id=api_key.key_id,
                agent="research",
                status="completed",
                provider=response.metadata.provider.value,
                model=response.metadata.model,
                duration_seconds=response.metadata.duration_seconds,
                tokens_used=response.metadata.tokens_used,
                estimated_cost=None,
                metadata={
                    "depth": response.metadata.depth.value,
                    "sources_count": response.metadata.sources_count,
                },
            )

        rate_limiter = getattr(http_request.app.state, "rate_limiter", None)
        if rate_limiter is not None:
            await rate_limiter.record_usage(
                api_key_id=api_key.key_id,
                agent="research",
                tokens=response.metadata.tokens_used,
                estimated_cost=None,
            )

        if as_markdown:
            return PlainTextResponse(content=response.markdown, media_type="text/markdown")
        return response
    except ProviderNotConfiguredError as exc:
        if history_service is not None:
            await history_service.record_execution(
                request_id=request_id,
                api_key_id=api_key.key_id,
                agent="research",
                status="failed",
                provider=payload.provider.value if payload.provider is not None else None,
                model=None,
                duration_seconds=None,
                tokens_used=None,
                estimated_cost=None,
                error=str(exc),
                metadata={"depth": payload.depth.value},
            )
        logger.error("Research provider not configured", extra={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderExecutionError as exc:
        if history_service is not None:
            await history_service.record_execution(
                request_id=request_id,
                api_key_id=api_key.key_id,
                agent="research",
                status="failed",
                provider=payload.provider.value if payload.provider is not None else None,
                model=None,
                duration_seconds=None,
                tokens_used=None,
                estimated_cost=None,
                error=str(exc),
                metadata={"depth": payload.depth.value},
            )
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
        if history_service is not None:
            await history_service.record_execution(
                request_id=request_id,
                api_key_id=api_key.key_id,
                agent="research",
                status="failed",
                provider=payload.provider.value if payload.provider is not None else None,
                model=None,
                duration_seconds=None,
                tokens_used=None,
                estimated_cost=None,
                error=str(exc),
                metadata={"depth": payload.depth.value},
            )
        logger.error("Research request failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Research request failed") from exc
