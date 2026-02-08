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
