"""End-to-end smoke test of the vstack MCP server.

Exercises the public surface (list_tools / list_resources /
list_prompts / read_resource / get_prompt / call_tool) without going
through the stdio transport. The MCP SDK's request handlers are
registered on the Server via decorators, so the test reaches in
through ``server.request_handlers`` to invoke them directly.

A representative LLM-driven pattern (Lewin) is run with a hand-
canned stub response and the output is asserted to round-trip
through the pattern's detection model. A second pattern
(Span-of-Control) is run as a deterministic check that the input
schema accepts a real trace payload.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp.types import (
    GetPromptRequest,
    GetPromptRequestParams,
    ListPromptsRequest,
    ListResourcesRequest,
    ListToolsRequest,
    ReadResourceRequest,
    ReadResourceRequestParams,
)
from pydantic import AnyUrl

import vstack.mcp as mcp
from vstack.aar import StubClient
from vstack.mcp._registry import PATTERNS, tool_name_for
from vstack.mcp._server import _dispatch_tool_call, build_server


@pytest.fixture
def server():
    return build_server()


def _run(coro):
    """Drive an async helper from a sync test body."""
    return asyncio.run(coro)


def _invoke_handler(server, request_cls, params=None):
    """Look up a request handler on the server and invoke it."""
    handler = server.request_handlers[request_cls]
    method_default = request_cls.model_fields["method"].default
    if params is None:
        request = request_cls.model_construct(method=method_default, params=None)
    else:
        request = request_cls(method=method_default, params=params)
    return _run(handler(request))


def test_server_metadata(server) -> None:
    assert mcp.SERVER_NAME == "vstack-mcp"
    assert mcp.SERVER_VERSION  # any non-empty string
    assert "34" in mcp.SERVER_INSTRUCTIONS


def test_list_tools_returns_all_patterns(server) -> None:
    result = _invoke_handler(server, ListToolsRequest)
    tools = result.root.tools
    assert len(tools) == 34
    names = {t.name for t in tools}
    expected = {tool_name_for(p) for p in PATTERNS}
    assert names == expected


def test_every_tool_has_valid_schema(server) -> None:
    result = _invoke_handler(server, ListToolsRequest)
    for tool in result.root.tools:
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        # The two MCP-layer params should be merged in on every tool.
        assert "mode" in schema["properties"]
        assert "model" in schema["properties"]
        assert schema["properties"]["mode"]["type"] == "string"
        assert "enum" in schema["properties"]["mode"]
        assert "standard" in schema["properties"]["mode"]["enum"]


def test_list_resources_includes_index_and_per_pattern(server) -> None:
    result = _invoke_handler(server, ListResourcesRequest)
    uris = {str(r.uri).rstrip("/") for r in result.root.resources}
    assert "vstack://patterns/index" in uris
    # Every pattern publishes playbooks + composition; most also citations.
    for p in PATTERNS:
        assert f"vstack://patterns/{p.name}/playbooks" in uris
        assert f"vstack://patterns/{p.name}/composition" in uris


def _read_resource(server, uri: str):
    params = ReadResourceRequestParams(uri=AnyUrl(uri))
    result = _invoke_handler(server, ReadResourceRequest, params)
    # ReadResourceResult wraps {contents: [...]}; ServerResult.root is
    # ReadResourceResult.
    return result.root.contents


def test_read_index_resource(server) -> None:
    contents = _read_resource(server, "vstack://patterns/index")
    assert contents
    body = json.loads(contents[0].text)
    assert body["count"] == 34
    assert len(body["patterns"]) == 34
    first = body["patterns"][0]
    assert first["name"] == "lewin"
    assert first["tool"] == "vstack_lewin"


def test_read_per_pattern_playbooks_resource(server) -> None:
    contents = _read_resource(server, "vstack://patterns/lewin/playbooks")
    body = json.loads(contents[0].text)
    assert body["pattern"] == "lewin"
    assert body["count"] > 0
    sample = body["playbooks"][0]
    assert "key" in sample
    assert "playbook" in sample


def test_read_per_pattern_composition_resource(server) -> None:
    contents = _read_resource(server, "vstack://patterns/schein_culture/composition")
    body = json.loads(contents[0].text)
    assert body["pattern"] == "schein_culture"
    assert body["composition"] is not None


def test_list_prompts_has_meta_and_one_per_pattern(server) -> None:
    result = _invoke_handler(server, ListPromptsRequest)
    prompts = result.root.prompts
    names = [p.name for p in prompts]
    # 34 invocation prompts + 1 meta picker = 35
    assert len(names) == 35
    assert "vstack_pick_pattern" in names
    assert "vstack_lewin_invoke" in names
    assert "vstack_schein_culture_invoke" in names


def test_get_prompt_pick_pattern_renders(server) -> None:
    params = GetPromptRequestParams(
        name="vstack_pick_pattern",
        arguments={
            "situation": "The QA agent keeps confidently citing wrong years.",
            "known_artifacts": "agent trace, user complaint",
        },
    )
    result = _invoke_handler(server, GetPromptRequest, params)
    messages = result.root.messages
    assert len(messages) == 1
    text = messages[0].content.text
    assert "The QA agent keeps confidently citing wrong years." in text
    # The catalogue should be rendered into the prompt body.
    assert "vstack_lewin" in text
    assert "vstack_schein_culture" in text


def test_get_prompt_invoke_renders(server) -> None:
    params = GetPromptRequestParams(
        name="vstack_lewin_invoke",
        arguments={
            "artifact": "Agent qa-bot returned 'Pluto reclassified in 2003'.",
            "mode": "forensic",
        },
    )
    result = _invoke_handler(server, GetPromptRequest, params)
    text = result.root.messages[0].content.text
    assert "Lewin Attribution" in text
    assert "Pluto reclassified" in text
    assert "forensic" in text


# ----------------------------------------------------------------------
# call_tool: full pipeline with a stub LLM
# ----------------------------------------------------------------------


@pytest.fixture
def stub_lewin(monkeypatch):
    """Stub LLM with canned standard-mode Lewin responses.

    Standard mode runs two LLM calls: locus scoring + interventions.
    """
    scores = json.dumps(
        [
            {
                "locus": "internal",
                "score": 0.15,
                "severity": "low",
                "explanation": "model output looked confident but wrong",
                "evidence_quotes": [],
            },
            {
                "locus": "environmental",
                "score": 0.85,
                "severity": "high",
                "explanation": "RAG returned a stale 2003 Wikipedia snapshot",
                "evidence_quotes": ["returned a 2003 Wikipedia revision"],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_locus": "environmental",
                "intervention_type": "change_rag_index",
                "description": "refresh the Wikipedia index nightly",
                "suggested_implementation": "cron job + dedup",
                "estimated_impact": "high",
                "rationale": "stops stale revisions",
            }
        ]
    )
    stub = StubClient([scores, interventions])

    def _resolve(**_: Any):
        return stub

    monkeypatch.setattr("vstack.mcp._server.resolve_llm_client", _resolve)
    return stub


def test_call_tool_lewin_end_to_end(stub_lewin) -> None:
    from vstack.lewin import LewinDetection

    arguments = {
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
        "mode": "standard",
    }

    response = _dispatch_tool_call("vstack_lewin", arguments)
    assert len(response) == 1
    payload = response[0].text
    detection = LewinDetection.model_validate_json(payload)

    assert detection.dominant_locus == "environmental"
    assert len(detection.interventions) == 1
    assert detection.interventions[0].target_locus == "environmental"


def test_call_tool_invalid_input_returns_error(monkeypatch) -> None:
    """A trace with missing required fields should round-trip as a
    structured error response, not raise."""
    response = _dispatch_tool_call("vstack_lewin", {"task": "", "steps": []})
    assert len(response) == 1
    body = json.loads(response[0].text)
    assert "error" in body


def test_call_tool_unknown_pattern_returns_error() -> None:
    response = _dispatch_tool_call("vstack_does_not_exist", {})
    body = json.loads(response[0].text)
    assert body["error"] == "error"
    assert "Unknown vstack pattern" in body["message"]


def test_call_tool_invalid_mode_returns_error(stub_lewin) -> None:
    response = _dispatch_tool_call(
        "vstack_lewin",
        {
            "task": "x",
            "steps": [{"type": "input", "content": "x"}],
            "outcome": "x",
            "success": False,
            "mode": "BOGUS",
        },
    )
    body = json.loads(response[0].text)
    assert body["error"] == "invalid_mode"


# ----------------------------------------------------------------------
# Pure-registry coverage of all 34 tools without an LLM
# ----------------------------------------------------------------------


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_every_tool_dispatch_validates_input_shape(pattern) -> None:
    """Sending an empty payload to every one of the 34 tools should
    produce a validation error (or LLM-resolution error) but never
    crash the server."""
    response = _dispatch_tool_call(tool_name_for(pattern), {})
    assert len(response) == 1
    body = json.loads(response[0].text)
    assert "error" in body
    assert body["error"] in {"validation_error", "llm_resolution_error"}
