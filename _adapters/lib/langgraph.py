"""LangGraph node factories.

LangGraph nodes are plain callables that take a state dict and return
a state delta. Each pattern is exposed as a node factory: pass it the
state-key paths to pull trace data from, and it returns a callable
LangGraph node.
"""

from __future__ import annotations

from typing import Any, Callable

from ._base import (
    AdapterImportError,
    PatternToolSpec,
    list_pattern_tool_specs,
    pattern_tool_spec_for,
    require_module,
    run_pattern_dispatch,
)


def as_langgraph_nodes(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
    state_key: str = "trace",
    output_key_prefix: str = "vstack_",
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Return ``{node_name: node_fn}`` mapping for all (or selected) patterns.

    Each node reads the trace dict from ``state[state_key]``, dispatches
    the pattern, and writes the detection back to
    ``state[output_key_prefix + pattern_name]``.

    Compose into a :class:`langgraph.graph.StateGraph` with
    ``graph.add_node(name, fn)``.

    Importing this module requires ``valanistack[langgraph]``; the
    function delays the import so ``vstack.adapters.langgraph`` is
    cheap until callers actually need it.
    """
    # The import is verified here so users get a clear error before
    # any graph construction begins, even though we don't directly use
    # langgraph symbols below (the returned callables are framework-
    # neutral and only need to satisfy the StateGraph node contract).
    require_module("langgraph", extras_hint="langgraph")

    specs = specs or list_pattern_tool_specs()
    return {
        spec.name: _build_node(spec, llm_client_factory, state_key, output_key_prefix)
        for spec in specs
    }


def node_for(
    pattern_name: str,
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    state_key: str = "trace",
    output_key_prefix: str = "vstack_",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a single LangGraph node for one pattern by name."""
    require_module("langgraph", extras_hint="langgraph")
    spec = pattern_tool_spec_for(pattern_name)
    return _build_node(spec, llm_client_factory, state_key, output_key_prefix)


def _build_node(
    spec: PatternToolSpec,
    llm_client_factory: Callable[[], Any] | None,
    state_key: str,
    output_key_prefix: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    pattern = spec.pattern

    def node(state: dict[str, Any]) -> dict[str, Any]:
        trace_data = state.get(state_key, {})
        if not isinstance(trace_data, dict):
            return {
                output_key_prefix + pattern.name: {
                    "error": "state_shape",
                    "message": (
                        f"Expected state[{state_key!r}] to be a dict; "
                        f"got {type(trace_data).__name__}."
                    ),
                }
            }
        result = run_pattern_dispatch(
            pattern,
            dict(trace_data),
            llm_client_factory=llm_client_factory,
        )
        return {output_key_prefix + pattern.name: result}

    node.__name__ = f"vstack_{pattern.name}_node"
    node.__doc__ = spec.description
    return node


__all__ = ["AdapterImportError", "as_langgraph_nodes", "node_for"]
