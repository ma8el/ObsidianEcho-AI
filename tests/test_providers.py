"""Tests for provider management."""

import pytest

from app.core.config import ProviderConfig, ProvidersConfig
from app.models.providers import ProviderType
from app.services.providers import ProviderManager, ProviderNotConfiguredError


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

    def test_get_xai_model(self, providers_config_both: ProvidersConfig) -> None:
        """Test getting XAI model instance."""
        manager = ProviderManager(providers_config_both)
        model = manager.get_model(ProviderType.XAI)
        assert model is not None
        # Check it's the right type
        from agno.models.xai import xAI

        assert isinstance(model, xAI)

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
