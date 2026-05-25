"""CrewAI tool bindings.

CrewAI's ``BaseTool`` accepts a callable and a Pydantic args schema;
each pattern wraps to a ``BaseTool`` subclass with the registry's
input model as the args schema.

Install with ``pip install 'valanistack[crewai]'``.
"""

from __future__ import annotations

from typing import Any, Callable, Type

from ._base import (
    AdapterImportError,
    PatternToolSpec,
    list_pattern_tool_specs,
    require_module,
    run_pattern_dispatch,
)


def as_crewai_tools(
    *,
    llm_client_factory: Callable[[], Any] | None = None,
    specs: list[PatternToolSpec] | None = None,
) -> list[Any]:
    """Return one CrewAI ``BaseTool`` subclass instance per pattern."""
    crewai_tools = require_module("crewai.tools", extras_hint="crewai")
    BaseTool = crewai_tools.BaseTool

    specs = specs or list_pattern_tool_specs()
    return [_build_tool(spec, llm_client_factory, BaseTool) for spec in specs]


def _build_tool(
    spec: PatternToolSpec,
    llm_client_factory: Callable[[], Any] | None,
    BaseTool: Type[Any],
) -> Any:
    pattern = spec.pattern
    resolved = pattern.load()

    # CrewAI's BaseTool is class-based; we build a per-pattern subclass
    # so the docstring, name, and args_schema all carry through.
    def _run(self: Any, **kwargs: Any) -> dict[str, Any]:
        return run_pattern_dispatch(pattern, kwargs, llm_client_factory=llm_client_factory)

    cls_name = f"Vstack{_camel(pattern.name)}Tool"
    cls = type(
        cls_name,
        (BaseTool,),
        {
            "name": spec.name,
            "description": spec.description,
            "args_schema": resolved.input_cls,
            "_run": _run,
        },
    )
    return cls()


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_"))


__all__ = ["AdapterImportError", "as_crewai_tools"]
