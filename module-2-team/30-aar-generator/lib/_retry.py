"""
Retry helpers for LLM calls.

LLM calls fail for many reasons: rate limits, transient network errors,
provider-side incidents, timeouts. The retry decorator below distinguishes
retryable from non-retryable failures and applies exponential backoff.

It is intentionally small and dependency-free. For richer retry policies
(circuit breakers, deadline-aware retries, etc.) users can wrap their
own client.
"""

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

log = logging.getLogger("agentcity.aar.retry")

T = TypeVar("T")

# Errors we treat as retryable. We match by class-name substring so we don't
# need to import every LLM SDK at module load time.
_RETRYABLE_NAME_SUBSTRINGS: tuple[str, ...] = (
    "RateLimit",
    "Timeout",
    "Connection",
    "ServiceUnavailable",
    "InternalServer",
    "APIStatusError",
    "APIError",
    "APIConnectionError",
    "OverloadedError",
    "ReadTimeout",
)

# Errors we treat as fatal and never retry. Matching here wins over
# retryable matching.
_FATAL_NAME_SUBSTRINGS: tuple[str, ...] = (
    "Authentication",
    "PermissionDenied",
    "InvalidRequest",
    "BadRequest",
    "NotFound",
    "Unauthorized",
)


def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    if any(fatal in name for fatal in _FATAL_NAME_SUBSTRINGS):
        return False
    if any(retryable in name for retryable in _RETRYABLE_NAME_SUBSTRINGS):
        return True
    # Generic network exceptions
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    return False


def with_retry(
    fn: Callable[..., T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.25,
) -> Callable[..., T]:
    """Decorator: retry `fn` on retryable errors with exponential backoff.

    Total attempt count is `max_attempts` (so max_attempts=3 = original
    call plus 2 retries). Delay doubles each attempt up to `max_delay`,
    plus a small jitter to avoid thundering-herd retries.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        last_exc: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except BaseException as exc:
                last_exc = exc
                if attempt >= max_attempts or not _is_retryable(exc):
                    log.error(
                        "LLM call failed (%s) on attempt %d/%d, not retrying",
                        type(exc).__name__,
                        attempt,
                        max_attempts,
                    )
                    raise
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                delay += random.uniform(0, delay * jitter)
                log.warning(
                    "LLM call failed (%s) on attempt %d/%d, retrying in %.2fs",
                    type(exc).__name__,
                    attempt,
                    max_attempts,
                    delay,
                )
                time.sleep(delay)
        # Unreachable, but mypy needs it.
        assert last_exc is not None
        raise last_exc

    return wrapper
