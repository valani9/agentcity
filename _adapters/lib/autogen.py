"""Microsoft AutoGen function-calling adapter.

AutoGen v0.4+ accepts an OpenAI-style function manifest plus a Python
callable for each function. We return both pieces so users can plug
straight into ``AssistantAgent(tools=...)`` or the older
``UserProxyAgent.register_for_llm`` flow.

No AutoGen import is required to USE the function manifest (it's just
JSON), so this adapter has no install-gate. The callables it returns
are pure-Python and don't depend on the autogen package.
"""

from __future__ import annotations

from typing import Any, Callable

from ._base import (
    PatternToolSpec,
    list_pattern_tool_specs,
    run_pattern_dispatch,
)


def as_autogen_function_manifest(
    specs: list[PatternToolSpec] | None = None,
) -> list[dict[str, Any]]:
    """Return AutoGen ``[{"name", "description", "parameters"}, ...]``."""
    specs = specs or list_pattern_tool_specs()
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_schema,
        }
        for spec in specs
    ]


def as_autogen_callables(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    """Return ``{tool_name: callable}`` for AutoGen function registration.

    Each callable accepts ``**kwargs`` matching the pattern's input
    schema (plus optional ``mode`` / ``model``) and returns the
    detection dict.
    """
    specs = specs or list_pattern_tool_specs()
    out: dict[str, Callable[..., dict[str, Any]]] = {}
    for spec in specs:
        out[spec.name] = _build_callable(spec, llm_client_factory)
    return out


def _build_callable(
    spec: PatternToolSpec,
    llm_client_factory: Callable[[], Any] | None,
) -> Callable[..., dict[str, Any]]:
    pattern = spec.pattern

    def _fn(**kwargs: Any) -> dict[str, Any]:
        return run_pattern_dispatch(pattern, kwargs, llm_client_factory=llm_client_factory)

    _fn.__name__ = spec.name
    _fn.__doc__ = spec.description
    return _fn


__all__ = ["as_autogen_function_manifest", "as_autogen_callables"]
