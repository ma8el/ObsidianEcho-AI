"""Authentication models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


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
    key: str | None = Field(
        default=None,
        description="Plain text API key (hashed during authentication)",
    )
    key_hash: str | None = Field(
        default=None,
        description="Pre-hashed API key (SHA-256 hex)",
    )
    status: APIKeyStatus = Field(default=APIKeyStatus.ACTIVE, description="Key status")

    @model_validator(mode="after")
    def validate_key_material(self) -> "APIKeyConfig":
        """
        Ensure exactly one key material field is provided.

        Either `key` (plain text) or `key_hash` (SHA-256) must be set.
        """
        if self.key and self.key_hash:
            raise ValueError("Provide only one of 'key' or 'key_hash'")

        if not self.key and not self.key_hash:
            raise ValueError("One of 'key' or 'key_hash' must be provided")

        if self.key_hash:
            key_hash = self.key_hash.lower()
            if len(key_hash) != 64 or any(c not in "0123456789abcdef" for c in key_hash):
                raise ValueError("'key_hash' must be a 64-character hexadecimal SHA-256 hash")
            self.key_hash = key_hash

        return self
