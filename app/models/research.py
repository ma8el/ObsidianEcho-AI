"""Research agent request/response models."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.providers import ProviderType


class ResearchDepth(StrEnum):
    """Depth levels for research analysis."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchRequest(BaseModel):
    """Request model for research agent."""

    topic: str = Field(min_length=3, description="Research topic or question")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Research depth level")
    provider: ProviderType | None = Field(
        default=None,
        description="Provider to use (defaults to configured default)",
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Optional focus areas to emphasize in research",
    )


class SourceReference(BaseModel):
    """A structured source citation."""

    url: str = Field(description="Source URL")
    title: str | None = Field(default=None, description="Optional source title")


class ResearchMetadata(BaseModel):
    """Execution metadata for research requests."""

    provider: ProviderType = Field(description="Provider that was used")
    model: str = Field(description="Model that was used")
    depth: ResearchDepth = Field(description="Depth requested")
    duration_seconds: float = Field(description="Execution duration in seconds")
    tokens_used: int | None = Field(default=None, description="Total tokens used if available")
    sources_count: int = Field(description="Number of extracted sources")


class ResearchResponse(BaseModel):
    """Response model for research endpoint."""

    topic: str = Field(description="Research topic")
    markdown: str = Field(description="Obsidian-ready markdown note")
    sources: list[SourceReference] = Field(default_factory=list, description="Extracted sources")
    metadata: ResearchMetadata = Field(description="Execution metadata")
