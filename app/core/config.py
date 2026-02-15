"""Configuration management."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.auth import APIKeyConfig


class ProviderConfig(BaseModel):
    """Configuration for an AI provider."""

    enabled: bool = Field(default=True, description="Whether this provider is enabled")
    model: str = Field(description="Default model to use")
    timeout_seconds: int = Field(default=60, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")


class ProvidersConfig(BaseModel):
    """Configuration for all AI providers."""

    openai: ProviderConfig | None = Field(default=None, description="OpenAI configuration")
    xai: ProviderConfig | None = Field(default=None, description="XAI configuration")
    default_provider: str = Field(default="openai", description="Default provider to use")


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = Field(default=True, description="Whether authentication is enabled")
    api_keys: list[APIKeyConfig] = Field(default_factory=list, description="List of valid API keys")


class HistoryConfig(BaseModel):
    """Request/execution history configuration."""

    enabled: bool = Field(default=True, description="Whether history tracking is enabled")
    storage_dir: str = Field(
        default="data/history", description="Directory for history JSONL files"
    )
    retention_days: int = Field(default=30, description="Retention window for history files")


class RateLimitPolicy(BaseModel):
    """Rate limits for request, token, and cost dimensions."""

    requests_per_minute: int | None = Field(default=None, ge=1)
    requests_per_hour: int | None = Field(default=None, ge=1)
    requests_per_day: int | None = Field(default=None, ge=1)

    tokens_per_minute: int | None = Field(default=None, ge=1)
    tokens_per_hour: int | None = Field(default=None, ge=1)
    tokens_per_day: int | None = Field(default=None, ge=1)

    cost_per_minute: float | None = Field(default=None, ge=0.0)
    cost_per_hour: float | None = Field(default=None, ge=0.0)
    cost_per_day: float | None = Field(default=None, ge=0.0)


class RateLimitsConfig(BaseModel):
    """Global and per-agent rate limiting configuration."""

    enabled: bool = Field(default=True, description="Whether rate limiting is enabled")
    default: RateLimitPolicy = Field(
        default_factory=lambda: RateLimitPolicy(
            requests_per_minute=10_000,
            requests_per_hour=100_000,
            requests_per_day=500_000,
            tokens_per_day=10_000_000,
            cost_per_day=1_000.0,
        ),
        description="Default limits applied to all agents",
    )
    agents: dict[str, RateLimitPolicy] = Field(
        default_factory=dict,
        description="Optional per-agent limit overrides",
    )
    cleanup_interval_seconds: int = Field(
        default=300,
        ge=1,
        description="Interval for in-memory counter cleanup",
    )


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = Field(default="ObsidianEcho-AI", description="Application name")
    version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")

    # CORS
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")

    # AI Providers
    providers: ProvidersConfig = Field(
        default_factory=ProvidersConfig, description="AI provider configurations"
    )

    # Authentication
    auth: AuthConfig = Field(default_factory=AuthConfig, description="Authentication configuration")

    # History
    history: HistoryConfig = Field(
        default_factory=HistoryConfig, description="Request/execution history configuration"
    )

    # Rate limiting
    rate_limits: RateLimitsConfig = Field(
        default_factory=RateLimitsConfig,
        description="API rate limiting configuration",
    )

    # Configuration file path
    config_file: str = Field(
        default="config/main.yaml",
        description="Path to configuration file",
    )

    model_config = SettingsConfigDict(
        env_prefix="OEA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def load_yaml_config(self) -> dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        config_path = Path(self.config_file)
        if not config_path.exists():
            return {}

        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def merge_yaml_config(self) -> None:
        """Merge YAML configuration into settings."""
        yaml_config = self.load_yaml_config()

        for key, value in yaml_config.items():
            if hasattr(self, key):
                # Handle nested configurations for Pydantic models
                if key == "providers" and isinstance(value, dict):
                    self.providers = ProvidersConfig(**value)
                elif key == "auth" and isinstance(value, dict):
                    self.auth = AuthConfig(**value)
                elif key == "history" and isinstance(value, dict):
                    self.history = HistoryConfig(**value)
                elif key == "rate_limits" and isinstance(value, dict):
                    self.rate_limits = RateLimitsConfig(**value)
                else:
                    setattr(self, key, value)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Application settings
    """
    settings = Settings()

    # Merge YAML config if file exists
    if os.path.exists(settings.config_file):
        settings.merge_yaml_config()

    return settings
