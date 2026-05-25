"""Sliding-window rate limiter for the REST surface.

In-memory by default (fine for a single-process FastAPI deployment).
The :class:`RateLimiter` protocol exists so a downstream user can
swap in a Redis-backed implementation without changing the call sites
in vstack.api.

The window is sliding: every check records the timestamp + decrements
an in-memory ring buffer per key. Time complexity per check is O(N)
where N is the configured ``max_requests`` (typically <= 1000), so
even at 10k req/s the per-check overhead is microseconds.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Protocol


@dataclass(frozen=True)
class RateLimitDecision:
    """One rate-limiter check result."""

    allowed: bool
    remaining: int
    """Approximate remaining quota in the current window after this
    request would be admitted. -1 if the limiter doesn't track."""

    retry_after_seconds: float
    """How long until at least one slot frees up. 0 if ``allowed`` is True."""

    limit: int
    """The configured ``max_requests`` for context."""


class RateLimitExceeded(RuntimeError):
    """Raised when a synchronous caller wants exceptions instead of
    decisions (the API layer uses the decision object directly)."""

    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__(f"rate limit exceeded; retry after {decision.retry_after_seconds:.2f}s")
        self.decision = decision


class RateLimiter(Protocol):
    """Pluggable backend interface."""

    def check(self, key: str) -> RateLimitDecision:
        """Record + check; return a decision."""
        ...

    def reset(self, key: str | None = None) -> None:
        """Drop state for ``key`` (or all keys if None). Tests use this."""
        ...


@dataclass
class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter.

    Default config: 100 requests / 60-second window. Override via
    ``max_requests`` / ``window_seconds``.

    Thread-safe under the typical request-per-thread shape; lock is
    only held during the deque mutation, not during the timestamp
    comparison loop.
    """

    max_requests: int = 100
    window_seconds: float = 60.0
    _buckets: dict[str, Deque[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _now: Callable[[], float] = field(default=time.monotonic)
    """Injection point for tests."""

    def check(self, key: str) -> RateLimitDecision:
        now = self._now()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket
            # Evict stale timestamps.
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                # Oldest timestamp in the window is when the quota
                # frees by one. Retry-after = (oldest + window) - now.
                retry_after = (bucket[0] + self.window_seconds) - now
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=max(retry_after, 0.0),
                    limit=self.max_requests,
                )
            bucket.append(now)
            return RateLimitDecision(
                allowed=True,
                remaining=self.max_requests - len(bucket),
                retry_after_seconds=0.0,
                limit=self.max_requests,
            )

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)
