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

    async def chat(self, message: str, provider: ProviderType | None = None) -> ChatResponse:
        """
        Send a message and get a response.

        Args:
            message: User message
            provider: Provider to use (None for default)

        Returns:
            Chat response with reply and metadata
        """
        # Use default provider if none specified
        if provider is None:
            provider = self.provider_manager.get_default_provider()

        # Get model and model name from provider manager
        model = self.provider_manager.get_model(provider)
        model_name = self.provider_manager.get_model_name(provider)

        logger.info(
            "Processing chat message",
            extra={"provider": provider.value, "model": model_name},
        )

        # Create agent with the model
        agent = Agent(
            model=model,
            instructions="You are a helpful AI assistant. Be concise and friendly.",
            markdown=True,
        )

        # Run the agent asynchronously
        response = await agent.arun(message)

        # Extract the response content
        reply = str(response.content) if hasattr(response, "content") else str(response)

        logger.info(
            "Chat message processed successfully",
            extra={"provider": provider.value, "reply_length": len(reply)},
        )

        return ChatResponse(
            reply=reply,
            provider=provider,
            model=model_name,
        )
