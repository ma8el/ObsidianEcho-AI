"""Tests for provider management."""

import pytest

from app.core.config import ProviderConfig, ProvidersConfig
from app.models.providers import ProviderType
from app.services.providers import (
    ProviderExecutionError,
    ProviderManager,
    ProviderNotConfiguredError,
)


@pytest.fixture
def openai_config() -> ProviderConfig:
    """Create OpenAI provider config for testing."""
    return ProviderConfig(
        enabled=True,
        model="gpt-4o",
        timeout_seconds=30,
        max_retries=2,
    )


@pytest.fixture
def xai_config() -> ProviderConfig:
    """Create XAI provider config for testing."""
    return ProviderConfig(
        enabled=True,
        model="grok-beta",
        timeout_seconds=30,
        max_retries=2,
    )


@pytest.fixture
def providers_config_openai_only(openai_config: ProviderConfig) -> ProvidersConfig:
    """Create providers config with only OpenAI enabled."""
    return ProvidersConfig(
        openai=openai_config,
        xai=None,
        default_provider="openai",
    )


@pytest.fixture
def providers_config_both(
    openai_config: ProviderConfig, xai_config: ProviderConfig
) -> ProvidersConfig:
    """Create providers config with both providers enabled."""
    return ProvidersConfig(
        openai=openai_config,
        xai=xai_config,
        default_provider="openai",
    )


@pytest.fixture
def providers_config_xai_disabled(
    openai_config: ProviderConfig, xai_config: ProviderConfig
) -> ProvidersConfig:
    """Create providers config with XAI disabled."""
    xai_config.enabled = False
    return ProvidersConfig(
        openai=openai_config,
        xai=xai_config,
        default_provider="openai",
    )


class TestProviderManager:
    """Test ProviderManager initialization and configuration."""

    def test_init_with_openai_only(self, providers_config_openai_only: ProvidersConfig) -> None:
        """Test ProviderManager initialization with only OpenAI."""
        manager = ProviderManager(providers_config_openai_only)
        assert manager.config == providers_config_openai_only
        available = manager.get_available_providers()
        assert ProviderType.OPENAI in available
        assert ProviderType.XAI not in available

    def test_init_with_both_providers(self, providers_config_both: ProvidersConfig) -> None:
        """Test ProviderManager initialization with both providers."""
        manager = ProviderManager(providers_config_both)
        available = manager.get_available_providers()
        assert ProviderType.OPENAI in available
        assert ProviderType.XAI in available

    def test_init_with_xai_disabled(self, providers_config_xai_disabled: ProvidersConfig) -> None:
        """Test ProviderManager initialization with XAI disabled."""
        manager = ProviderManager(providers_config_xai_disabled)
        available = manager.get_available_providers()
        assert ProviderType.OPENAI in available
        assert ProviderType.XAI not in available

    def test_init_with_no_providers(self) -> None:
        """Test ProviderManager initialization with no providers."""
        config = ProvidersConfig(
            openai=None,
            xai=None,
            default_provider="openai",
        )
        manager = ProviderManager(config)
        assert manager.get_available_providers() == []


class TestGetModel:
    """Test getting model instances from ProviderManager."""

    def test_get_openai_model(self, providers_config_openai_only: ProvidersConfig) -> None:
        """Test getting OpenAI model instance."""
        manager = ProviderManager(providers_config_openai_only)
        model = manager.get_model(ProviderType.OPENAI)
        assert model is not None
        # Check it's the right type
        from agno.models.openai import OpenAIChat

        assert isinstance(model, OpenAIChat)

    def test_openai_model_uses_configured_timeout_and_retries(
        self, providers_config_openai_only: ProvidersConfig, mocker
    ) -> None:
        """Test OpenAI model creation uses timeout/retry configuration."""
        manager = ProviderManager(providers_config_openai_only)
        mock_openai = mocker.patch("app.services.providers.OpenAIChat")
        sentinel_model = object()
        mock_openai.return_value = sentinel_model

        model = manager.get_model(ProviderType.OPENAI)

        assert model is sentinel_model
        mock_openai.assert_called_once_with(
            id="gpt-4o",
            timeout=30,
            max_retries=2,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        )

    def test_get_xai_model(self, providers_config_both: ProvidersConfig) -> None:
        """Test getting XAI model instance."""
        manager = ProviderManager(providers_config_both)
        model = manager.get_model(ProviderType.XAI)
        assert model is not None
        # Check it's the right type
        from agno.models.xai import xAI

        assert isinstance(model, xAI)

    def test_xai_model_uses_configured_timeout_and_retries(
        self, providers_config_both: ProvidersConfig, mocker
    ) -> None:
        """Test XAI model creation uses timeout/retry configuration."""
        manager = ProviderManager(providers_config_both)
        mock_xai = mocker.patch("app.services.providers.xAI")
        sentinel_model = object()
        mock_xai.return_value = sentinel_model

        model = manager.get_model(ProviderType.XAI)

        assert model is sentinel_model
        mock_xai.assert_called_once_with(
            id="grok-beta",
            timeout=30,
            max_retries=2,
            retries=2,
            delay_between_retries=1,
            exponential_backoff=True,
        )

    def test_get_default_provider_model(
        self, providers_config_openai_only: ProvidersConfig
    ) -> None:
        """Test getting model with no provider specified (uses default)."""
        manager = ProviderManager(providers_config_openai_only)
        model = manager.get_model()  # Should use default (openai)
        assert model is not None
        from agno.models.openai import OpenAIChat

        assert isinstance(model, OpenAIChat)

    def test_get_model_not_configured(self, providers_config_openai_only: ProvidersConfig) -> None:
        """Test getting model for unconfigured provider raises error."""
        manager = ProviderManager(providers_config_openai_only)
        with pytest.raises(ProviderNotConfiguredError) as exc_info:
            manager.get_model(ProviderType.XAI)
        assert "not configured" in str(exc_info.value).lower()

    def test_get_model_disabled_provider(
        self, providers_config_xai_disabled: ProvidersConfig
    ) -> None:
        """Test getting model for disabled provider raises error."""
        manager = ProviderManager(providers_config_xai_disabled)
        with pytest.raises(ProviderNotConfiguredError):
            manager.get_model(ProviderType.XAI)


