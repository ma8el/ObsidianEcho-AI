"""Tests for security utilities."""

from app.core.security import (
    generate_api_key,
    generate_request_id,
    hash_api_key,
    validate_api_key_format,
    verify_api_key,
)
from app.models.auth import APIKey, APIKeyStatus


class TestAPIKeyGeneration:
    """Tests for API key generation."""

    def test_generate_api_key_format(self):
        """Test that generated API keys have correct format."""
        key = generate_api_key()
        assert key.startswith("oea_")
        assert len(key) == 36  # oea_ (4) + 32 hex chars

    def test_generate_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100  # All should be unique

    def test_generate_api_key_hex_chars(self):
        """Test that generated API keys contain only hex characters."""
        key = generate_api_key()
        key_part = key[4:]  # Remove oea_ prefix
        # Should not raise ValueError
        int(key_part, 16)


class TestAPIKeyHashing:
    """Tests for API key hashing."""

    def test_hash_api_key_deterministic(self):
        """Test that hashing is deterministic."""
        key = "oea_0123456789abcdef0123456789abcdef"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes."""
        key1 = "oea_0123456789abcdef0123456789abcdef"
        key2 = "oea_fedcba9876543210fedcba9876543210"
        hash1 = hash_api_key(key1)
        hash2 = hash_api_key(key2)
        assert hash1 != hash2

    def test_hash_api_key_length(self):
        """Test that hash has expected length (SHA-256 hex = 64 chars)."""
        key = generate_api_key()
        hashed = hash_api_key(key)
        assert len(hashed) == 64


class TestAPIKeyValidation:
    """Tests for API key format validation."""

    def test_validate_valid_key(self):
        """Test validation of valid API key."""
        key = generate_api_key()
        assert validate_api_key_format(key) is True

    def test_validate_wrong_prefix(self):
        """Test validation fails for wrong prefix."""
        key = "xxx_0123456789abcdef0123456789abcdef"
        assert validate_api_key_format(key) is False

    def test_validate_missing_prefix(self):
        """Test validation fails for missing prefix."""
        key = "0123456789abcdef0123456789abcdef"
        assert validate_api_key_format(key) is False

    def test_validate_wrong_length(self):
        """Test validation fails for wrong length."""
        key = "oea_0123456789abcdef"  # Too short
        assert validate_api_key_format(key) is False

    def test_validate_non_hex_chars(self):
        """Test validation fails for non-hex characters."""
        key = "oea_0123456789abcdefghij123456789ab"
        assert validate_api_key_format(key) is False

    def test_validate_empty_key(self):
        """Test validation fails for empty key."""
        assert validate_api_key_format("") is False


class TestAPIKeyVerification:
    """Tests for API key verification."""

    def test_verify_valid_active_key(self):
        """Test verification of valid active key."""
        key = generate_api_key()
        stored_key = APIKey(
            key_id="test",
            name="Test Key",
            key_hash=hash_api_key(key),
            status=APIKeyStatus.ACTIVE,
        )
        assert verify_api_key(key, stored_key) is True

    def test_verify_revoked_key(self):
        """Test verification fails for revoked key."""
        key = generate_api_key()
        stored_key = APIKey(
            key_id="test",
            name="Test Key",
            key_hash=hash_api_key(key),
            status=APIKeyStatus.REVOKED,
        )
        assert verify_api_key(key, stored_key) is False

    def test_verify_wrong_key(self):
        """Test verification fails for wrong key."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        stored_key = APIKey(
            key_id="test",
            name="Test Key",
            key_hash=hash_api_key(key1),
            status=APIKeyStatus.ACTIVE,
        )
        assert verify_api_key(key2, stored_key) is False


class TestRequestIDGeneration:
    """Tests for request ID generation."""

    def test_generate_request_id_format(self):
        """Test that generated request IDs have correct format."""
        req_id = generate_request_id()
        assert req_id.startswith("req_")
        assert len(req_id) == 36  # req_ (4) + 32 hex chars

    def test_generate_request_id_uniqueness(self):
        """Test that generated request IDs are unique."""
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100  # All should be unique

    def test_generate_request_id_hex_chars(self):
        """Test that generated request IDs contain only hex characters."""
        req_id = generate_request_id()
        id_part = req_id[4:]  # Remove req_ prefix
        # Should not raise ValueError
        int(id_part, 16)
