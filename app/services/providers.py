"""Provider management and agno integration."""

from agno.models.openai import OpenAIChat
from agno.models.xai import xAI

from app.core.config import ProvidersConfig
from app.core.logging import get_logger
from app.models.providers import ProviderType

logger = get_logger(__name__)


class ProviderError(Exception):
    """Base exception for provider-related errors."""

    pass


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is not configured."""

    pass


class ProviderManager:
    """
    Manages AI provider configurations.

    Provides methods to create agno model instances for configured providers.
    This allows agents to be created with system prompts and other configurations
    at a higher level.
    """

    def __init__(self, config: ProvidersConfig) -> None:
        """
        Initialize the provider manager.

        Args:
            config: Provider configuration
        """
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that at least one provider is configured."""
        has_provider = False

        if self.config.openai and self.config.openai.enabled:
            has_provider = True
            logger.info(
                "OpenAI provider configured",
                extra={"model": self.config.openai.model},
            )

        if self.config.xai and self.config.xai.enabled:
            has_provider = True
            logger.info(
                "XAI provider configured",
                extra={"model": self.config.xai.model},
            )

        if not has_provider:
            logger.warning("No AI providers are configured and enabled")

    def get_model(self, provider: ProviderType | None = None) -> OpenAIChat | xAI:
        """
        Get a model instance for the specified provider.

        This returns an agno model object that can be passed to Agent().
        The caller can then add system prompts and other agent configuration.

        Args:
            provider: Provider type, or None to use default

        Returns:
            agno model instance (OpenAIChat or xAI)

        Raises:
            ProviderNotConfiguredError: If the provider is not configured

        Example:
            ```python
            model = provider_manager.get_model(ProviderType.OPENAI)
            agent = Agent(
                model=model,
                instructions="You are a helpful assistant",
                markdown=True
            )
            ```
        """
        if provider is None:
            provider = self.get_default_provider()

        if provider == ProviderType.OPENAI:
            return self._get_openai_model()
        elif provider == ProviderType.XAI:
            return self._get_xai_model()
        else:
            raise ProviderNotConfiguredError(f"Unsupported provider: {provider.value}")

    def _get_openai_model(self) -> OpenAIChat:
        """
        Get OpenAI model instance.

        API key is read from OPENAI_API_KEY environment variable.

        Returns:
            OpenAIChat model instance

        Raises:
            ProviderNotConfiguredError: If OpenAI is not configured
        """
        if not self.config.openai or not self.config.openai.enabled:
            raise ProviderNotConfiguredError("OpenAI provider is not configured or enabled")

        config = self.config.openai
        return OpenAIChat(
            id=config.model,
        )

    def _get_xai_model(self) -> xAI:
        """
        Get xAI model instance.

        API key is read from XAI_API_KEY environment variable.

        Returns:
            xAI model instance

        Raises:
            ProviderNotConfiguredError: If XAI is not configured
        """
        if not self.config.xai or not self.config.xai.enabled:
            raise ProviderNotConfiguredError("XAI provider is not configured or enabled")

        config = self.config.xai
        return xAI(
            id=config.model,
            retries=config.max_retries,
            delay_between_retries=1,
            exponential_backoff=True,
        )

    def get_available_providers(self) -> list[ProviderType]:
        """
        Get list of configured and enabled providers.

        Returns:
            List of available provider types
        """
        providers = []
        if self.config.openai and self.config.openai.enabled:
            providers.append(ProviderType.OPENAI)
        if self.config.xai and self.config.xai.enabled:
            providers.append(ProviderType.XAI)
        return providers

    def get_default_provider(self) -> ProviderType:
        """
        Get the default provider type.

        Returns:
            Default provider type

        Raises:
            ProviderNotConfiguredError: If default provider is not available
        """
        default = ProviderType(self.config.default_provider)
        available = self.get_available_providers()

        if default not in available:
            if not available:
                raise ProviderNotConfiguredError("No providers are configured")
            # Fallback to first available provider
            default = available[0]
            logger.warning(
                "Default provider not available, using fallback",
                extra={
                    "requested": self.config.default_provider,
                    "fallback": default.value,
                },
            )

        return default

    def get_model_name(self, provider: ProviderType) -> str:
        """
        Get the configured model name for a provider.

        Args:
            provider: Provider type

        Returns:
            Model name

        Raises:
            ProviderNotConfiguredError: If the provider is not configured
        """
        if provider == ProviderType.OPENAI:
            if not self.config.openai or not self.config.openai.enabled:
                raise ProviderNotConfiguredError("OpenAI provider is not configured or enabled")
            return self.config.openai.model
        elif provider == ProviderType.XAI:
            if not self.config.xai or not self.config.xai.enabled:
                raise ProviderNotConfiguredError("XAI provider is not configured or enabled")
            return self.config.xai.model
        else:
            raise ProviderNotConfiguredError(f"Unsupported provider: {provider.value}")
