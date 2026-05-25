"""OpenAI Assistants / function-calling tool schemas.

Returns JSON shapes ready to drop into OpenAI's tool-use APIs. No
external dependencies required -- the OpenAI ``tools`` parameter is a
plain JSON document.

The Anthropic Messages API uses the same ``input_schema`` shape, so
:func:`as_anthropic_tool_schemas` is a thin re-export.
"""

from __future__ import annotations

from typing import Any

from ._base import PatternToolSpec, list_pattern_tool_specs


def as_openai_tool_schemas(specs: list[PatternToolSpec] | None = None) -> list[dict[str, Any]]:
    """Return OpenAI Chat Completions / Assistants ``tools`` array.

    Shape: ``[{"type": "function", "function": {"name", "description",
    "parameters"}}, ...]`` -- the canonical OpenAI tool spec.
    """
    specs = specs or list_pattern_tool_specs()
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema,
            },
        }
        for spec in specs
    ]


def as_anthropic_tool_schemas(specs: list[PatternToolSpec] | None = None) -> list[dict[str, Any]]:
    """Return Anthropic Messages API ``tools`` array.

    Shape: ``[{"name", "description", "input_schema"}, ...]``.
    """
    specs = specs or list_pattern_tool_specs()
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in specs
    ]
