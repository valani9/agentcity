"""Tests for ``vstack.adapters``.

The pure-JSON adapters (OpenAI, Anthropic, AutoGen, Open WebUI) are
exercised against all 34 patterns. The framework-gated adapters
(LangChain, LangGraph, CrewAI, LlamaIndex, Pydantic AI) are skipped
when their framework isn't installed; the test still verifies that
the import-error path is actionable.
"""

from __future__ import annotations

import importlib
import json

import pytest

from vstack.adapters import (
    list_pattern_tool_specs,
    pattern_tool_spec_for,
    serialize_detection,
)
from vstack.adapters._base import (
    AdapterImportError,
    require_module,
    run_pattern_dispatch,
)
from vstack.adapters.autogen import (
    as_autogen_callables,
    as_autogen_function_manifest,
)
from vstack.adapters.openai import (
    as_anthropic_tool_schemas,
    as_openai_tool_schemas,
)
from vstack.adapters.openwebui import as_openwebui_manifest
from vstack.aar import StubClient
from vstack.mcp._registry import PATTERNS


# ----------------------------------------------------------------------
# Core registry-driven spec
# ----------------------------------------------------------------------


def test_one_spec_per_pattern() -> None:
    specs = list_pattern_tool_specs()
    assert len(specs) == 34
    assert {s.pattern_name for s in specs} == {p.name for p in PATTERNS}


def test_spec_schema_serializes_to_json() -> None:
    for spec in list_pattern_tool_specs():
        # round-trip through json so we know it's serializable
        body = json.dumps(spec.input_schema)
        assert "mode" in body
        assert "model" in body


def test_pattern_tool_spec_for_returns_correct_pattern() -> None:
    spec = pattern_tool_spec_for("lewin")
    assert spec.pattern_name == "lewin"
    assert spec.name == "vstack_lewin"
    assert "Lewin" in spec.friendly


def test_pattern_tool_spec_for_unknown_raises() -> None:
    with pytest.raises(KeyError):
        pattern_tool_spec_for("does_not_exist")


def test_serialize_detection_handles_pydantic_and_plain() -> None:
    from vstack.lewin import LewinDetection, LocusEvidence, LewinIntervention

    detection = LewinDetection(
        agent_id="t",
        dominant_locus="environmental",
        locus_scores={
            "internal": 0.1,
            "environmental": 0.9,
            "interactional": 0.0,
            "indeterminate": 0.0,
        },
        loci=[
            LocusEvidence(
                locus="environmental",
                score=0.9,
                severity="high",
                explanation="x",
                evidence_quotes=[],
            )
        ],
        interventions=[
            LewinIntervention(
                target_locus="environmental",
                intervention_type="change_rag_index",
                description="x",
                suggested_implementation="y",
                estimated_impact="high",
                rationale="z",
            )
        ],
        attribution_quality="well-attributed",
        initial_attribution_correct=False,
        generator_model="test",
        success=False,
    )
    payload = serialize_detection(detection)
    assert payload["dominant_locus"] == "environmental"
    # Plain dict round-trip.
    assert serialize_detection({"foo": "bar"}) == {"foo": "bar"}


# ----------------------------------------------------------------------
# Dispatcher (the common code path every framework uses)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_dispatch_empty_payload_returns_structured_error(pattern) -> None:
    response = run_pattern_dispatch(
        pattern,
        {},
        llm_client_factory=lambda: StubClient([]),
    )
    assert isinstance(response, dict)
    assert response.get("error") in {
        "validation_error",
        "invalid_mode",
        "llm_resolution_error",
        "analyzer_error",
    }


def test_dispatch_invalid_mode() -> None:
    pattern = pattern_tool_spec_for("lewin").pattern
    response = run_pattern_dispatch(
        pattern,
        {
            "task": "x",
            "steps": [{"type": "input", "content": "x"}],
            "outcome": "x",
            "success": False,
            "mode": "BOGUS",
        },
        llm_client_factory=lambda: StubClient([]),
    )
    assert response.get("error") == "invalid_mode"


def test_dispatch_lewin_end_to_end_with_stub() -> None:
    scores = json.dumps(
        [
            {
                "locus": "environmental",
                "score": 0.9,
                "severity": "high",
                "explanation": "stale RAG",
                "evidence_quotes": ["returned a 2003 Wikipedia revision"],
            }
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_locus": "environmental",
                "intervention_type": "change_rag_index",
                "description": "x",
                "suggested_implementation": "y",
                "estimated_impact": "high",
                "rationale": "z",
            }
        ]
    )
    stub = StubClient([scores, interventions])

    spec = pattern_tool_spec_for("lewin")
    response = run_pattern_dispatch(
        spec.pattern,
        {
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
        },
        llm_client_factory=lambda: stub,
    )
    assert "error" not in response
    assert response["dominant_locus"] == "environmental"


