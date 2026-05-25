"""Tests for ``vstack.observability``."""

from __future__ import annotations

import threading
import time

import pytest

import vstack.observability as obs
from vstack.observability._metrics import (
    Counter,
    Histogram,
    MetricsRegistry,
    record_request,
    render_prometheus,
    time_request,
)
from vstack.observability._request_id import (
    REQUEST_ID_HEADER,
    current_request_id,
    get_or_create_request_id,
    reset_request_id,
    set_current_request_id,
)
from vstack.observability._sentry import (
    _redact_dsn,
    install_sentry_if_configured,
    is_sentry_active,
)


# ----------------------------------------------------------------------
# Counter
# ----------------------------------------------------------------------


def test_counter_inc_no_labels() -> None:
    c = Counter(name="x", description="d")
    c.inc()
    c.inc(2.5)
    assert c.value() == 3.5


def test_counter_inc_with_labels() -> None:
    c = Counter(name="x", description="d", label_names=("status",))
    c.inc(status="ok")
    c.inc(status="ok")
    c.inc(status="err")
    assert c.value(status="ok") == 2
    assert c.value(status="err") == 1
    assert c.value(status="missing") == 0


def test_counter_thread_safety() -> None:
    c = Counter(name="x", description="d")

    def worker():
        for _ in range(1000):
            c.inc()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.value() == 8000


# ----------------------------------------------------------------------
# Histogram
# ----------------------------------------------------------------------


def test_histogram_observe_buckets() -> None:
    h = Histogram(name="x", description="d", buckets=(0.1, 0.5, 1.0, float("inf")))
    h.observe(0.05)
    h.observe(0.3)
    h.observe(2.0)
    # Bucket layout under our observe()'s semantics: each observation
    # increments every bucket where value <= edge.
    assert h._counts[()][0] == 1  # 0.05 <= 0.1
    assert h._counts[()][1] == 2  # 0.05 + 0.3 <= 0.5
    assert h._counts[()][2] == 2  # same
    assert h._counts[()][3] == 3  # all <= +Inf
    assert h._sums[()] == pytest.approx(0.05 + 0.3 + 2.0)


def test_histogram_ignores_nan_and_inf() -> None:
    h = Histogram(name="x", description="d")
    h.observe(float("nan"))
    h.observe(float("inf"))
    assert () not in h._counts  # nothing recorded


def test_histogram_with_labels() -> None:
    h = Histogram(name="x", description="d", label_names=("pattern",), buckets=(1.0, float("inf")))
    h.observe(0.5, pattern="lewin")
    h.observe(0.5, pattern="aar")
    assert h._counts[("lewin",)][0] == 1
    assert h._counts[("aar",)][0] == 1


# ----------------------------------------------------------------------
# MetricsRegistry
# ----------------------------------------------------------------------


def test_registry_get_or_create_idempotent() -> None:
    reg = MetricsRegistry()
    c1 = reg.counter("x", "d")
    c2 = reg.counter("x", "d")
    assert c1 is c2


def test_registry_render_prometheus_includes_counter_and_histogram() -> None:
    reg = MetricsRegistry()
    c = reg.counter("vstack_test_total", "demo counter", label_names=("status",))
    c.inc(status="ok")
    c.inc(status="ok")
    h = reg.histogram(
        "vstack_test_duration_seconds",
        "demo histogram",
        label_names=("pattern",),
        buckets=(0.5, 1.0, float("inf")),
    )
    h.observe(0.2, pattern="lewin")
    text = render_prometheus(reg)
    assert "# HELP vstack_test_total" in text
    assert "# TYPE vstack_test_total counter" in text
    assert 'vstack_test_total{status="ok"} 2' in text
    assert "# TYPE vstack_test_duration_seconds histogram" in text
    assert 'vstack_test_duration_seconds_bucket{pattern="lewin",le="0.5"}' in text
    assert 'vstack_test_duration_seconds_bucket{pattern="lewin",le="+Inf"}' in text
    assert 'vstack_test_duration_seconds_count{pattern="lewin"}' in text
    assert 'vstack_test_duration_seconds_sum{pattern="lewin"}' in text


