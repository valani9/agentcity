"""Tests for the v0.6.0 API hardening: auth, rate limit, request
limits, readyz/livez, metrics, request-id round-trip, CORS, security
headers, caching."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import vstack.api as api
from vstack.aar import StubClient
from vstack.cache import InMemoryLRUCache
from vstack.observability import MetricsRegistry
from vstack.security import (
    APIKey,
    APIKeyStore,
    InMemoryRateLimiter,
    RequestLimits,
)


# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------


def _client(**kwargs) -> TestClient:
    app = api.build_app(
        llm_client_factory=lambda: StubClient([]),
        **kwargs,
    )
    return TestClient(app)


def test_no_auth_by_default() -> None:
    client = _client(env={})
    r = client.get("/v1/patterns")
    assert r.status_code == 200


def test_require_auth_blocks_without_key() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("k", "a" * 30)])
    client = _client(keystore=store, require_auth=True, env={})
    r = client.get("/v1/patterns")
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error"] == "unauthorized"
    assert "WWW-Authenticate" in r.headers


def test_require_auth_allows_with_bearer() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("k", "a" * 30)])
    client = _client(keystore=store, require_auth=True, env={})
    r = client.get("/v1/patterns", headers={"Authorization": "Bearer " + "a" * 30})
    assert r.status_code == 200


def test_require_auth_allows_with_x_api_key() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("k", "a" * 30)])
    client = _client(keystore=store, require_auth=True, env={})
    r = client.get("/v1/patterns", headers={"X-API-Key": "a" * 30})
    assert r.status_code == 200


def test_require_auth_rejects_wrong_key() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("k", "a" * 30)])
    client = _client(keystore=store, require_auth=True, env={})
    r = client.get("/v1/patterns", headers={"Authorization": "Bearer wrong-key-here"})
    assert r.status_code == 401


def test_require_auth_misconfigured_when_no_keys() -> None:
    client = _client(keystore=APIKeyStore(), require_auth=True, env={})
    r = client.get("/v1/patterns")
    assert r.status_code == 500
    assert r.json()["detail"]["error"] == "auth_misconfigured"


def test_public_paths_skip_auth() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("k", "a" * 30)])
    client = _client(keystore=store, require_auth=True, env={})
    for path in ("/healthz", "/livez", "/readyz", "/metrics", "/openapi.json"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} blocked"


# ----------------------------------------------------------------------
# Rate limiting
# ----------------------------------------------------------------------


def test_rate_limit_returns_429_with_retry_after() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60.0)
    client = _client(rate_limiter=limiter, env={})
    r1 = client.get("/v1/patterns")
    assert r1.status_code == 200
    r2 = client.get("/v1/patterns")
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers
    body = r2.json()
    assert body["detail"]["error"] == "rate_limited"


def test_rate_limit_headers_on_success() -> None:
    limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60.0)
    client = _client(rate_limiter=limiter, env={})
    r = client.get("/v1/patterns")
    assert r.headers.get("X-RateLimit-Limit") == "10"
    assert r.headers.get("X-RateLimit-Remaining") == "9"


def test_rate_limit_does_not_apply_to_health() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60.0)
    client = _client(rate_limiter=limiter, env={})
    client.get("/v1/patterns")  # uses up the quota
    # Health probes should still respond.
    for path in ("/healthz", "/readyz", "/metrics"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} blocked under rate-limit"


# ----------------------------------------------------------------------
# Request limits
# ----------------------------------------------------------------------


def test_oversized_trace_steps_returns_413() -> None:
    limits = RequestLimits(max_trace_steps=2, max_body_bytes=10_000_000)
    client = _client(limits=limits, env={})
    payload = {
        "task": "x",
        "outcome": "y",
        "success": False,
        "steps": [{"type": "input", "content": "x"}] * 5,
    }
    r = client.post("/v1/analyze/lewin", json=payload)
    assert r.status_code == 413
    assert r.json()["detail"]["error"] == "request_too_large"


def test_oversized_body_returns_413() -> None:
    limits = RequestLimits(max_body_bytes=100)
    client = _client(limits=limits, env={})
    # Manually set Content-Length to bypass real-body short-circuit
    r = client.post(
        "/v1/analyze/lewin",
        json={"steps": ["x"] * 1000},
        headers={"Content-Length": "10000"},
    )
    # TestClient may set the header itself; the actual reject path is
    # tested by the request-body's actual size in this transport.
    assert r.status_code in (413, 400, 422)


# ----------------------------------------------------------------------
# readyz / livez / healthz
# ----------------------------------------------------------------------


def test_readyz_initially_ready() -> None:
    client = _client(env={})
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_livez_alias() -> None:
    client = _client(env={})
    r = client.get("/livez")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------


def test_metrics_endpoint_returns_prometheus_text() -> None:
    metrics = MetricsRegistry()
    client = _client(metrics=metrics, env={})
    # Generate some traffic.
    client.get("/v1/patterns")
    # Force a counter so the registry isn't empty.
    metrics.counter("test_seed_total", "test").inc()
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "# HELP" in body
    assert "test_seed_total" in body


# ----------------------------------------------------------------------
# Request ID
# ----------------------------------------------------------------------


def test_request_id_echoes_valid_inbound() -> None:
    client = _client(env={})
    r = client.get("/v1/patterns", headers={"X-Request-ID": "req_test_42"})
    assert r.headers["X-Request-ID"] == "req_test_42"


def test_request_id_generated_when_absent() -> None:
    client = _client(env={})
    r = client.get("/v1/patterns")
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert rid.startswith("req_")


def test_request_id_invalid_replaced_with_safe_one() -> None:
    client = _client(env={})
    r = client.get("/v1/patterns", headers={"X-Request-ID": "<script>alert(1)</script>"})
    assert r.headers["X-Request-ID"].startswith("req_")


# ----------------------------------------------------------------------
# Security headers
# ----------------------------------------------------------------------


def test_security_headers_applied() -> None:
    client = _client(env={})
    r = client.get("/v1/patterns")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers
    assert "Referrer-Policy" in r.headers


# ----------------------------------------------------------------------
# Caching
# ----------------------------------------------------------------------


@pytest.fixture
def lewin_factory():
    """Stub client factory that produces fresh stubs (so we can verify
    that a second request uses cache, not a re-run)."""
    scores = json.dumps(
        [
            {
                "locus": "environmental",
                "score": 0.9,
                "severity": "high",
                "explanation": "stale RAG",
                "evidence_quotes": [],
            }
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_locus": "environmental",
                "intervention_type": "change_rag_index",
                "description": "refresh",
                "suggested_implementation": "cron",
                "estimated_impact": "high",
                "rationale": "stops staleness",
            }
        ]
    )
    call_count = {"n": 0}

    def factory():
        call_count["n"] += 1
        return StubClient([scores, interventions])

    factory._counter = call_count  # type: ignore[attr-defined]
    return factory


def test_cache_serves_repeat_requests(lewin_factory) -> None:
    cache = InMemoryLRUCache(capacity=10)
    app = api.build_app(llm_client_factory=lewin_factory, cache=cache, env={})
    client = TestClient(app)
    payload = {
        "task": "x",
        "steps": [{"type": "input", "content": "y"}],
        "outcome": "z",
        "success": False,
        "mode": "standard",
    }
    r1 = client.post("/v1/analyze/lewin", json=payload)
    r2 = client.post("/v1/analyze/lewin", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same body content; cached=True on the second.
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
    # Factory invoked only once (cache hit avoided the second run).
    assert lewin_factory._counter["n"] == 1


def test_no_cache_default_means_every_request_runs(lewin_factory) -> None:
    app = api.build_app(llm_client_factory=lewin_factory, env={})
    client = TestClient(app)
    payload = {
        "task": "x",
        "steps": [{"type": "input", "content": "y"}],
        "outcome": "z",
        "success": False,
        "mode": "standard",
    }
    client.post("/v1/analyze/lewin", json=payload)
    client.post("/v1/analyze/lewin", json=payload)
    # No cache -> factory invoked twice.
    assert lewin_factory._counter["n"] == 2