# ----------------------------------------------------------------------
# Pure-JSON adapters
# ----------------------------------------------------------------------


def test_openai_tool_schemas_one_per_pattern() -> None:
    schemas = as_openai_tool_schemas()
    assert len(schemas) == 34
    assert all(s["type"] == "function" for s in schemas)
    assert all("name" in s["function"] and "parameters" in s["function"] for s in schemas)
    # JSON-serializable end-to-end.
    json.dumps(schemas)


def test_anthropic_tool_schemas_one_per_pattern() -> None:
    schemas = as_anthropic_tool_schemas()
    assert len(schemas) == 34
    for s in schemas:
        assert s["name"].startswith("vstack_")
        assert "input_schema" in s
    json.dumps(schemas)


def test_autogen_function_manifest_one_per_pattern() -> None:
    manifest = as_autogen_function_manifest()
    assert len(manifest) == 34
    for entry in manifest:
        assert "name" in entry and "parameters" in entry
    json.dumps(manifest)


def test_autogen_callables_match_manifest() -> None:
    callables = as_autogen_callables(llm_client_factory=lambda: StubClient([]))
    manifest = as_autogen_function_manifest()
    assert set(callables.keys()) == {entry["name"] for entry in manifest}
    # Each callable returns a dict (validation error on empty payload).
    sample = next(iter(callables.values()))
    result = sample()
    assert isinstance(result, dict)


def test_openwebui_manifest_shape() -> None:
    manifest = as_openwebui_manifest(api_base_url="http://localhost:8000")
    assert manifest["name"] == "vstack"
    assert manifest["openapi_url"] == "http://localhost:8000/openapi.json"
    assert len(manifest["tools"]) == 34
    sample = manifest["tools"][0]
    assert sample["method"] == "POST"
    assert sample["url"].startswith("http://localhost:8000/v1/analyze/")
    json.dumps(manifest)


# ----------------------------------------------------------------------
# Framework-gated adapters (skipped when framework isn't installed)
# ----------------------------------------------------------------------


def _has_module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_module("langchain_core"), reason="langchain_core not installed")
def test_langchain_tools_when_installed() -> None:
    from vstack.adapters.langchain import as_langchain_tools

    tools = as_langchain_tools(llm_client_factory=lambda: StubClient([]))
    assert len(tools) == 34
    assert all(hasattr(t, "name") for t in tools)


@pytest.mark.skipif(not _has_module("langgraph"), reason="langgraph not installed")
def test_langgraph_nodes_when_installed() -> None:
    from vstack.adapters.langgraph import as_langgraph_nodes

    nodes = as_langgraph_nodes(llm_client_factory=lambda: StubClient([]))
    assert len(nodes) == 34
    # Each value is a callable.
    sample = next(iter(nodes.values()))
    assert callable(sample)


@pytest.mark.skipif(not _has_module("crewai"), reason="crewai not installed")
def test_crewai_tools_when_installed() -> None:
    from vstack.adapters.crewai import as_crewai_tools

    tools = as_crewai_tools(llm_client_factory=lambda: StubClient([]))
    assert len(tools) == 34


@pytest.mark.skipif(
    not (_has_module("llama_index.core.tools") or _has_module("llama_index.tools")),
    reason="llama_index not installed",
)
def test_llamaindex_tools_when_installed() -> None:
    from vstack.adapters.llamaindex import as_llamaindex_tools

    tools = as_llamaindex_tools(llm_client_factory=lambda: StubClient([]))
    assert len(tools) == 34


@pytest.mark.skipif(not _has_module("pydantic_ai"), reason="pydantic_ai not installed")
def test_pydantic_ai_tools_when_installed() -> None:
    from vstack.adapters.pydantic_ai import as_pydantic_ai_tools

    tools = as_pydantic_ai_tools(llm_client_factory=lambda: StubClient([]))
    assert len(tools) == 34
    assert all(callable(t.func) for t in tools)


def test_require_module_raises_actionable_error() -> None:
    """If the user calls a framework adapter without the framework
    installed, the error message names the pip extra to install."""
    with pytest.raises(AdapterImportError) as exc:
        require_module("definitely_not_a_real_module", extras_hint="langchain")
    assert "valanistack[langchain]" in str(exc.value)
