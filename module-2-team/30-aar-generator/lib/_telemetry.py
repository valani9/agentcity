"""Optional token / cost telemetry for AgentCity diagnostic runs.

LLM-driven diagnostics cost money. In production deployments you want
to know which patterns are expensive, which agent flows trigger the
most pattern runs, and where unexpected token spikes come from.

This module provides a tiny, dependency-free telemetry surface that is
**off by default**. When enabled, every LLM call routed through an
adapter that recorded ``last_usage`` is reported to a sink the caller
supplies.

Design notes
------------
- The library does not ship a "default sink." Telemetry providers
  (Datadog, Honeycomb, internal Prometheus, OpenTelemetry) have wildly
  different shapes; we deliberately don't pick one.
- The :class:`TelemetrySink` protocol is one method: ``record(event)``.
  Adapters can buffer, batch, async-flush, or drop events as they see
  fit — the library only emits.
- :class:`InMemoryTelemetrySink` is the testing default. It captures
  every event for assertions.
- Pattern generators emit events by calling :func:`record_llm_call`
  after each successful LLM completion. The wiring is one line of code
  per generator — patterns that don't adopt still work fine, they just
  don't produce telemetry.

Example::

    from agentcity.aar._telemetry import (
        InMemoryTelemetrySink,
        set_default_sink,
        record_llm_call,
    )

    sink = InMemoryTelemetrySink()
    set_default_sink(sink)

    # ... run diagnostics ...

    for event in sink.events:
        print(event.pattern, event.tokens, event.elapsed_ms)
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from ._logging import current_pattern, current_run_id

log = logging.getLogger("agentcity.aar.telemetry")


@dataclass
class TelemetryEvent:
    """One observed LLM call (or diagnostic run-level event)."""

    event_type: str
    pattern: str | None = None
    run_id: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class TelemetrySink(Protocol):
    """A telemetry sink receives :class:`TelemetryEvent` records.

    Implementations can buffer, batch, async-flush, drop on overflow,
    or forward to external systems. The library never assumes anything
    about delivery semantics.
    """

    def record(self, event: TelemetryEvent) -> None: ...


class InMemoryTelemetrySink:
    """Default testing sink — captures every event for assertions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[TelemetryEvent] = []

    def record(self, event: TelemetryEvent) -> None:
        with self._lock:
            self.events.append(event)

    def clear(self) -> None:
        with self._lock:
            self.events.clear()


class NullTelemetrySink:
    """Drop everything. The default when telemetry is disabled."""

    def record(self, event: TelemetryEvent) -> None:
        return None


_default_sink: TelemetrySink = NullTelemetrySink()


def set_default_sink(sink: TelemetrySink | None) -> None:
    """Install a process-wide telemetry sink.

    ``None`` restores the null sink (telemetry disabled).
    """
    global _default_sink
    _default_sink = sink if sink is not None else NullTelemetrySink()


def get_default_sink() -> TelemetrySink:
    return _default_sink


def record_llm_call(
    *,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    elapsed_ms: float = 0.0,
    pattern: str | None = None,
    run_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a telemetry event for a completed LLM call.

    Pattern / run_id are auto-populated from the current logging
    context (set by :func:`agentcity.aar._logging.run_context`) when
    not explicitly passed.
    """
    event = TelemetryEvent(
        event_type="llm_call",
        pattern=pattern if pattern is not None else current_pattern(),
        run_id=run_id if run_id is not None else current_run_id(),
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens or (input_tokens + output_tokens),
        elapsed_ms=elapsed_ms,
        extra=extra or {},
    )
    try:
        _default_sink.record(event)
    except Exception as exc:  # pragma: no cover — telemetry must never break the run
        log.warning(
            "Telemetry sink raised %s; dropping event. Sink: %s",
            type(exc).__name__,
            type(_default_sink).__name__,
        )


@contextmanager
def time_call() -> Iterator[dict[str, float]]:
    """Helper: measure elapsed_ms around an LLM call.

    Usage::

        with time_call() as t:
            text = self.llm.complete(prompt, system=sys)
        record_llm_call(model=..., elapsed_ms=t["elapsed_ms"], ...)
    """
    start = time.monotonic()
    handle: dict[str, float] = {"elapsed_ms": 0.0}
    try:
        yield handle
    finally:
        handle["elapsed_ms"] = (time.monotonic() - start) * 1000.0


__all__ = [
    "InMemoryTelemetrySink",
    "NullTelemetrySink",
    "TelemetryEvent",
    "TelemetrySink",
    "get_default_sink",
    "record_llm_call",
    "set_default_sink",
    "time_call",
]
