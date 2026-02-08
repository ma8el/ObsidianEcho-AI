"""Chat-related models."""

from pydantic import BaseModel, Field

from app.models.providers import ProviderType


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(description="User message to send to the agent")
    provider: ProviderType | None = Field(
        default=None, description="Provider to use (defaults to configured default)"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    reply: str = Field(description="Agent's reply")
    provider: ProviderType = Field(description="Provider that was used")
    model: str = Field(description="Model that was used")
