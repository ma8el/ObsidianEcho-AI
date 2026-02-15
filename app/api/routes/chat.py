"""Chat endpoint for testing provider integration."""

from fastapi import APIRouter, Depends, HTTPException

from app.agents.chat import ChatAgent
from app.api.middleware import get_current_api_key
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
    request: ChatRequest,
    api_key: APIKey = Depends(get_current_api_key),
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
        response = await chat_agent.chat(
            message=request.message,
            provider=request.provider,
        )
        return response

    except ProviderNotConfiguredError as e:
        logger.error("Provider not configured", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error(
            "Chat request failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Chat request failed") from e
