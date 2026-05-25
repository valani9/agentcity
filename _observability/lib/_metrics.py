"""Lightweight Prometheus-text-format metrics collector.

Why we hand-roll this: the upstream ``prometheus_client`` package
pulls in a lot of optional dependencies (gRPC, multiprocess mode)
that vstack's typical user doesn't need. The Prometheus text
exposition format is tightly specified and easy to emit; we expose
the same Counter / Histogram API the upstream package does for the
parts we use.

The registry is process-global by default. Tests pass an explicit
:class:`MetricsRegistry` to avoid leaking counters between cases.
"""

from __future__ import annotations

import contextlib
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Mapping


# Histogram buckets in seconds. Default chosen for LLM-pattern
# latency: quick mode ~1-3s, standard ~3-8s, forensic ~8-30s.
DEFAULT_HISTOGRAM_BUCKETS: tuple[float, ...] = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    float("inf"),
)


@dataclass
class Counter:
    """Monotonically-increasing counter with optional labels."""

    name: str
    description: str
    label_names: tuple[str, ...] = ()
    _values: dict[tuple[str, ...], float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, value: float = 1.0, **labels: str) -> None:
        key = self._key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + value

    def value(self, **labels: str) -> float:
        with self._lock:
            return self._values.get(self._key(labels), 0.0)

    def _key(self, labels: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.label_names)


