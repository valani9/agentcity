"""vstack.observability -- Prometheus metrics + correlation IDs +
optional error reporting.

What this module provides:

* :class:`MetricsRegistry` -- a small in-process counter/histogram
  collector with a Prometheus text-format exporter. No upstream
  ``prometheus_client`` dependency required (the format is plain
  text + tightly specified).
* :func:`record_request` / :func:`time_request` -- helpers that
  the REST + MCP layers call to capture per-pattern latency +
  status histograms.
* :func:`get_or_create_request_id` -- generates a request ID per
  request, propagates it via the ``X-Request-ID`` header round-
  trip.
* :func:`install_sentry_if_configured` -- optional hook that
  initializes ``sentry-sdk`` when ``SENTRY_DSN`` is set. No-op
  when the SDK isn't installed.
"""

from ._metrics import (
    DEFAULT_METRICS_REGISTRY,
    Counter,
    Histogram,
    MetricsRegistry,
    record_request,
    render_prometheus,
    time_request,
)
from ._request_id import (
    REQUEST_ID_HEADER,
    current_request_id,
    get_or_create_request_id,
    reset_request_id,
    set_current_request_id,
)
from ._sentry import install_sentry_if_configured, is_sentry_active

__all__ = [
    "Counter",
    "Histogram",
    "MetricsRegistry",
    "DEFAULT_METRICS_REGISTRY",
    "REQUEST_ID_HEADER",
    "current_request_id",
    "get_or_create_request_id",
    "install_sentry_if_configured",
    "is_sentry_active",
    "record_request",
    "render_prometheus",
    "reset_request_id",
    "set_current_request_id",
    "time_request",
]

__version__ = "0.6.0"
