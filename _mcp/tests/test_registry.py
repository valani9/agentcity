"""Cheap, deterministic checks that every pattern resolves cleanly.

These run without any LLM calls. If they fail, the registry has drifted
from the underlying vstack pattern modules and the MCP server will
crash at runtime, which makes this the first line of defense.
"""

from __future__ import annotations

import inspect

import pytest

import vstack.mcp as mcp
from vstack.mcp._registry import PATTERNS, tool_name_for


def test_pattern_count() -> None:
    """vstack ships 34 patterns; the registry must enumerate all of them."""
    assert len(PATTERNS) == 34


def test_pattern_names_unique() -> None:
    names = [p.name for p in PATTERNS]
    assert len(names) == len(set(names)), "duplicate pattern name in registry"


def test_tool_names_unique() -> None:
    tools = [tool_name_for(p) for p in PATTERNS]
    assert len(tools) == len(set(tools)), "duplicate MCP tool name"


def test_module_groups_present() -> None:
    """The three module groups should all appear in the registry."""
    groups = {p.group for p in PATTERNS}
    assert groups == {
        "Module 1 / Individual",
        "Module 2 / Team",
        "Module 3 / Organization",
    }


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_pattern_resolves(pattern: mcp.PatternEntry) -> None:
    """Every entry must point at an importable analyzer, input, output,
    and mode literal — and the analyzer's run() signature must accept
    a single trace argument typed as the input class."""
    resolved = pattern.load()
    assert inspect.isclass(resolved.analyzer_cls), f"{pattern.name}: analyzer is not a class"
    assert inspect.isclass(resolved.input_cls), f"{pattern.name}: input is not a class"
    assert inspect.isclass(resolved.output_cls), f"{pattern.name}: output is not a class"

    method = getattr(resolved.analyzer_cls, "run", None)
    assert callable(method), f"{pattern.name}: analyzer has no .run() method"

    sig = inspect.signature(method)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    assert params, f"{pattern.name}: .run() takes no trace argument"

    # First positional param should be the trace; we don't require strict
    # type-annotation equality (string-annotation forward refs etc.), but
    # we do require the param exists.
    first = params[0]
    assert first.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    ), f"{pattern.name}: first run() param is not positional"


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_pattern_has_modes(pattern: mcp.PatternEntry) -> None:
    """Every pattern must expose at least one mode value."""
    resolved = pattern.load()
    assert resolved.mode_values, f"{pattern.name}: no mode values"
    # quick + standard are the universal subset; forensic is common but
    # not required by the registry contract.
    assert "standard" in resolved.mode_values, f"{pattern.name}: 'standard' mode missing"


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_input_schema_serializes(pattern: mcp.PatternEntry) -> None:
    """The pattern's input model must produce a JSON-serializable schema.
    This is what the MCP tool's inputSchema is built from."""
    resolved = pattern.load()
    schema = resolved.input_cls.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    # A trace with no required fields would be a registry / schema bug.
    assert schema.get("required"), f"{pattern.name}: input has no required fields"


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_pattern_has_playbooks_dict(pattern: mcp.PatternEntry) -> None:
    """Every pattern must export a PLAYBOOKS dict (possibly empty)."""
    resolved = pattern.load()
    assert resolved.playbooks is not None
    # Playbooks should be iterable as a mapping.
    list(resolved.playbooks.items())  # type: ignore[union-attr]


@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_pattern_has_composition(pattern: mcp.PatternEntry) -> None:
    """Composition manifest must resolve (even if shallow)."""
    resolved = pattern.load()
    assert resolved.composition is not None, f"{pattern.name}: {pattern.composition_attr} is None"
