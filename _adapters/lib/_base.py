"""Adapter-shared helpers.

Each framework-specific module turns a :class:`PatternToolSpec` into
its native tool / node / function-schema shape. The spec itself is
framework-neutral and is derived from ``vstack.mcp._registry`` at
import time.

The dispatcher (:func:`run_pattern_dispatch`) is the single chunk of
logic that every adapter shares: validate input dict against the
pattern's Pydantic input model, resolve an LLM client, instantiate
the analyzer, run, serialize the detection back to a JSON-friendly
dict. Per-framework modules only translate the spec into a tool
object and bind the dispatcher as the callable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import BaseModel

from vstack.mcp._client import (
    LLMResolutionError,
    default_model_for,
    resolve_llm_client,
)
from vstack.mcp._registry import PATTERNS, PatternEntry, tool_name_for


class AdapterImportError(ImportError):
    """Raised when an adapter is invoked but its framework is not installed."""


@dataclass(frozen=True)
class PatternToolSpec:
    """Framework-neutral description of one pattern as a tool.

    Every adapter consumes specs of this shape -- they are derived
    from ``vstack.mcp._registry`` so the MCP server, REST API, and
    every framework adapter all describe the same tool surface.
    """

    name: str
    """The tool name in the same form MCP exposes: ``vstack_<pattern_name>``."""

    pattern_name: str
    """The pattern's import name, e.g. ``"lewin"``."""

    friendly: str
    """Human-readable label, e.g. ``"Lewin Attribution"``."""

    description: str
    """One-paragraph description suitable for tool docstrings."""

    input_schema: dict[str, Any]
    """JSON schema for the tool's input, with ``mode`` and ``model``
    optional fields merged at the top level."""

    output_schema: dict[str, Any]
    """JSON schema for the tool's output detection."""

    mode_values: tuple[str, ...]
    """Valid pipeline modes (typically quick / standard / forensic)."""

    pattern: PatternEntry
    """The underlying registry entry, for adapters that need extra fields."""


def list_pattern_tool_specs() -> list[PatternToolSpec]:
    """Return one :class:`PatternToolSpec` per registered pattern."""
    return [_build_spec(p) for p in PATTERNS]


def pattern_tool_spec_for(pattern_name: str) -> PatternToolSpec:
    """Return the spec for a single pattern by its import name."""
    for p in PATTERNS:
        if p.name == pattern_name:
            return _build_spec(p)
    raise KeyError(f"Unknown vstack pattern: {pattern_name}")


def run_pattern_dispatch(
    pattern: PatternEntry,
    arguments: dict[str, Any],
    *,
    llm_client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Run one pattern given a JSON-friendly arguments dict.

    Parameters
    ----------
    pattern:
        Registry entry to invoke.
    arguments:
        Dict that may include ``mode``, ``model``, and the trace
        fields at the top level (matches how the MCP server unwraps
        tool-call input).
    llm_client_factory:
        Optional zero-arg callable returning an LLM client. Defaults
        to :func:`vstack.mcp.resolve_llm_client`. Tests inject a stub.

    Returns
    -------
    dict
        On success, the detection model dumped to a JSON-safe dict.
        On failure, a ``{"error": "<kind>", "message": "..."}``
        envelope -- adapters can choose to raise or surface this.
    """
    arguments = dict(arguments or {})
    mode = arguments.pop("mode", None)
    model = arguments.pop("model", None)

    resolved = pattern.load()

    if mode and mode not in resolved.mode_values:
        return {
            "error": "invalid_mode",
            "message": (
                f"Mode {mode!r} not valid for {pattern.name}. Allowed: {list(resolved.mode_values)}"
            ),
        }

    try:
        trace = resolved.input_cls.model_validate(arguments)
    except Exception as e:  # pydantic.ValidationError
        return {"error": "validation_error", "message": str(e)}

    factory = llm_client_factory or resolve_llm_client
    try:
        llm = factory()
    except LLMResolutionError as e:
        return {"error": "llm_resolution_error", "message": str(e)}

    chosen_mode = mode or "standard"
    chosen_model = model or default_model_for(llm)

    try:
        analyzer = resolved.analyzer_cls(llm, model=chosen_model, mode=chosen_mode)
        detection = analyzer.run(trace)
    except Exception as e:  # noqa: BLE001 - runtime analyzer failure
        return {"error": "analyzer_error", "message": str(e)}

    return serialize_detection(detection)


def serialize_detection(obj: Any) -> dict[str, Any]:
    """Return a JSON-safe dict view of a Pydantic detection."""
    if isinstance(obj, BaseModel):
        result = obj.model_dump(mode="json")
    else:
        result = json.loads(json.dumps(obj, default=str))
    if not isinstance(result, dict):
        return {"value": result}
    return result


def require_module(module_name: str, extras_hint: str | None = None) -> Any:
    """Import a framework module, raising AdapterImportError if missing.

    Every framework adapter calls this at the top of its public
    factory function so the import error becomes actionable
    ("install ``valanistack[langchain]``") instead of a stack trace.
    """
    import importlib

    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        hint = f" Run: pip install 'valanistack[{extras_hint}]'" if extras_hint else ""
        raise AdapterImportError(
            f"vstack adapter requires the '{module_name}' package, which is not installed.{hint}"
        ) from e


def _build_spec(pattern: PatternEntry) -> PatternToolSpec:
    resolved = pattern.load()
    input_schema = _augmented_input_schema(resolved, pattern)
    output_schema = resolved.output_cls.model_json_schema()
    description = _build_description(pattern, resolved.mode_values)
    return PatternToolSpec(
        name=tool_name_for(pattern),
        pattern_name=pattern.name,
        friendly=pattern.friendly,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
        mode_values=tuple(resolved.mode_values),
        pattern=pattern,
    )


def _augmented_input_schema(resolved: Any, pattern: PatternEntry) -> dict[str, Any]:
    """The pattern's input model schema + top-level ``mode`` / ``model``."""
    trace_schema = resolved.input_cls.model_json_schema()
    properties: dict[str, Any] = dict(trace_schema.get("properties", {}))
    required = list(trace_schema.get("required", []))
    defs = dict(trace_schema.get("$defs", {}))
    properties["mode"] = {
        "type": "string",
        "enum": list(resolved.mode_values),
        "description": (
            "Pipeline mode. 'quick' = 1 LLM call (CI / live ops); "
            "'standard' = 2 LLM calls (default); 'forensic' = 4 LLM "
            "calls with deep audits. Defaults to 'standard'."
        ),
    }
    properties["model"] = {
        "type": "string",
        "description": (
            "LLM model identifier passed to the analyzer "
            "(e.g. 'claude-sonnet-4-6', 'gpt-4o'). Auto-selected if omitted."
        ),
    }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    if defs:
        schema["$defs"] = defs
    if "description" in trace_schema:
        schema["description"] = trace_schema["description"]
    return schema


def _build_description(pattern: PatternEntry, mode_values: Iterable[str]) -> str:
    return (
        f"{pattern.summary}\n\n"
        f"Group: {pattern.group}. Input: {pattern.input_cls}. "
        f"Output: {pattern.output_cls}. "
        f"Modes: {', '.join(mode_values)}."
    )
