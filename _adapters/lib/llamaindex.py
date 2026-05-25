"""LlamaIndex tool bindings.

Maps the 34 patterns onto LlamaIndex's ``FunctionTool``. Install with
``pip install 'valanistack[llamaindex]'``.
"""

from __future__ import annotations

from typing import Any, Callable

from ._base import (
    AdapterImportError,
    PatternToolSpec,
    list_pattern_tool_specs,
    require_module,
    run_pattern_dispatch,
)


def as_llamaindex_tools(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
) -> list[Any]:
    """Return one LlamaIndex ``FunctionTool`` per pattern."""
    # LlamaIndex moved the tools module a couple of times; try the
    # canonical 0.10+ path first, fall back to legacy locations.
    try:
        tools_mod = require_module("llama_index.core.tools", extras_hint="llamaindex")
    except AdapterImportError:
        tools_mod = require_module("llama_index.tools", extras_hint="llamaindex")
    FunctionTool = tools_mod.FunctionTool

    specs = specs or list_pattern_tool_specs()
    return [_build_tool(spec, llm_client_factory, FunctionTool) for spec in specs]


def _build_tool(
    spec: PatternToolSpec,
    llm_client_factory: Callable[[], Any] | None,
    FunctionTool: Any,
) -> Any:
    pattern = spec.pattern
    resolved = pattern.load()

    def _invoke(**kwargs: Any) -> dict[str, Any]:
        return run_pattern_dispatch(pattern, kwargs, llm_client_factory=llm_client_factory)

    _invoke.__name__ = spec.name
    _invoke.__doc__ = spec.description

    return FunctionTool.from_defaults(
        fn=_invoke,
        name=spec.name,
        description=spec.description,
        fn_schema=resolved.input_cls,
    )


__all__ = ["AdapterImportError", "as_llamaindex_tools"]
