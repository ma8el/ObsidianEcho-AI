"""Task queue models."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.models.providers import ProviderType
from app.models.research import ResearchDepth


class AgentType(StrEnum):
    """Supported agent types for async task execution."""

    CHAT = "chat"
    RESEARCH = "research"


class TaskStatus(StrEnum):
    """Task lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatTaskRequest(BaseModel):
    """Submit a chat task."""

    agent: Literal[AgentType.CHAT] = Field(default=AgentType.CHAT)
    message: str = Field(min_length=1, description="Message to send to chat agent")
    provider: ProviderType | None = Field(
        default=None,
        description="Optional provider override",
    )
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (higher = sooner)")


class ResearchTaskRequest(BaseModel):
    """Submit a research task."""

    agent: Literal[AgentType.RESEARCH] = Field(default=AgentType.RESEARCH)
    topic: str = Field(min_length=3, description="Research topic")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Research depth")
    provider: ProviderType | None = Field(
        default=None,
        description="Optional provider override",
    )
    focus_areas: list[str] = Field(default_factory=list, description="Optional focus areas")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (higher = sooner)")


TaskRequest = Annotated[
    ChatTaskRequest | ResearchTaskRequest,
    Field(discriminator="agent"),
]


class TaskSubmissionResponse(BaseModel):
    """Response returned when a task is submitted."""

    task_id: str
    status: TaskStatus
    status_url: str


class TaskStatusResponse(BaseModel):
    """Task status payload."""

    task_id: str
    agent: AgentType
    status: TaskStatus
    priority: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    error: str | None = None


class TaskResultResponse(TaskStatusResponse):
    """Task result payload."""

    result: dict[str, Any] | None = None


class TaskListResponse(BaseModel):
    """Paginated task list payload."""

    total: int
    limit: int
    offset: int
    tasks: list[TaskStatusResponse]
