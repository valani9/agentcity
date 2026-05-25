"""Pydantic AI tool bindings.

Pydantic AI exposes tools as plain Python functions decorated with
``@agent.tool_plain``. Since the underlying registry already speaks
Pydantic, the integration is the thinnest of all adapters: hand back
``(callable, name, description)`` tuples that callers register on
their own agent.

Install with ``pip install 'valanistack[pydantic_ai]'``.
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

from ._base import (
    AdapterImportError,
    PatternToolSpec,
    list_pattern_tool_specs,
    require_module,
    run_pattern_dispatch,
)


class PydanticAITool(NamedTuple):
    name: str
    description: str
    func: Callable[..., dict[str, Any]]


def as_pydantic_ai_tools(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
) -> list[PydanticAITool]:
    """Return per-pattern ``(name, description, func)`` triples.

    Register on your agent::

        from pydantic_ai import Agent
        from vstack.adapters.pydantic_ai import as_pydantic_ai_tools

        agent = Agent(...)
        for tool in as_pydantic_ai_tools():
            agent.tool_plain(tool.func, name=tool.name)
    """
    # Verify the framework is importable; callers may pass our
    # callables to any agent shape but a useful early error helps.
    require_module("pydantic_ai", extras_hint="pydantic_ai")

    specs = specs or list_pattern_tool_specs()
    out: list[PydanticAITool] = []
    for spec in specs:
        fn = _build_callable(spec, llm_client_factory)
        out.append(PydanticAITool(spec.name, spec.description, fn))
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


__all__ = ["AdapterImportError", "PydanticAITool", "as_pydantic_ai_tools"]
