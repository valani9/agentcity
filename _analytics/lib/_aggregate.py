"""Streaming aggregator over the telemetry JSONL log.

Three views: per-pattern, per-model, per-day. Each view returns
ordered rows with token totals + estimated cost. Cost estimation uses
:class:`CostEstimator`, which ships a baseline price table for the
major providers; users can override per-model rates via the
``vstack-config`` preference keys (or by passing a custom ``rates``
dict).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from vstack.memory import get_analytics_dir

from ._sink import DEFAULT_FILENAME


# Baseline $/1k token rates. Sticker prices as of 2025 spring; the
# exact numbers don't matter for relative comparisons. Override via
# CostEstimator(rates=...) for current pricing.
DEFAULT_RATES_PER_1K: dict[str, tuple[float, float]] = {
    # (input_per_1k, output_per_1k)
    "claude-opus-4-7": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.0008, 0.004),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-opus": (0.015, 0.075),
    "claude-3-haiku": (0.00025, 0.00125),
    "gpt-5": (0.005, 0.020),
    "gpt-4o": (0.005, 0.015),
    "gpt-4-turbo": (0.010, 0.030),
    "gpt-4o-mini": (0.00015, 0.0006),
    "o1-preview": (0.015, 0.060),
    "o1-mini": (0.003, 0.012),
    "llama3.1:8b": (0.0, 0.0),  # local
    "stub-model": (0.0, 0.0),
}


@dataclass(frozen=True)
class PerPatternRow:
    pattern: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_ms: float
    estimated_cost_usd: float


@dataclass(frozen=True)
class PerModelRow:
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_ms: float
    estimated_cost_usd: float


@dataclass(frozen=True)
class PerDayRow:
    day: str  # YYYY-MM-DD
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_ms: float
    estimated_cost_usd: float


class CostEstimator:
    """Maps model id -> ($/1k input, $/1k output) and computes cost."""

    def __init__(self, rates: dict[str, tuple[float, float]] | None = None) -> None:
        self.rates: dict[str, tuple[float, float]] = dict(DEFAULT_RATES_PER_1K)
        if rates:
            self.rates.update(rates)

    def cost(self, model: str | None, input_tokens: int, output_tokens: int) -> float:
        if not model:
            return 0.0
        rate = self.rates.get(model)
        if rate is None:
            rate = self._best_effort_rate(model)
        in_rate, out_rate = rate
        return round(
            (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate,
            6,
        )

    def _best_effort_rate(self, model: str) -> tuple[float, float]:
        """When the model isn't in the table, try a prefix match."""
        lowered = model.lower()
        for key, rate in self.rates.items():
            if lowered.startswith(key.lower()):
                return rate
        return (0.0, 0.0)


class TelemetryAggregator:
    """Stream + roll up the JSONL telemetry log."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        estimator: CostEstimator | None = None,
    ) -> None:
        self.path = path or (get_analytics_dir() / DEFAULT_FILENAME)
        self.estimator = estimator or CostEstimator()

    def iter_events(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def per_pattern(self) -> list[PerPatternRow]:
        buckets = self._bucket(lambda e: e.get("pattern") or "unknown")
        return [PerPatternRow(pattern=key, **stats) for key, stats in sorted(buckets.items())]

    def per_model(self) -> list[PerModelRow]:
        buckets = self._bucket(lambda e: e.get("model") or "unknown")
        return [PerModelRow(model=key, **stats) for key, stats in sorted(buckets.items())]

    def per_day(self) -> list[PerDayRow]:
        def _day_of(event: dict[str, Any]) -> str:
            ts = event.get("timestamp")
            if not ts:
                return "unknown"
            try:
                return datetime.fromisoformat(ts).astimezone(timezone.utc).date().isoformat()
            except ValueError:
                return "unknown"

        buckets = self._bucket(_day_of)
        return [PerDayRow(day=key, **stats) for key, stats in sorted(buckets.items())]

    def top_costs(self, n: int = 10) -> list[dict[str, Any]]:
        """Return the top-N most expensive individual calls."""
        scored: list[tuple[float, dict[str, Any]]] = []
        for e in self.iter_events():
            cost = self.estimator.cost(
                e.get("model"),
                int(e.get("input_tokens") or 0),
                int(e.get("output_tokens") or 0),
            )
            scored.append((cost, e))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**event, "estimated_cost_usd": cost} for cost, event in scored[:n]]

    def total_cost(self) -> float:
        total = 0.0
        for e in self.iter_events():
            total += self.estimator.cost(
                e.get("model"),
                int(e.get("input_tokens") or 0),
                int(e.get("output_tokens") or 0),
            )
        return round(total, 4)

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _bucket(
        self,
        key_fn: Callable[[dict[str, Any]], str],
    ) -> dict[str, dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "elapsed_ms": 0.0,
                "estimated_cost_usd": 0.0,
            }
        )
        for e in self.iter_events():
            key = key_fn(e)
            slot = buckets[key]
            slot["calls"] += 1
            slot["input_tokens"] += int(e.get("input_tokens") or 0)
            slot["output_tokens"] += int(e.get("output_tokens") or 0)
            slot["total_tokens"] += int(e.get("total_tokens") or 0)
            slot["elapsed_ms"] += float(e.get("elapsed_ms") or 0.0)
            slot["estimated_cost_usd"] += self.estimator.cost(
                e.get("model"),
                int(e.get("input_tokens") or 0),
                int(e.get("output_tokens") or 0),
            )
        # Round costs for stable display.
        for s in buckets.values():
            s["estimated_cost_usd"] = round(s["estimated_cost_usd"], 6)
        return buckets


def default_aggregator() -> TelemetryAggregator:
    """An aggregator rooted at ``~/.vstack/analytics/telemetry.jsonl``."""
    return TelemetryAggregator()
