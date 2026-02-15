"""History tracking models."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class RequestHistoryEntry(BaseModel):
    """Stored request history entry."""

    timestamp: datetime = Field(description="Request completion timestamp")
    request_id: str | None = Field(default=None, description="Request ID")
    api_key_id: str | None = Field(default=None, description="API key identifier if authenticated")
    method: str = Field(description="HTTP method")
    path: str = Field(description="Request path")
    status_code: int = Field(description="HTTP status code")
    duration_ms: float = Field(description="Request duration in milliseconds")
    client: str | None = Field(default=None, description="Client host")
    error: str | None = Field(default=None, description="Optional error message")


class ExecutionHistoryEntry(BaseModel):
    """Stored agent execution history entry."""

    timestamp: datetime = Field(description="Execution timestamp")
    request_id: str | None = Field(default=None, description="Request ID")
    api_key_id: str | None = Field(default=None, description="API key identifier")
    agent: str = Field(description="Agent name")
    status: str = Field(description="Execution status")
    provider: str | None = Field(default=None, description="Provider used")
    model: str | None = Field(default=None, description="Model used")
    duration_seconds: float | None = Field(default=None, description="Execution duration")
    tokens_used: int | None = Field(default=None, description="Total tokens consumed")
    estimated_cost: float | None = Field(
        default=None, description="Estimated or provider-reported cost"
    )
    error: str | None = Field(default=None, description="Execution error details")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra execution metadata")


class RequestHistoryListResponse(BaseModel):
    """Paginated request history response."""

    total: int
    limit: int
    offset: int
    items: list[RequestHistoryEntry]


class ExecutionHistoryListResponse(BaseModel):
    """Paginated execution history response."""

    total: int
    limit: int
    offset: int
    items: list[ExecutionHistoryEntry]


class HistoryStatsResponse(BaseModel):
    """Aggregated history metrics."""

    api_key_id: str
    start_date: date | None = None
    end_date: date | None = None

    request_count: int
    request_error_count: int
    average_request_duration_ms: float

    execution_count: int
    execution_success_count: int
    execution_failure_count: int

    total_tokens_used: int
    total_estimated_cost: float
