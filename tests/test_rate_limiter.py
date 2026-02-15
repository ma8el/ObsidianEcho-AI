"""Tests for rate limiter service and API integration."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.core.config import RateLimitPolicy, RateLimitsConfig
from app.main import create_app
from app.main import settings as app_settings
from app.models.chat import ChatResponse
from app.models.providers import ProviderType
from app.services.rate_limiter import RateLimiter

TEST_HEADERS = {"X-API-Key": "oea_0123456789abcdef0123456789abcdef"}


@pytest.fixture
def rate_limited_client() -> Iterator[TestClient]:
    """Create test client with strict test-specific rate limits."""
    original = app_settings.rate_limits.model_copy(deep=True)
    app_settings.rate_limits = RateLimitsConfig(
        enabled=True,
        default=RateLimitPolicy(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=1_000,
            tokens_per_day=1_000,
            cost_per_day=100.0,
        ),
        agents={
            "chat": RateLimitPolicy(requests_per_minute=1, requests_per_hour=5, requests_per_day=20)
        },
        cleanup_interval_seconds=1,
    )

    app = create_app()
    with TestClient(app) as client:
        yield client

    app_settings.rate_limits = original


class TestRateLimiterService:
    """Unit tests for in-memory limiter behavior."""

    @pytest.mark.asyncio
    async def test_per_key_request_limits(self) -> None:
        limiter = RateLimiter(
            RateLimitsConfig(
                enabled=True,
                default=RateLimitPolicy(requests_per_minute=1),
                cleanup_interval_seconds=1,
            )
        )

        first = await limiter.consume_request(api_key_id="key-1", agent="chat")
        second = await limiter.consume_request(api_key_id="key-1", agent="chat")
        other_key = await limiter.consume_request(api_key_id="key-2", agent="chat")

        assert first is not None and first.allowed
        assert second is not None and not second.allowed
        assert other_key is not None and other_key.allowed

    @pytest.mark.asyncio
    async def test_token_and_cost_limits(self) -> None:
        limiter = RateLimiter(
            RateLimitsConfig(
                enabled=True,
                default=RateLimitPolicy(
                    requests_per_minute=10,
                    tokens_per_day=3,
                    cost_per_day=1.0,
                ),
                cleanup_interval_seconds=1,
            )
        )

        await limiter.record_usage(
            api_key_id="token-key", agent="research", tokens=3, estimated_cost=0.0
        )
        token_block = await limiter.consume_request(api_key_id="token-key", agent="research")
        assert token_block is not None and not token_block.allowed
        assert token_block.dimension == "tokens"

        await limiter.record_usage(
            api_key_id="cost-key", agent="research", tokens=0, estimated_cost=1.0
        )
        cost_block = await limiter.consume_request(api_key_id="cost-key", agent="research")
        assert cost_block is not None and not cost_block.allowed
        assert cost_block.dimension == "cost"


class TestRateLimiterAPI:
    """Integration tests for endpoint-level rate limiting."""

    def test_headers_present_on_successful_response(self, rate_limited_client: TestClient) -> None:
        response = rate_limited_client.get("/health", headers=TEST_HEADERS)

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_chat_agent_specific_limit(
        self, rate_limited_client: TestClient, mocker: MockerFixture
    ) -> None:
        mock_chat = mocker.patch("app.api.routes.chat.chat_agent.chat")
        mock_chat.return_value = ChatResponse(
            reply="hi",
            provider=ProviderType.OPENAI,
            model="gpt-4o",
        )

        first = rate_limited_client.post("/chat", json={"message": "hello"}, headers=TEST_HEADERS)
        second = rate_limited_client.post("/chat", json={"message": "again"}, headers=TEST_HEADERS)
        health = rate_limited_client.get("/health", headers=TEST_HEADERS)

        assert first.status_code == 200
        assert second.status_code == 429
        assert "Retry-After" in second.headers
        assert health.status_code == 200
