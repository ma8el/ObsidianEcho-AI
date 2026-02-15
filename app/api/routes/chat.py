"""Chat endpoint for testing provider integration."""

from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.chat import ChatAgent
from app.api.middleware import get_authenticated_api_key
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.auth import APIKey
from app.models.chat import ChatRequest, ChatResponse
from app.services.providers import ProviderManager, ProviderNotConfiguredError

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize provider manager and chat agent
settings = get_settings()
provider_manager = ProviderManager(settings.providers)
chat_agent = ChatAgent(provider_manager)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    http_request: Request,
    api_key: APIKey = Depends(get_authenticated_api_key),
) -> ChatResponse:
    """
    Send a message to the chat agent and get a response.

    This endpoint is for testing the provider integration.

    Args:
        request: Chat request with message and optional provider
        api_key: API key from authentication (injected)

    Returns:
        Chat response with reply and metadata

    Raises:
        HTTPException: If provider is not configured or request fails
    """
    try:
        start = perf_counter()
        response = await chat_agent.chat(
            message=payload.message,
            provider=payload.provider,
        )

        history_service = getattr(http_request.app.state, "history_service", None)
        if history_service is not None:
            await history_service.record_execution(
                request_id=getattr(http_request.state, "request_id", None),
                api_key_id=api_key.key_id,
                agent="chat",
                status="completed",
                provider=response.provider.value,
                model=response.model,
                duration_seconds=round(perf_counter() - start, 4),
                tokens_used=None,
                estimated_cost=None,
            )

        rate_limiter = getattr(http_request.app.state, "rate_limiter", None)
        if rate_limiter is not None:
            await rate_limiter.record_usage(
                api_key_id=api_key.key_id,
                agent="chat",
                tokens=None,
                estimated_cost=None,
            )
        return response

    except ProviderNotConfiguredError as e:
        history_service = getattr(http_request.app.state, "history_service", None)
        if history_service is not None:
            await history_service.record_execution(
                request_id=getattr(http_request.state, "request_id", None),
                api_key_id=api_key.key_id,
                agent="chat",
                status="failed",
                provider=payload.provider.value if payload.provider is not None else None,
                model=None,
                duration_seconds=None,
                tokens_used=None,
                estimated_cost=None,
                error=str(e),
            )
        logger.error("Provider not configured", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        history_service = getattr(http_request.app.state, "history_service", None)
        if history_service is not None:
            await history_service.record_execution(
                request_id=getattr(http_request.state, "request_id", None),
                api_key_id=api_key.key_id,
                agent="chat",
                status="failed",
                provider=payload.provider.value if payload.provider is not None else None,
                model=None,
                duration_seconds=None,
                tokens_used=None,
                estimated_cost=None,
                error=str(e),
            )
        logger.error(
            "Chat request failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Chat request failed") from e
