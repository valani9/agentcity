"""Tests for ``vstack.api`` -- routes, payload validation, stub-LLM
roundtrips, error cases."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import vstack.api as api
from vstack.aar import StubClient
from vstack.mcp._registry import PATTERNS


@pytest.fixture
def lewin_stub_factory():
    """Pre-canned standard-mode Lewin responses; reusable per-test."""

    def _make() -> StubClient:
        scores = json.dumps(
            [
                {
                    "locus": "internal",
                    "score": 0.15,
                    "severity": "low",
                    "explanation": "model behaved correctly",
                    "evidence_quotes": [],
                },
                {
                    "locus": "environmental",
                    "score": 0.85,
                    "severity": "high",
                    "explanation": "stale RAG index",
                    "evidence_quotes": ["returned a 2003 Wikipedia revision"],
                },
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_locus": "environmental",
                    "intervention_type": "change_rag_index",
                    "description": "refresh the RAG index nightly",
                    "suggested_implementation": "cron + dedup",
                    "estimated_impact": "high",
                    "rationale": "removes stale revisions",
                }
            ]
        )
        return StubClient([scores, interventions])

    return _make


@pytest.fixture
def client(lewin_stub_factory):
    app = api.build_app(llm_client_factory=lewin_stub_factory)
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["patterns"] == 34


def test_list_patterns(client: TestClient) -> None:
    r = client.get("/v1/patterns")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 34
    names = {p["name"] for p in body["patterns"]}
    assert names == {p.name for p in PATTERNS}
    # Spot check the first record's shape.
    first = body["patterns"][0]
    for k in (
        "name",
        "friendly",
        "group",
        "tool",
        "summary",
        "input_class",
        "output_class",
        "modes",
        "analyze_url",
        "resources",
    ):
        assert k in first


def test_get_pattern(client: TestClient) -> None:
    r = client.get("/v1/patterns/lewin")
    assert r.status_code == 200
    assert r.json()["tool"] == "vstack_lewin"


def test_get_unknown_pattern_returns_404(client: TestClient) -> None:
    r = client.get("/v1/patterns/does_not_exist")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "unknown_pattern"


def test_playbooks_endpoint(client: TestClient) -> None:
    r = client.get("/v1/patterns/lewin/playbooks")
    assert r.status_code == 200
    body = r.json()
    assert body["pattern"] == "lewin"
    assert body["count"] > 0


def test_composition_endpoint(client: TestClient) -> None:
    r = client.get("/v1/patterns/schein_culture/composition")
    assert r.status_code == 200
    body = r.json()
    assert body["pattern"] == "schein_culture"
    assert body["composition"] is not None


def test_citations_endpoint(client: TestClient) -> None:
    r = client.get("/v1/patterns/lewin/citations")
    assert r.status_code == 200
    assert "Lewin" in r.text or len(r.text) > 0


def test_analyze_lewin_envelope_shape(client: TestClient) -> None:
    payload = {
        "trace": {
            "task": "Answer 'When was Pluto reclassified?'",
            "steps": [
                {"type": "input", "content": "When was Pluto reclassified?"},
                {"type": "tool_call", "content": "rag.search(query='pluto')"},
                {"type": "observation", "content": "returned a 2003 Wikipedia revision"},
                {"type": "output", "content": "Pluto was reclassified in 2003."},
            ],
            "outcome": "Confidently wrong year (2006 is correct).",
            "success": False,
            "initial_attribution": "model is bad at facts",
        },
        "mode": "standard",
    }
    r = client.post("/v1/analyze/lewin", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pattern"] == "lewin"
    assert body["mode"] == "standard"
    assert body["detection"]["dominant_locus"] == "environmental"


def test_analyze_lewin_flat_shape(client: TestClient) -> None:
    """The endpoint also accepts the trace fields at the top level."""
    payload = {
        "task": "Answer 'When was Pluto reclassified?'",
        "steps": [
            {"type": "input", "content": "x"},
            {"type": "tool_call", "content": "rag.search"},
            {"type": "observation", "content": "2003 wiki snapshot"},
            {"type": "output", "content": "Pluto reclassified in 2003."},
        ],
        "outcome": "wrong year",
        "success": False,
        "initial_attribution": "model bad",
        "mode": "standard",
    }
    r = client.post("/v1/analyze/lewin", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["detection"]["dominant_locus"] == "environmental"


def test_analyze_invalid_mode_returns_400(client: TestClient) -> None:
    r = client.post(
        "/v1/analyze/lewin",
        json={
            "task": "t",
            "steps": [{"type": "input", "content": "x"}],
            "outcome": "o",
            "success": False,
            "mode": "BOGUS",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_mode"


def test_analyze_invalid_input_returns_400(client: TestClient) -> None:
    r = client.post("/v1/analyze/lewin", json={"task": "", "steps": []})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "validation_error"


def test_analyze_unknown_pattern_returns_404(client: TestClient) -> None:
    r = client.post("/v1/analyze/does_not_exist", json={})
    assert r.status_code == 404


def test_openapi_lists_all_pattern_endpoints(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec["paths"]
    # Spot check key endpoints exist.
    assert "/healthz" in paths
    assert "/v1/patterns" in paths
    assert "/v1/patterns/{name}" in paths
    assert "/v1/analyze/{name}" in paths


def test_llm_resolution_failure_returns_502(lewin_stub_factory) -> None:
    from vstack.mcp._client import LLMResolutionError

    def factory():
        raise LLMResolutionError("no key configured")

    app = api.build_app(llm_client_factory=factory)
    c = TestClient(app)
    r = c.post(
        "/v1/analyze/lewin",
        json={
            "task": "t",
            "steps": [{"type": "input", "content": "x"}],
            "outcome": "o",
            "success": False,
        },
    )
    assert r.status_code == 502
    assert r.json()["detail"]["error"] == "llm_resolution_error"