@dataclass
class Histogram:
    """Histogram with cumulative bucket counts + sum."""

    name: str
    description: str
    label_names: tuple[str, ...] = ()
    buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS
    _counts: dict[tuple[str, ...], list[int]] = field(default_factory=dict)
    _sums: dict[tuple[str, ...], float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float, **labels: str) -> None:
        if math.isnan(value) or math.isinf(value):
            return
        key = self._key(labels)
        with self._lock:
            counts = self._counts.setdefault(key, [0] * len(self.buckets))
            self._sums[key] = self._sums.get(key, 0.0) + value
            for i, edge in enumerate(self.buckets):
                if value <= edge:
                    counts[i] += 1

    def _key(self, labels: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(str(labels.get(n, "")) for n in self.label_names)


@dataclass
class MetricsRegistry:
    """A collection of Counters + Histograms with a Prometheus exporter."""

    counters: dict[str, Counter] = field(default_factory=dict)
    histograms: dict[str, Histogram] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def counter(self, name: str, description: str, label_names: Iterable[str] = ()) -> Counter:
        with self._lock:
            existing = self.counters.get(name)
            if existing is not None:
                return existing
            counter = Counter(name=name, description=description, label_names=tuple(label_names))
            self.counters[name] = counter
            return counter

    def histogram(
        self,
        name: str,
        description: str,
        label_names: Iterable[str] = (),
        buckets: Iterable[float] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> Histogram:
        with self._lock:
            existing = self.histograms.get(name)
            if existing is not None:
                return existing
            histogram = Histogram(
                name=name,
                description=description,
                label_names=tuple(label_names),
                buckets=tuple(buckets),
            )
            self.histograms[name] = histogram
            return histogram

    def render_prometheus(self) -> str:
        """Return the registry as a Prometheus text-format string."""
        return render_prometheus(self)


DEFAULT_METRICS_REGISTRY = MetricsRegistry()
"""Process-wide default registry. The REST API + MCP server use this
unless a test or downstream caller injects their own."""


# ----------------------------------------------------------------------
# request helpers
# ----------------------------------------------------------------------


def _request_counter(registry: MetricsRegistry) -> Counter:
    return registry.counter(
        "vstack_requests_total",
        "Total vstack analyzer requests, labeled by surface / pattern / mode / status.",
        label_names=("surface", "pattern", "mode", "status"),
    )


def _request_histogram(registry: MetricsRegistry) -> Histogram:
    return registry.histogram(
        "vstack_request_duration_seconds",
        "Analyzer-request latency in seconds, labeled by surface / pattern / mode.",
        label_names=("surface", "pattern", "mode"),
    )


def record_request(
    *,
    surface: str,
    pattern: str,
    mode: str,
    status: str,
    duration_seconds: float,
    registry: MetricsRegistry | None = None,
) -> None:
    """Capture one request + duration to the metrics registry.

    ``status`` is a low-cardinality string: ``"ok"`` /
    ``"validation_error"`` / ``"invalid_mode"`` /
    ``"analyzer_error"`` / ``"llm_resolution_error"`` /
    ``"rate_limited"`` / ``"unauthorized"`` / etc.
    """
    registry = registry or DEFAULT_METRICS_REGISTRY
    _request_counter(registry).inc(surface=surface, pattern=pattern, mode=mode, status=status)
    _request_histogram(registry).observe(
        duration_seconds, surface=surface, pattern=pattern, mode=mode
    )


@contextlib.contextmanager
def time_request(
    *,
    surface: str,
    pattern: str,
    mode: str,
    registry: MetricsRegistry | None = None,
) -> Iterator[dict[str, str]]:
    """Context manager: time the block + record on exit.

    Usage::

        with time_request(surface="rest", pattern="lewin", mode="standard") as out:
            try:
                detection = analyzer.run(trace)
                out["status"] = "ok"
            except ValidationError:
                out["status"] = "validation_error"
                raise
    """
    started = time.perf_counter()
    bucket: dict[str, str] = {"status": "unknown"}
    try:
        yield bucket
    finally:
        elapsed = time.perf_counter() - started
        record_request(
            surface=surface,
            pattern=pattern,
            mode=mode,
            status=bucket.get("status", "unknown"),
            duration_seconds=elapsed,
            registry=registry,
        )


# ----------------------------------------------------------------------
# Prometheus exporter
# ----------------------------------------------------------------------


def render_prometheus(registry: MetricsRegistry) -> str:
    """Render the registry to Prometheus text exposition format."""
    lines: list[str] = []
    for counter in registry.counters.values():
        lines.append(f"# HELP {counter.name} {counter.description}")
        lines.append(f"# TYPE {counter.name} counter")
        if not counter.label_names:
            lines.append(f"{counter.name} {counter.value()}")
            continue
        with counter._lock:
            for label_values, value in counter._values.items():
                label_str = _format_labels(counter.label_names, label_values)
                lines.append(f"{counter.name}{label_str} {value}")
    for histogram in registry.histograms.values():
        lines.append(f"# HELP {histogram.name} {histogram.description}")
        lines.append(f"# TYPE {histogram.name} histogram")
        with histogram._lock:
            for label_values, counts in histogram._counts.items():
                cumulative = 0
                for i, edge in enumerate(histogram.buckets):
                    cumulative += counts[i] - (counts[i - 1] if i > 0 else 0)
                    # Actually counts[] in observe() above only
                    # increments once per bucket where value<=edge;
                    # to get cumulative we just accumulate counts.
                    pass
                # Re-do cumulative properly: counts[i] holds total
                # observations <= buckets[i] because observe() above
                # increments every bucket where value<=edge.
                for i, edge in enumerate(histogram.buckets):
                    le = "+Inf" if edge == float("inf") else _format_float(edge)
                    bucket_labels = _format_labels(
                        histogram.label_names + ("le",),
                        label_values + (le,),
                    )
                    lines.append(f"{histogram.name}_bucket{bucket_labels} {counts[i]}")
                count_labels = _format_labels(histogram.label_names, label_values)
                total_count = counts[-1] if counts else 0
                total_sum = histogram._sums.get(label_values, 0.0)
                lines.append(f"{histogram.name}_count{count_labels} {total_count}")
                lines.append(f"{histogram.name}_sum{count_labels} {total_sum}")
    return "\n".join(lines) + ("\n" if lines else "")


def _format_labels(names: tuple[str, ...], values: tuple[str, ...]) -> str:
    if not names:
        return ""
    pairs = []
    for n, v in zip(names, values):
        v = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        pairs.append(f'{n}="{v}"')
    return "{" + ",".join(pairs) + "}"


def _format_float(v: float) -> str:
    if v == int(v):
        return f"{int(v)}"
    return f"{v}"
