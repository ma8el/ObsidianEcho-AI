"""Provider management and agno integration."""

import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

from agno.models.openai import OpenAIChat
from agno.models.openai.responses import OpenAIResponses
from agno.models.xai import xAI

from app.core.config import ProvidersConfig
from app.core.logging import get_logger
from app.models.providers import ProviderHealth, ProviderType
from app.models.research import ResearchDepth

logger = get_logger(__name__)


class ProviderError(Exception):
    """Base exception for provider-related errors."""

    pass


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is not configured."""

    pass


class ProviderExecutionError(ProviderError):
    """Raised when all provider execution attempts fail."""

    def __init__(
        self,
        message: str,
        attempted_providers: list[ProviderType],
        last_error: Exception,
    ) -> None:
        super().__init__(message)
        self.attempted_providers = attempted_providers
        self.last_error = last_error


T = TypeVar("T")


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
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            retries=config.max_retries,
            delay_between_retries=1,
            exponential_backoff=True,
        )

    def _get_openai_research_model(self, depth: ResearchDepth) -> OpenAIResponses:
        """
        Get OpenAI Responses API model configured for research workflows.

        Uses native web-search tool integration.
        """
        if not self.config.openai or not self.config.openai.enabled:
            raise ProviderNotConfiguredError("OpenAI provider is not configured or enabled")

        config = self.config.openai
        request_params: dict[str, list[dict[str, str]]] = {}

        # For non deep-research models, explicitly attach web_search_preview.
        if "deep-research" not in config.model:
            request_params["tools"] = [{"type": "web_search_preview"}]

        return OpenAIResponses(
            id=config.model,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            retries=config.max_retries,
            delay_between_retries=1,
            exponential_backoff=True,
            request_params=request_params or None,
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
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            retries=config.max_retries,
            delay_between_retries=1,
            exponential_backoff=True,
        )

    def _get_xai_research_model(self) -> xAI:
        """
        Get xAI model configured for research workflows.

        Enables provider-native live search parameters.
        """
        if not self.config.xai or not self.config.xai.enabled:
            raise ProviderNotConfiguredError("XAI provider is not configured or enabled")

        config = self.config.xai
        return xAI(
            id=config.model,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            retries=config.max_retries,
            delay_between_retries=1,
            exponential_backoff=True,
            search_parameters={"mode": "on"},
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

    def get_research_model(
        self, provider: ProviderType | None = None, depth: ResearchDepth = ResearchDepth.STANDARD
    ) -> OpenAIResponses | xAI:
        """
        Get a research-configured model with native web-search capabilities.

        Args:
            provider: Provider type, or None to use default
            depth: Research depth (kept for future provider-specific tuning)
        """
        if provider is None:
            provider = self.get_default_provider()

        if provider == ProviderType.OPENAI:
            return self._get_openai_research_model(depth=depth)
        elif provider == ProviderType.XAI:
            return self._get_xai_research_model()
        else:
            raise ProviderNotConfiguredError(f"Unsupported provider: {provider.value}")

    def get_research_model_name(self, provider: ProviderType, depth: ResearchDepth) -> str:
        """
        Get model name for research execution.

        Args:
            provider: Provider type
            depth: Research depth (reserved for future specialized model mapping)
        """
        _ = depth
        return self.get_model_name(provider)

    def check_provider_health(self, provider: ProviderType) -> ProviderHealth:
        """
        Check health status for a provider.

        Health is considered "ready" when:
        - provider is configured and enabled
        - provider API key exists in the environment
        - model instance can be created
        """
        if provider == ProviderType.OPENAI:
            config = self.config.openai
            env_var = "OPENAI_API_KEY"
        elif provider == ProviderType.XAI:
            config = self.config.xai
            env_var = "XAI_API_KEY"
        else:
            raise ProviderNotConfiguredError(f"Unsupported provider: {provider.value}")

        if config is None:
            return ProviderHealth(
                provider=provider,
                enabled=False,
                model=None,
                api_key_present=False,
                healthy=False,
                reason="Provider not configured",
            )

        api_key_present = bool(os.getenv(env_var))
        if not config.enabled:
            return ProviderHealth(
                provider=provider,
                enabled=False,
                model=config.model,
                api_key_present=api_key_present,
                healthy=False,
                reason="Provider disabled",
            )

        if not api_key_present:
            return ProviderHealth(
                provider=provider,
                enabled=True,
                model=config.model,
                api_key_present=False,
                healthy=False,
                reason=f"Missing environment variable: {env_var}",
            )

        try:
            self.get_model(provider)
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(
                provider=provider,
                enabled=True,
                model=config.model,
                api_key_present=True,
                healthy=False,
                reason=f"Model initialization failed: {exc}",
            )

        return ProviderHealth(
            provider=provider,
            enabled=True,
            model=config.model,
            api_key_present=True,
            healthy=True,
            reason="Provider is ready",
        )

    def get_providers_health(self, include_disabled: bool = True) -> list[ProviderHealth]:
        """
        Get health status for all known providers.

        Args:
            include_disabled: Include disabled/unconfigured providers in output

        Returns:
            Provider health statuses
        """
        providers = [ProviderType.OPENAI, ProviderType.XAI]
        health = [self.check_provider_health(provider) for provider in providers]
        if include_disabled:
            return health
        return [status for status in health if status.enabled]

    def get_provider_chain(
        self, preferred_provider: ProviderType | None = None
    ) -> list[ProviderType]:
        """
        Get ordered providers to try for execution.

        Preferred/default provider is tried first, then remaining enabled providers.

        Args:
            preferred_provider: Preferred provider, or None for configured default

        Returns:
            Ordered list of providers to attempt

        Raises:
            ProviderNotConfiguredError: If no providers are available
        """
        available = self.get_available_providers()
        if not available:
            raise ProviderNotConfiguredError("No providers are configured")

        first = (
            preferred_provider if preferred_provider is not None else self.get_default_provider()
        )

        if first not in available:
            raise ProviderNotConfiguredError(f"{first.value} provider is not configured or enabled")

        return [first, *[provider for provider in available if provider != first]]

    async def run_with_fallback(
        self,
        operation: Callable[[ProviderType], Awaitable[T]],
        preferred_provider: ProviderType | None = None,
    ) -> tuple[T, ProviderType]:
        """
        Execute an async provider operation with fallback to other providers.

        Args:
            operation: Async callable that executes work for a given provider
            preferred_provider: Provider to try first, or None for default

        Returns:
            Tuple of operation result and provider used

        Raises:
            ProviderExecutionError: If all providers fail during execution
            ProviderNotConfiguredError: If no valid providers are configured
        """
        chain = self.get_provider_chain(preferred_provider)
        errors: list[tuple[ProviderType, Exception]] = []

        for provider in chain:
            try:
                result = await operation(provider)
                return result, provider
            except Exception as exc:  # noqa: BLE001
                errors.append((provider, exc))
                logger.warning(
                    "Provider execution failed, trying next provider if available",
                    extra={"provider": provider.value, "error": str(exc)},
                )

        attempted = [provider for provider, _ in errors]
        last_error = errors[-1][1]
        attempted_str = ", ".join(provider.value for provider in attempted)
        raise ProviderExecutionError(
            message=f"All provider execution attempts failed: {attempted_str}",
            attempted_providers=attempted,
            last_error=last_error,
        ) from last_error
