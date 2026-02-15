"""Security utilities for API key management."""

import hashlib
import secrets
from typing import Final

from app.models.auth import APIKey, APIKeyStatus

# API key format: oea_<32 random hex characters>
API_KEY_PREFIX: Final = "oea_"
API_KEY_LENGTH: Final = 32  # Length of random part (hex chars)


def generate_api_key() -> str:
    """
    Generate a new API key.

    Returns:
        A new API key in format: oea_<32 hex chars>
    """
    random_part = secrets.token_hex(API_KEY_LENGTH // 2)  # hex returns 2 chars per byte
    return f"{API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256.

    Args:
        api_key: Plain text API key

    Returns:
        Hashed API key (hex digest)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if format is valid, False otherwise
    """
    if not api_key.startswith(API_KEY_PREFIX):
        return False

    key_part = api_key[len(API_KEY_PREFIX) :]
    if len(key_part) != API_KEY_LENGTH:
        return False

    # Check if it's valid hex
    try:
        int(key_part, 16)
        return True
    except ValueError:
        return False


def verify_api_key(api_key: str, stored_key: APIKey) -> bool:
    """
    Verify an API key against a stored key.

    Args:
        api_key: Plain text API key to verify
        stored_key: Stored API key with hash

    Returns:
        True if key is valid and active, False otherwise
    """
    # Check if key is active
    if stored_key.status != APIKeyStatus.ACTIVE:
        return False

    # Verify hash
    key_hash = hash_api_key(api_key)
    return key_hash == stored_key.key_hash


def generate_request_id() -> str:
    """
    Generate a unique request ID.

    Returns:
        A unique request ID
    """
    return f"req_{secrets.token_hex(16)}"
