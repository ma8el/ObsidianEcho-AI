"""Provider-related models and enums."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ProviderType(StrEnum):
    """Supported AI provider types."""

    OPENAI = "openai"
    XAI = "xai"


class AgentResponse(BaseModel):
    """Response from an agent execution."""

    content: str = Field(description="Generated content")
    provider: ProviderType = Field(description="Provider used")
    model: str = Field(description="Model used")
    tokens_used: int | None = Field(default=None, description="Total tokens used")
    duration_seconds: float = Field(description="Execution duration in seconds")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class ProviderHealth(BaseModel):
    """Health status for a configured provider."""

    provider: ProviderType = Field(description="Provider type")
    enabled: bool = Field(description="Whether provider is enabled in config")
    model: str | None = Field(default=None, description="Configured model name")
    api_key_present: bool = Field(
        description="Whether provider API key is available in environment"
    )
    healthy: bool = Field(description="Whether provider can be used")
    reason: str = Field(description="Human-readable status reason")
