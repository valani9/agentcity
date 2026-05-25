"""MCP resource handlers — citation files, playbooks, composition manifests.

Resources let an LLM browse pattern reference material (the academic
anchors and the failure-mode playbooks) without invoking a tool. The
URI scheme is::

    vstack://patterns/<name>/citations
    vstack://patterns/<name>/playbooks
    vstack://patterns/<name>/composition
    vstack://patterns/index

The catalogue resource (``vstack://patterns/index``) lists every
registered pattern with its friendly label, summary, and tool name —
useful for an LLM picking which tool to call.
"""

from __future__ import annotations

import importlib.resources as ir
import json
from typing import Any

from pydantic import BaseModel

from ._registry import PATTERNS, PATTERNS_BY_NAME, PatternEntry, tool_name_for

INDEX_URI = "vstack://patterns/index"


def list_resource_uris() -> list[tuple[str, str, str, str]]:
    """Enumerate every resource URI the server publishes.

    Returns a list of ``(uri, name, description, mime_type)`` tuples.
    """
    out: list[tuple[str, str, str, str]] = [
        (
            INDEX_URI,
            "vstack pattern index",
            "Catalogue of all 34 vstack patterns with summaries and tool names.",
            "application/json",
        ),
    ]
    for p in PATTERNS:
        if p.citations_present:
            out.append(
                (
                    f"vstack://patterns/{p.name}/citations",
                    f"{p.friendly} citations",
                    f"Academic anchors and reading list for {p.friendly}.",
                    "text/markdown",
                )
            )
        out.append(
            (
                f"vstack://patterns/{p.name}/playbooks",
                f"{p.friendly} playbooks",
                (
                    f"Failure-mode playbooks for {p.friendly}: one recipe per "
                    "(locus, factor) combination with literature-anchored "
                    "intervention guidance."
                ),
                "application/json",
            )
        )
        out.append(
            (
                f"vstack://patterns/{p.name}/composition",
                f"{p.friendly} composition manifest",
                (
                    f"Cross-pattern handoff recommendations for {p.friendly}: "
                    "which upstream / downstream vstack patterns to run, "
                    "plus framework overlays (LangGraph / CrewAI / AutoGen)."
                ),
                "application/json",
            )
        )
    return out


def read_resource(uri: str) -> tuple[str, str]:
    """Resolve a vstack resource URI to ``(mime_type, content_str)``."""
    if uri == INDEX_URI:
        return ("application/json", _build_index())

    parsed = _parse_pattern_uri(uri)
    if parsed is None:
        raise ValueError(f"Unknown vstack resource URI: {uri}")
    pattern_name, kind = parsed
    pattern = PATTERNS_BY_NAME.get(pattern_name)
    if pattern is None:
        raise ValueError(f"Unknown vstack pattern: {pattern_name}")

    if kind == "citations":
        return ("text/markdown", _read_citations(pattern))
    if kind == "playbooks":
        return ("application/json", _serialize_playbooks(pattern))
    if kind == "composition":
        return ("application/json", _serialize_composition(pattern))
    raise ValueError(f"Unknown vstack resource kind: {kind!r} in {uri}")


def _parse_pattern_uri(uri: str) -> tuple[str, str] | None:
    prefix = "vstack://patterns/"
    if not uri.startswith(prefix):
        return None
    body = uri[len(prefix) :]
    parts = body.split("/")
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


def _build_index() -> str:
    rows: list[dict[str, Any]] = []
    for p in PATTERNS:
        rows.append(
            {
                "name": p.name,
                "friendly": p.friendly,
                "group": p.group,
                "tool": tool_name_for(p),
                "summary": p.summary,
                "input_class": p.input_cls,
                "output_class": p.output_cls,
                "resources": {
                    "citations": (
                        f"vstack://patterns/{p.name}/citations" if p.citations_present else None
                    ),
                    "playbooks": f"vstack://patterns/{p.name}/playbooks",
                    "composition": f"vstack://patterns/{p.name}/composition",
                },
            }
        )
    return json.dumps({"patterns": rows, "count": len(rows)}, indent=2)


def _read_citations(pattern: PatternEntry) -> str:
    if not pattern.citations_present:
        return (
            f"# {pattern.friendly}\n\n"
            "(No per-pattern CITATIONS.md ships with this pattern. "
            "See the top-level repo CITATIONS.md for the foundational "
            "literature anchors.)"
        )
    res = ir.files(f"vstack.{pattern.name}").joinpath("CITATIONS.md")
    return res.read_text(encoding="utf-8")


def _serialize_playbooks(pattern: PatternEntry) -> str:
    resolved = pattern.load()
    raw = resolved.playbooks
    if not raw:
        return json.dumps({"pattern": pattern.name, "playbooks": []}, indent=2)
    entries: list[dict[str, Any]] = []
    for key, playbook in raw.items():
        # Keys are usually tuples like (locus, factor); fall back to str().
        if isinstance(key, tuple):
            key_repr = "::".join(str(k) for k in key)
            key_parts = list(key)
        else:
            key_repr = str(key)
            key_parts = [str(key)]
        payload = _to_jsonable(playbook)
        entries.append({"key": key_repr, "key_parts": key_parts, "playbook": payload})
    return json.dumps(
        {"pattern": pattern.name, "playbooks": entries, "count": len(entries)},
        indent=2,
    )


def _serialize_composition(pattern: PatternEntry) -> str:
    resolved = pattern.load()
    payload = _to_jsonable(resolved.composition)
    return json.dumps({"pattern": pattern.name, "composition": payload}, indent=2)


def _to_jsonable(obj: Any) -> Any:
    """Best-effort JSON-friendly view of a Pydantic model or container."""
    if obj is None:
        return None
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    # Fall back to repr — keeps the resource readable even when an
    # opaque object slips through.
    return repr(obj)
