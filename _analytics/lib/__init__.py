"""vstack.analytics -- aggregate the ``record_llm_call`` telemetry
events emitted by every vstack pattern.

Provides:

* :class:`FileTelemetrySink` -- a :class:`vstack.aar.TelemetrySink`
  that appends one JSONL line per LLM call to
  ``~/.vstack/analytics/telemetry.jsonl``. Activate it once at
  startup with :func:`enable_file_telemetry`; the existing
  ``record_llm_call`` calls in every pattern then flow into the
  file automatically.

* :class:`TelemetryAggregator` -- streaming aggregator over the JSONL
  log. Returns per-pattern, per-model, and per-day usage + cost
  totals.

* :class:`CostEstimator` -- maps model id to a $/1k tokens table and
  applies it to each call's token counts.

* ``vstack-analytics`` CLI -- ``summary`` / ``top-costs`` / ``cost``
  / ``raw`` / ``path``.
"""

from ._sink import FileTelemetrySink, enable_file_telemetry
from ._aggregate import (
    CostEstimator,
    PerDayRow,
    PerModelRow,
    PerPatternRow,
    TelemetryAggregator,
    default_aggregator,
)

__all__ = [
    "FileTelemetrySink",
    "enable_file_telemetry",
    "CostEstimator",
    "PerDayRow",
    "PerModelRow",
    "PerPatternRow",
    "TelemetryAggregator",
    "default_aggregator",
]

__version__ = "0.4.0"
