"""Open WebUI tool-server plugin.

Open WebUI consumes tools via an OpenAPI-spec'd HTTP server. The most
direct way to expose vstack to Open WebUI is to point it at the
``vstack-api`` server's OpenAPI spec; this module exposes a helper
that emits the equivalent plugin manifest so users don't have to
configure the URL by hand.

Pure JSON output -- no Open WebUI import required.
"""

from __future__ import annotations

from typing import Any

from ._base import PatternToolSpec, list_pattern_tool_specs


def as_openwebui_manifest(
    *,
    api_base_url: str = "http://127.0.0.1:8000",
    specs: list[PatternToolSpec] | None = None,
) -> dict[str, Any]:
    """Return an Open-WebUI-compatible tool manifest.

    The manifest lists the 34 ``POST /v1/analyze/<pattern_name>``
    endpoints with their input/output schemas, plus the catalogue
    GET endpoints. Drop the JSON into Open WebUI's "Tools -> Add
    OpenAPI Tool" panel, or point it at ``<api_base_url>/openapi.json``
    directly for the same effect.
    """
    specs = specs or list_pattern_tool_specs()
    tools: list[dict[str, Any]] = []
    for spec in specs:
        tools.append(
            {
                "name": spec.name,
                "description": spec.description,
                "url": f"{api_base_url.rstrip('/')}/v1/analyze/{spec.pattern_name}",
                "method": "POST",
                "input_schema": spec.input_schema,
                "output_schema": spec.output_schema,
            }
        )
    return {
        "name": "vstack",
        "description": (
            "Organizational behavior diagnostics for AI agents. "
            "34 patterns covering individual, team, and "
            "organizational scales."
        ),
        "version": "0.4.0",
        "api_base_url": api_base_url,
        "openapi_url": f"{api_base_url.rstrip('/')}/openapi.json",
        "tools": tools,
    }


__all__ = ["as_openwebui_manifest"]
