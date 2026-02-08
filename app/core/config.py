"""Configuration management."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
