"""Simple chat agent for testing provider integration."""

from agno.agent import Agent

from app.core.logging import get_logger
from app.models.chat import ChatResponse
from app.models.providers import ProviderType
from app.services.providers import ProviderManager

logger = get_logger(__name__)


class ChatAgent:
    """
    Simple chat agent for basic conversation.

    This agent is primarily for testing the provider integration
    and demonstrating the basic agent pattern.
    """

    def __init__(self, provider_manager: ProviderManager) -> None:
        """
        Initialize the chat agent.

        Args:
            provider_manager: Provider manager instance
        """
        self.provider_manager = provider_manager

    async def _chat_with_provider(self, message: str, provider: ProviderType) -> tuple[str, str]:
        """Execute a chat request with a specific provider."""
        model = self.provider_manager.get_model(provider)
        model_name = self.provider_manager.get_model_name(provider)

        agent = Agent(
            model=model,
            instructions="You are a helpful AI assistant. Be concise and friendly.",
            markdown=True,
        )

        response = await agent.arun(message)
        reply = str(response.content) if hasattr(response, "content") else str(response)
        return reply, model_name

    async def chat(self, message: str, provider: ProviderType | None = None) -> ChatResponse:
        """
        Send a message and get a response.

        Args:
            message: User message
            provider: Provider to use (None for default)

        Returns:
            Chat response with reply and metadata
        """
        requested_provider = provider.value if provider is not None else "default"
        logger.info("Processing chat message", extra={"requested_provider": requested_provider})

        (reply, model_name), used_provider = await self.provider_manager.run_with_fallback(
            operation=lambda candidate: self._chat_with_provider(message, candidate),
            preferred_provider=provider,
        )

        logger.info(
            "Chat message processed successfully",
            extra={
                "provider": used_provider.value,
                "model": model_name,
                "reply_length": len(reply),
            },
        )

        return ChatResponse(
            reply=reply,
            provider=used_provider,
            model=model_name,
        )