class TestDefaultProvider:
    """Test default provider logic."""

    def test_get_default_provider(self, providers_config_both: ProvidersConfig) -> None:
        """Test getting default provider."""
        manager = ProviderManager(providers_config_both)
        default = manager.get_default_provider()
        assert default == ProviderType.OPENAI

    def test_default_provider_fallback(self, providers_config_both: ProvidersConfig) -> None:
        """Test fallback when default provider is not available."""
        # Set default to XAI but disable it
        providers_config_both.default_provider = "xai"
        assert providers_config_both.xai is not None
        providers_config_both.xai.enabled = False

        manager = ProviderManager(providers_config_both)
        default = manager.get_default_provider()
        # Should fallback to OpenAI (the only available one)
        assert default == ProviderType.OPENAI

    def test_default_provider_no_providers_available(self) -> None:
        """Test error when no providers are available."""
        config = ProvidersConfig(
            openai=None,
            xai=None,
            default_provider="openai",
        )
        manager = ProviderManager(config)
        with pytest.raises(ProviderNotConfiguredError) as exc_info:
            manager.get_default_provider()
        assert "no providers" in str(exc_info.value).lower()


class TestAvailableProviders:
    """Test getting list of available providers."""

    def test_get_available_providers_single(
        self, providers_config_openai_only: ProvidersConfig
    ) -> None:
        """Test getting available providers with single provider."""
        manager = ProviderManager(providers_config_openai_only)
        available = manager.get_available_providers()
        assert len(available) == 1
        assert ProviderType.OPENAI in available

    def test_get_available_providers_multiple(self, providers_config_both: ProvidersConfig) -> None:
        """Test getting available providers with multiple providers."""
        manager = ProviderManager(providers_config_both)
        available = manager.get_available_providers()
        assert len(available) == 2
        assert ProviderType.OPENAI in available
        assert ProviderType.XAI in available

    def test_get_available_providers_none(self) -> None:
        """Test getting available providers when none are configured."""
        config = ProvidersConfig(
            openai=None,
            xai=None,
            default_provider="openai",
        )
        manager = ProviderManager(config)
        available = manager.get_available_providers()
        assert len(available) == 0


class TestProviderFallback:
    """Test provider runtime fallback behavior."""

    @pytest.mark.asyncio
    async def test_run_with_fallback_uses_second_provider_on_failure(
        self, providers_config_both: ProvidersConfig
    ) -> None:
        """Test fallback to next provider when primary fails."""
        manager = ProviderManager(providers_config_both)

        async def operation(provider: ProviderType) -> str:
            if provider == ProviderType.OPENAI:
                raise RuntimeError("OpenAI unavailable")
            return f"ok:{provider.value}"

        result, used_provider = await manager.run_with_fallback(
            operation=operation,
            preferred_provider=ProviderType.OPENAI,
        )

        assert result == "ok:xai"
        assert used_provider == ProviderType.XAI

    @pytest.mark.asyncio
    async def test_run_with_fallback_raises_after_all_fail(
        self, providers_config_both: ProvidersConfig
    ) -> None:
        """Test error when all providers fail during execution."""
        manager = ProviderManager(providers_config_both)

        async def operation(provider: ProviderType) -> str:
            raise RuntimeError(f"{provider.value} failed")

        with pytest.raises(ProviderExecutionError) as exc_info:
            await manager.run_with_fallback(
                operation=operation,
                preferred_provider=ProviderType.OPENAI,
            )

        error = exc_info.value
        assert error.attempted_providers == [ProviderType.OPENAI, ProviderType.XAI]
        assert isinstance(error.last_error, RuntimeError)
