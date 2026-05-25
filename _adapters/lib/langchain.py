"""LangChain tool bindings.

Each of the 34 patterns becomes a ``StructuredTool`` that LangChain
agents can pick up. Install with ``pip install 'valanistack[langchain]'``.
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


def as_langchain_tools(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
) -> list[Any]:
    """Return a list of LangChain ``StructuredTool`` instances, one per pattern.

    Parameters
    ----------
    llm_client_factory:
        Optional zero-arg callable returning an LLM client. Defaults
        to :func:`vstack.mcp.resolve_llm_client`.
    specs:
        Optional pre-built spec list (useful for filtering down to a
        subset of patterns). Defaults to all 34.
    """
    lc_tools = require_module("langchain_core.tools", extras_hint="langchain")
    StructuredTool = lc_tools.StructuredTool

    specs = specs or list_pattern_tool_specs()
    return [_build_tool(spec, llm_client_factory, StructuredTool) for spec in specs]


def _build_tool(
    spec: PatternToolSpec,
    llm_client_factory: Callable[[], Any] | None,
    StructuredTool: Any,
) -> Any:
    pattern = spec.pattern

    def _invoke(**kwargs: Any) -> dict[str, Any]:
        return run_pattern_dispatch(pattern, kwargs, llm_client_factory=llm_client_factory)

    # LangChain's StructuredTool accepts a JSON schema via args_schema;
    # the older `args_schema` slot wanted a Pydantic class, but newer
    # versions accept the dict form. We pass both forms via the
    # registry's resolved input class for older versions, and the
    # raw schema for newer ones (LangChain ignores the unrecognized
    # kwarg if any).
    resolved = pattern.load()
    return StructuredTool.from_function(
        func=_invoke,
        name=spec.name,
        description=spec.description,
        args_schema=resolved.input_cls,
    )


__all__ = ["AdapterImportError", "as_langchain_tools"]
