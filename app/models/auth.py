"""Authentication models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class APIKeyStatus(StrEnum):
    """API key status."""

    ACTIVE = "active"
    REVOKED = "revoked"


class APIKey(BaseModel):
    """API key model."""

    key_id: str = Field(description="Unique identifier for the key")
    name: str = Field(description="Human-readable name for the key")
    key_hash: str = Field(description="Hashed API key value")
    status: APIKeyStatus = Field(default=APIKeyStatus.ACTIVE, description="Key status")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    last_used_at: datetime | None = Field(default=None, description="Last usage timestamp")


class APIKeyConfig(BaseModel):
    """API key configuration from YAML."""

    key_id: str = Field(description="Unique identifier for the key")
    name: str = Field(description="Human-readable name for the key")
    key: str = Field(description="Plain text API key (will be hashed)")
    status: APIKeyStatus = Field(default=APIKeyStatus.ACTIVE, description="Key status")
