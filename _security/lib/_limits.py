"""Declarative request limits enforced by the REST + MCP layers.

Why ship these as a separate module: the caps need to be reusable
across vstack-api (HTTP request body validation), vstack-mcp (tool
input validation), and the framework adapters' run_pattern_dispatch
(programmatic input validation). One source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterator, Mapping


class RequestSizeExceeded(ValueError):
    """Raised when an incoming trace exceeds the configured limit.

    Carries the actual + limit values so the caller can surface a
    structured error envelope back to the user instead of a generic
    400.
    """

    def __init__(self, kind: str, actual: int, limit: int) -> None:
        super().__init__(
            f"{kind} exceeded: {actual} > {limit}. "
            f"Increase {_env_var_for(kind)} or split the trace."
        )
        self.kind = kind
        self.actual = actual
        self.limit = limit


@dataclass(frozen=True)
class RequestLimits:
    """Maximum sizes the API layer accepts.

    Defaults are chosen for "production-safe" — large enough that
    typical agent traces fit comfortably, small enough that a
    malicious client can't trivially OOM the server with one POST.
    """

    max_body_bytes: int = 5 * 1024 * 1024  # 5 MiB
    """Total POST body size in bytes. FastAPI middleware enforces."""

    max_trace_steps: int = 5_000
    """Cap on len(trace['steps']) / len(messages) / len(observations)
    across patterns. 5k steps is a very long agent run; saner users
    are typically < 100."""

    max_messages: int = 5_000
    """Cap on multi-agent message logs."""

    max_string_chars: int = 200_000
    """Per-string char cap on any free-text field. Mirrors the per-
    pattern ``max_trace_chars`` default."""

    max_total_chars: int = 1_000_000
    """Total free-text char count across the whole trace."""

    request_timeout_seconds: float = 120.0
    """Server-side per-request deadline. Forensic mode of some
    patterns can exceed this; the API surfaces a structured timeout
    error and the caller can retry in standard mode."""


DEFAULT_REQUEST_LIMITS = RequestLimits()


def request_limits_from_env(
    env: Mapping[str, str] | None = None,
    base: RequestLimits | None = None,
) -> RequestLimits:
    """Load limits from env vars, layering over ``base``.

    Env vars consulted:
      * ``VSTACK_API_MAX_BODY_BYTES``
      * ``VSTACK_API_MAX_TRACE_STEPS``
      * ``VSTACK_API_MAX_MESSAGES``
      * ``VSTACK_API_MAX_STRING_CHARS``
      * ``VSTACK_API_MAX_TOTAL_CHARS``
      * ``VSTACK_API_REQUEST_TIMEOUT``
    """
    env = env if env is not None else os.environ
    base = base or DEFAULT_REQUEST_LIMITS
    return RequestLimits(
        max_body_bytes=_int_env(env, "VSTACK_API_MAX_BODY_BYTES", base.max_body_bytes),
        max_trace_steps=_int_env(env, "VSTACK_API_MAX_TRACE_STEPS", base.max_trace_steps),
        max_messages=_int_env(env, "VSTACK_API_MAX_MESSAGES", base.max_messages),
        max_string_chars=_int_env(env, "VSTACK_API_MAX_STRING_CHARS", base.max_string_chars),
        max_total_chars=_int_env(env, "VSTACK_API_MAX_TOTAL_CHARS", base.max_total_chars),
        request_timeout_seconds=_float_env(
            env, "VSTACK_API_REQUEST_TIMEOUT", base.request_timeout_seconds
        ),
    )


def enforce_trace_limits(payload: Mapping[str, Any], limits: RequestLimits) -> None:
    """Walk a trace payload and raise on any cap violation.

    Called from the REST + framework-adapter dispatch path BEFORE the
    payload reaches Pydantic. Pydantic itself catches schema errors;
    this layer catches the size-based abuse the schema can't.
    """
    if not isinstance(payload, dict):
        return

    steps = payload.get("steps")
    if isinstance(steps, list) and len(steps) > limits.max_trace_steps:
        raise RequestSizeExceeded("trace_steps", len(steps), limits.max_trace_steps)

    messages = payload.get("messages")
    if isinstance(messages, list) and len(messages) > limits.max_messages:
        raise RequestSizeExceeded("messages", len(messages), limits.max_messages)

    total_chars = 0
    for value in _walk_strings(payload):
        if len(value) > limits.max_string_chars:
            raise RequestSizeExceeded("string_chars", len(value), limits.max_string_chars)
        total_chars += len(value)
        if total_chars > limits.max_total_chars:
            raise RequestSizeExceeded("total_chars", total_chars, limits.max_total_chars)


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _walk_strings(obj: Any) -> "Iterator[str]":
    if isinstance(obj, str):
        yield obj
        return
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)
        return


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return max(0.1, float(raw))
    except ValueError:
        return default


def _env_var_for(kind: str) -> str:
    return {
        "trace_steps": "VSTACK_API_MAX_TRACE_STEPS",
        "messages": "VSTACK_API_MAX_MESSAGES",
        "string_chars": "VSTACK_API_MAX_STRING_CHARS",
        "total_chars": "VSTACK_API_MAX_TOTAL_CHARS",
    }.get(kind, "VSTACK_API_*")
