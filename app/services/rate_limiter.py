"""In-memory per-key rate limiting with multi-dimensional windows."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Literal

from app.core.config import RateLimitPolicy, RateLimitsConfig

WindowName = Literal["minute", "hour", "day"]
DimensionName = Literal["requests", "tokens", "cost"]

WINDOW_SECONDS: dict[WindowName, int] = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}
DIMENSIONS: tuple[DimensionName, DimensionName, DimensionName] = ("requests", "tokens", "cost")


@dataclass(frozen=True)
class CounterKey:
    """Counter identity for one key/scope/dimension/window bucket."""

    api_key_id: str
    agent: str
    dimension: DimensionName
    window_seconds: int
    bucket_start: int


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of a single rate-limit check for headers and allow/deny logic."""

    allowed: bool
    dimension: DimensionName
    window: WindowName
    limit: float
    used: float
    remaining: float
    reset_at: int
    retry_after_seconds: int
    detail: str


class RateLimiter:
    """Tracks usage in-memory and evaluates per-key rate limits."""

    def __init__(self, config: RateLimitsConfig) -> None:
        self._config = config
        self._usage: dict[CounterKey, float] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup_monotonic = time.monotonic()
        self._max_window_seconds = max(WINDOW_SECONDS.values())

    @property
    def enabled(self) -> bool:
        """Whether rate limiting is enabled."""
        return self._config.enabled

    async def consume_request(self, *, api_key_id: str, agent: str) -> RateLimitDecision | None:
        """
        Evaluate request/token/cost limits and consume one request if allowed.

        Returns a decision for response headers and deny/allow signaling.
        """
        if not self.enabled:
            return None

        async with self._lock:
            now = time.time()
            self._cleanup_if_needed(now=now)
            policy = self._resolve_policy(agent)

            # Validate all dimensions before mutating counters.
            for dimension in DIMENSIONS:
                increment = 1.0 if dimension == "requests" else 0.0
                exceeded = self._first_exceeded_limit(
                    api_key_id=api_key_id,
                    agent=agent,
                    policy=policy,
                    dimension=dimension,
                    increment=increment,
                    now=now,
                )
                if exceeded is not None:
                    return exceeded

            # Consume request counters across all configured request windows.
            for _window_name, window_seconds, _limit in self._iter_limits(
                policy=policy,
                dimension="requests",
            ):
                key = self._counter_key(
                    api_key_id=api_key_id,
                    agent=agent,
                    dimension="requests",
                    window_seconds=window_seconds,
                    now=now,
                )
                self._usage[key] = self._usage.get(key, 0.0) + 1.0

            return self._build_primary_request_decision(
                api_key_id=api_key_id,
                agent=agent,
                policy=policy,
                now=now,
            )

    async def record_usage(
        self,
        *,
        api_key_id: str,
        agent: str,
        tokens: int | None,
        estimated_cost: float | None,
    ) -> None:
        """Record post-execution token/cost usage for future enforcement."""
        if not self.enabled:
            return

        token_increment = float(max(tokens or 0, 0))
        cost_increment = max(estimated_cost or 0.0, 0.0)
        if token_increment == 0.0 and cost_increment == 0.0:
            return

        async with self._lock:
            now = time.time()
            self._cleanup_if_needed(now=now)
            policy = self._resolve_policy(agent)

            if token_increment > 0.0:
                self._increment_dimension(
                    api_key_id=api_key_id,
                    agent=agent,
                    policy=policy,
                    dimension="tokens",
                    amount=token_increment,
                    now=now,
                )
            if cost_increment > 0.0:
                self._increment_dimension(
                    api_key_id=api_key_id,
                    agent=agent,
                    policy=policy,
                    dimension="cost",
                    amount=cost_increment,
                    now=now,
                )

    @staticmethod
    def build_headers(decision: RateLimitDecision | None) -> dict[str, str]:
        """Build HTTP headers describing current limit state."""
        if decision is None:
            return {}

        headers = {
            "X-RateLimit-Limit": _format_limit_number(decision.limit),
            "X-RateLimit-Remaining": _format_limit_number(decision.remaining),
            "X-RateLimit-Reset": str(decision.reset_at),
            "X-RateLimit-Dimension": decision.dimension,
            "X-RateLimit-Window": decision.window,
        }
        if not decision.allowed:
            headers["Retry-After"] = str(decision.retry_after_seconds)
        return headers

    def _resolve_policy(self, agent: str) -> RateLimitPolicy:
        base = self._config.default
        override = self._config.agents.get(agent)
        if override is None:
            return base

        return RateLimitPolicy(
            requests_per_minute=(
                override.requests_per_minute
                if override.requests_per_minute is not None
                else base.requests_per_minute
            ),
            requests_per_hour=(
                override.requests_per_hour
                if override.requests_per_hour is not None
                else base.requests_per_hour
            ),
            requests_per_day=(
                override.requests_per_day
                if override.requests_per_day is not None
                else base.requests_per_day
            ),
            tokens_per_minute=(
                override.tokens_per_minute
                if override.tokens_per_minute is not None
                else base.tokens_per_minute
            ),
            tokens_per_hour=(
                override.tokens_per_hour
                if override.tokens_per_hour is not None
                else base.tokens_per_hour
            ),
            tokens_per_day=(
                override.tokens_per_day
                if override.tokens_per_day is not None
                else base.tokens_per_day
            ),
            cost_per_minute=(
                override.cost_per_minute
                if override.cost_per_minute is not None
                else base.cost_per_minute
            ),
            cost_per_hour=(
                override.cost_per_hour if override.cost_per_hour is not None else base.cost_per_hour
            ),
            cost_per_day=(
                override.cost_per_day if override.cost_per_day is not None else base.cost_per_day
            ),
        )

    def _first_exceeded_limit(
        self,
        *,
        api_key_id: str,
        agent: str,
        policy: RateLimitPolicy,
        dimension: DimensionName,
        increment: float,
        now: float,
    ) -> RateLimitDecision | None:
        for window_name, window_seconds, limit in self._iter_limits(
            policy=policy, dimension=dimension
        ):
            key = self._counter_key(
                api_key_id=api_key_id,
                agent=agent,
                dimension=dimension,
                window_seconds=window_seconds,
                now=now,
            )
            used = self._usage.get(key, 0.0)
            projected = used + increment
            exceeded = projected > limit + 1e-9
            if increment == 0.0:
                exceeded = used >= limit - 1e-9
            if exceeded:
                reset_at = key.bucket_start + window_seconds
                retry_after_seconds = max(1, int(math.ceil(reset_at - now)))
                return RateLimitDecision(
                    allowed=False,
                    dimension=dimension,
                    window=window_name,
                    limit=limit,
                    used=used,
                    remaining=max(0.0, limit - used),
                    reset_at=reset_at,
                    retry_after_seconds=retry_after_seconds,
                    detail=f"Rate limit exceeded for {dimension} per {window_name}",
                )
        return None

    def _build_primary_request_decision(
        self,
        *,
        api_key_id: str,
        agent: str,
        policy: RateLimitPolicy,
        now: float,
    ) -> RateLimitDecision | None:
        best: RateLimitDecision | None = None
        best_score = float("inf")

        for window_name, window_seconds, limit in self._iter_limits(
            policy=policy,
            dimension="requests",
        ):
            key = self._counter_key(
                api_key_id=api_key_id,
                agent=agent,
                dimension="requests",
                window_seconds=window_seconds,
                now=now,
            )
            used = self._usage.get(key, 0.0)
            remaining = max(0.0, limit - used)
            score = remaining / limit if limit > 0 else 0.0

            decision = RateLimitDecision(
                allowed=True,
                dimension="requests",
                window=window_name,
                limit=limit,
                used=used,
                remaining=remaining,
                reset_at=key.bucket_start + window_seconds,
                retry_after_seconds=0,
                detail="Rate limit check passed",
            )
            if score < best_score:
                best = decision
                best_score = score

        return best

    def _increment_dimension(
        self,
        *,
        api_key_id: str,
        agent: str,
        policy: RateLimitPolicy,
        dimension: DimensionName,
        amount: float,
        now: float,
    ) -> None:
        for _window_name, window_seconds, _limit in self._iter_limits(
            policy=policy, dimension=dimension
        ):
            key = self._counter_key(
                api_key_id=api_key_id,
                agent=agent,
                dimension=dimension,
                window_seconds=window_seconds,
                now=now,
            )
            self._usage[key] = self._usage.get(key, 0.0) + amount

    @staticmethod
    def _iter_limits(
        *,
        policy: RateLimitPolicy,
        dimension: DimensionName,
    ) -> list[tuple[WindowName, int, float]]:
        raw_limits: list[tuple[WindowName, int | float | None]]
        if dimension == "requests":
            raw_limits = [
                ("minute", policy.requests_per_minute),
                ("hour", policy.requests_per_hour),
                ("day", policy.requests_per_day),
            ]
        elif dimension == "tokens":
            raw_limits = [
                ("minute", policy.tokens_per_minute),
                ("hour", policy.tokens_per_hour),
                ("day", policy.tokens_per_day),
            ]
        else:
            raw_limits = [
                ("minute", policy.cost_per_minute),
                ("hour", policy.cost_per_hour),
                ("day", policy.cost_per_day),
            ]

        limits: list[tuple[WindowName, int, float]] = []
        for window_name, limit in raw_limits:
            if limit is None:
                continue
            limits.append((window_name, WINDOW_SECONDS[window_name], float(limit)))
        return limits

    @staticmethod
    def _counter_key(
        *,
        api_key_id: str,
        agent: str,
        dimension: DimensionName,
        window_seconds: int,
        now: float,
    ) -> CounterKey:
        bucket_start = int(now // window_seconds) * window_seconds
        return CounterKey(
            api_key_id=api_key_id,
            agent=agent,
            dimension=dimension,
            window_seconds=window_seconds,
            bucket_start=bucket_start,
        )

    def _cleanup_if_needed(self, *, now: float) -> None:
        now_monotonic = time.monotonic()
        if now_monotonic - self._last_cleanup_monotonic < self._config.cleanup_interval_seconds:
            return

        cutoff = int(now) - self._max_window_seconds
        stale_keys = [key for key in self._usage if key.bucket_start + key.window_seconds < cutoff]
        for key in stale_keys:
            self._usage.pop(key, None)

        self._last_cleanup_monotonic = now_monotonic


def _format_limit_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")