# ----------------------------------------------------------------------
# record_request + time_request
# ----------------------------------------------------------------------


def test_record_request_populates_default_metrics() -> None:
    reg = MetricsRegistry()
    record_request(
        surface="rest",
        pattern="lewin",
        mode="standard",
        status="ok",
        duration_seconds=1.5,
        registry=reg,
    )
    text = render_prometheus(reg)
    assert "vstack_requests_total" in text
    assert "vstack_request_duration_seconds" in text


def test_time_request_captures_duration_on_exit() -> None:
    reg = MetricsRegistry()
    with time_request(surface="rest", pattern="aar", mode="quick", registry=reg) as bucket:
        bucket["status"] = "ok"
        time.sleep(0.01)
    text = render_prometheus(reg)
    assert 'vstack_requests_total{surface="rest",pattern="aar",mode="quick",status="ok"}' in text


def test_time_request_records_unknown_on_unset_status() -> None:
    reg = MetricsRegistry()
    with time_request(surface="rest", pattern="aar", mode="quick", registry=reg):
        pass
    text = render_prometheus(reg)
    assert 'status="unknown"' in text


def test_time_request_records_on_exception() -> None:
    reg = MetricsRegistry()
    with pytest.raises(RuntimeError):
        with time_request(surface="rest", pattern="aar", mode="quick", registry=reg) as bucket:
            bucket["status"] = "analyzer_error"
            raise RuntimeError("boom")
    text = render_prometheus(reg)
    assert 'status="analyzer_error"' in text


# ----------------------------------------------------------------------
# Request ID
# ----------------------------------------------------------------------


def test_get_or_create_request_id_uses_valid_inbound() -> None:
    incoming = "abc-123_42:xyz.42"
    assert get_or_create_request_id(incoming) == incoming


def test_get_or_create_request_id_replaces_invalid() -> None:
    bad = "not allowed!!! < script>"
    assert get_or_create_request_id(bad) != bad
    assert get_or_create_request_id(bad).startswith("req_")


def test_get_or_create_request_id_replaces_too_long() -> None:
    too_long = "a" * 1000
    assert get_or_create_request_id(too_long).startswith("req_")


def test_get_or_create_request_id_generates_when_none() -> None:
    rid = get_or_create_request_id(None)
    assert rid.startswith("req_")
    assert len(rid) > 10


def test_set_and_current_request_id() -> None:
    token = set_current_request_id("req_test_42")
    try:
        assert current_request_id() == "req_test_42"
    finally:
        reset_request_id(token)
    assert current_request_id() is None


def test_request_id_header_constant() -> None:
    assert REQUEST_ID_HEADER == "X-Request-ID"


# ----------------------------------------------------------------------
# Sentry hook
# ----------------------------------------------------------------------


def test_install_sentry_noop_when_dsn_unset() -> None:
    assert install_sentry_if_configured({}) is False
    assert is_sentry_active() is False


def test_install_sentry_noop_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure sentry_sdk import fails in this run by shadowing it.
    import sys

    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert install_sentry_if_configured({"SENTRY_DSN": "https://example/123"}) is False


def test_redact_dsn_hides_auth() -> None:
    redacted = _redact_dsn("https://abc123@o123.ingest.sentry.io/456")
    assert "abc123" not in redacted
    assert "***" in redacted


def test_redact_dsn_unparseable() -> None:
    assert _redact_dsn("not a dsn") == "<dsn>"


# ----------------------------------------------------------------------
# Module exports
# ----------------------------------------------------------------------


def test_module_exports() -> None:
    for name in (
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
        "set_current_request_id",
        "time_request",
    ):
        assert name in obs.__all__
    assert obs.__version__
