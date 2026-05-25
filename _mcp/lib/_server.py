"""The vstack MCP server.

Wires the pattern registry, the resource handlers, and the prompt
templates into a single :class:`mcp.server.lowlevel.Server` instance.
The server speaks stdio by default — the user's MCP client (Claude
Desktop, Cursor, Cline, etc.) spawns ``vstack-mcp`` as a subprocess,
exchanges JSON-RPC over stdin/stdout, and never talks over a network
socket. Zero hosting cost on our side.

Tools
-----

One tool per pattern (34 total), named ``vstack_<pattern_name>``. The
input schema is the pattern's Pydantic input model plus two optional
top-level fields: ``mode`` (``quick`` / ``standard`` / ``forensic``)
and ``model`` (LLM model string). Tool result is the pattern's
detection model serialized to indented JSON.

Resources
---------

* ``vstack://patterns/index`` — catalogue JSON
* ``vstack://patterns/<name>/citations`` — per-pattern citations.md
* ``vstack://patterns/<name>/playbooks`` — per-pattern playbooks
* ``vstack://patterns/<name>/composition`` — composition manifest

Prompts
-------

* ``vstack_pick_pattern`` — meta routing prompt
* ``vstack_<name>_invoke`` — one per pattern (35 total with the meta)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from ._client import LLMResolutionError, default_model_for, resolve_llm_client
from ._prompts import list_prompts as list_pattern_prompts
from ._prompts import render_prompt
from ._registry import PATTERNS, PATTERNS_BY_NAME, PatternEntry, tool_name_for
from ._resources import list_resource_uris, read_resource as read_vstack_resource

SERVER_NAME = "vstack-mcp"
SERVER_VERSION = "0.2.0"
SERVER_INSTRUCTIONS = (
    "vstack — Organizational behavior, practiced on AI agents.\n\n"
    "34 diagnostic patterns spanning individual, team, and "
    "organizational scales. Each pattern is exposed as a tool that "
    "takes a Pydantic-typed trace and returns a structured detection "
    "with severity, evidence, attached playbooks, and recommended "
    "follow-up patterns.\n\n"
    "Use the 'vstack_pick_pattern' prompt to route a free-form "
    "problem to the right tool, or browse 'vstack://patterns/index' "
    "for the full catalogue."
)

logger = logging.getLogger(__name__)


def build_server() -> Server[None, Any]:
    """Construct and wire the MCP server.

    Returns an unstarted :class:`Server` instance. Call
    :func:`run_stdio` to serve it; tests bypass that and exercise the
    handlers directly via :func:`_dispatch_tool_call`.
    """
    server: Server[None, Any] = Server(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
    )

    # The MCP SDK's decorator methods (server.list_tools(),
    # server.call_tool(), ...) return Callables whose decorator
    # protocol is not fully annotated upstream. Per-line ignores
    # silence the resulting "untyped-decorator" / "no-untyped-call"
    # errors under --strict mypy without weakening the rest of the
    # file's typing.
    @server.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
    async def _list_tools() -> list[Tool]:
        return [_build_tool(p) for p in PATTERNS]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        return _dispatch_tool_call(name, arguments)

    @server.list_resources()  # type: ignore[untyped-decorator,no-untyped-call]
    async def _list_resources() -> list[Resource]:
        return [
            Resource(
                uri=AnyUrl(uri),
                name=name,
                description=desc,
                mimeType=mime,
            )
            for (uri, name, desc, mime) in list_resource_uris()
        ]

    @server.read_resource()  # type: ignore[untyped-decorator,no-untyped-call]
    async def _read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        mime, body = read_vstack_resource(str(uri))
        return [ReadResourceContents(content=body, mime_type=mime)]

    @server.list_prompts()  # type: ignore[untyped-decorator,no-untyped-call]
    async def _list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name=spec.name,
                description=spec.description,
                arguments=[
                    PromptArgument(
                        name=arg.name,
                        description=arg.description,
                        required=arg.required,
                    )
                    for arg in spec.arguments
                ],
            )
            for spec in list_pattern_prompts()
        ]

    @server.get_prompt()  # type: ignore[untyped-decorator,no-untyped-call]
    async def _get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
        text = render_prompt(name, arguments)
        return GetPromptResult(
            description=f"vstack prompt: {name}",
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
        )

    return server


def _build_tool(pattern: PatternEntry) -> Tool:
    """Synthesize an MCP Tool definition for one pattern.

    The tool's input schema is the pattern's Pydantic input model with
    a ``mode`` and a ``model`` parameter merged in at the top level.
    """
    resolved = pattern.load()
    trace_schema = resolved.input_cls.model_json_schema()

    # Start from the trace schema's $defs and properties; add two more
    # top-level params for the run-time options.
    properties: dict[str, Any] = dict(trace_schema.get("properties", {}))
    required = list(trace_schema.get("required", []))
    defs = dict(trace_schema.get("$defs", {}))

    properties["mode"] = {
        "type": "string",
        "enum": list(resolved.mode_values),
        "description": (
            "Pipeline mode. 'quick' = 1 LLM call (CI / live ops); "
            "'standard' = 2 LLM calls (default); 'forensic' = 4 LLM "
            "calls with deep audits. Defaults to 'standard' if omitted."
        ),
    }
    properties["model"] = {
        "type": "string",
        "description": (
            "LLM model identifier passed through to the analyzer "
            "(e.g. 'claude-sonnet-4-6', 'gpt-4o'). Defaults are "
            "auto-selected based on which API key is available."
        ),
    }

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    if defs:
        input_schema["$defs"] = defs
    if "description" in trace_schema:
        input_schema["description"] = trace_schema["description"]

    description = (
        f"{pattern.summary}\n\n"
        f"Group: {pattern.group}. Input: {pattern.input_cls}. "
        f"Output: {pattern.output_cls}. "
        f"Modes: {', '.join(resolved.mode_values)}. "
        f"Browse 'vstack://patterns/{pattern.name}/playbooks' for "
        f"the failure-mode playbooks attached to this pattern."
    )

    return Tool(
        name=tool_name_for(pattern),
        title=pattern.friendly,
        description=description,
        inputSchema=input_schema,
    )


def _dispatch_tool_call(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Run a single tool call against the corresponding analyzer.

    Errors are surfaced as JSON inside a TextContent block so the MCP
    client can show a structured failure instead of just an exception
    stringified out of the protocol layer.
    """
    if not name.startswith("vstack_"):
        return _error_response(f"Unknown vstack tool: {name}")
    pattern_name = name[len("vstack_") :]
    pattern = PATTERNS_BY_NAME.get(pattern_name)
    if pattern is None:
        return _error_response(f"Unknown vstack pattern: {pattern_name}")

    arguments = dict(arguments or {})
    mode = arguments.pop("mode", None)
    model = arguments.pop("model", None)

    resolved = pattern.load()
    try:
        trace = resolved.input_cls.model_validate(arguments)
    except Exception as e:  # noqa: BLE001 — Pydantic ValidationError is the common case
        return _error_response(
            f"Input validation failed for {pattern.name}: {e}",
            kind="validation_error",
        )

    try:
        llm = resolve_llm_client()
    except LLMResolutionError as e:
        return _error_response(str(e), kind="llm_resolution_error")

    chosen_mode = mode or "standard"
    if chosen_mode not in resolved.mode_values:
        return _error_response(
            f"Invalid mode {chosen_mode!r} for {pattern.name}. Valid: {list(resolved.mode_values)}",
            kind="invalid_mode",
        )

    chosen_model = model or default_model_for(llm)
    try:
        analyzer = resolved.analyzer_cls(llm, model=chosen_model, mode=chosen_mode)
        detection = analyzer.run(trace)
    except Exception as e:  # noqa: BLE001 — runtime analyzer failure
        logger.exception("vstack pattern %s failed", pattern.name)
        return _error_response(
            f"Analyzer {pattern.analyzer_cls} failed: {e}",
            kind="analyzer_error",
        )

    body = (
        detection.model_dump_json(indent=2)
        if hasattr(detection, "model_dump_json")
        else json.dumps(detection, default=str, indent=2)
    )
    return [TextContent(type="text", text=body)]


def _error_response(message: str, *, kind: str = "error") -> list[TextContent]:
    payload = json.dumps({"error": kind, "message": message}, indent=2)
    return [TextContent(type="text", text=payload)]


async def run_stdio() -> None:
    """Run the server over stdio. Blocks until the client disconnects."""
    from mcp.server.stdio import stdio_server

    server = build_server()
    # Quiet down vstack's structured JSON logging — when running over
    # stdio, anything emitted on stdout is interpreted as protocol
    # traffic by the MCP client, so logging must stay on stderr.
    logging.basicConfig(
        level=os.environ.get("VSTACK_MCP_LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    async with stdio_server() as (read_stream, write_stream):
        init_opts = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_opts)
