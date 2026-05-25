"""High-level helpers built on top of :class:`BrowserSession`.

These wrap the most common chrome-devtools-mcp tool sequences so a
caller doesn't have to think about ``navigate_page`` + ``wait_for`` +
``list_network_requests`` + ``get_network_request`` every time they
want to scrape a trace from an observability dashboard.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ._client import BrowserSession, BrowserToolError

logger = logging.getLogger(__name__)


# Known agent-observability dashboards we have first-class scrape
# recipes for. Each entry maps a domain substring to:
#   * the URL pattern (regex) that the dashboard uses for trace pages
#   * the network-request URL substring that returns the structured
#     trace payload (so we can isolate it from page noise)
#   * a hint about which vstack pattern's input model it best maps to
#
# The recipes are best-effort -- the upstream dashboards change their
# JSON shapes every few months. When a recipe fails, the scrape
# helpers fall back to "page snapshot" mode and let the caller decide
# how to extract the trace.
KNOWN_DASHBOARDS: dict[str, dict[str, Any]] = {
    "smith.langchain.com": {
        "trace_path_pattern": r"/o/[^/]+/projects/[^/]+/r/[a-f0-9-]+",
        "network_filter": "/api/v1/runs/",
        "default_target_pattern": "aar",
        "vendor_hint": "LangSmith",
    },
    "app.phoenix.arize.com": {
        "trace_path_pattern": r"/projects/[^/]+/traces/[a-f0-9-]+",
        "network_filter": "/v1/traces",
        "default_target_pattern": "aar",
        "vendor_hint": "Arize Phoenix (cloud)",
    },
    "phoenix.arize.com": {
        "trace_path_pattern": r"/traces/[a-f0-9-]+",
        "network_filter": "/v1/traces",
        "default_target_pattern": "aar",
        "vendor_hint": "Arize Phoenix",
    },
    "us.helicone.ai": {
        "trace_path_pattern": r"/requests/[a-f0-9-]+",
        "network_filter": "/api/v1/request",
        "default_target_pattern": "lewin",
        "vendor_hint": "Helicone",
    },
    "app.langfuse.com": {
        "trace_path_pattern": r"/project/[^/]+/traces/[a-f0-9-]+",
        "network_filter": "/api/public/traces/",
        "default_target_pattern": "aar",
        "vendor_hint": "Langfuse",
    },
}


@dataclass(frozen=True)
class ScrapedTrace:
    """Structured result of a successful trace scrape.

    The ``raw_payload`` is the verbatim JSON the dashboard returned;
    callers are expected to map it onto the vstack pattern's input
    model themselves (or use an upstream MCP tool / LLM to translate).
    """

    url: str
    """The dashboard URL that was scraped."""

    vendor: str
    """One of LangSmith / Phoenix / Helicone / Langfuse / unknown."""

    raw_payload: Any
    """Parsed JSON body of the dashboard's trace API response."""

    suggested_pattern: str
    """vstack pattern import name we think this trace best maps to."""

    captured_network_requests: list[dict[str, Any]] = field(default_factory=list)
    """Every network request the page made during scraping, summarized
    as ``[{url, status, size, ...}, ...]``. Useful for debugging
    failed scrapes."""


async def scrape_trace(
    url: str,
    *,
    session: BrowserSession,
    wait_for_selector: str | None = None,
    timeout_seconds: float = 30.0,
) -> ScrapedTrace:
    """Navigate to a dashboard URL and return the structured trace.

    Tries to look the URL up in :data:`KNOWN_DASHBOARDS`; if found,
    filters the network requests to the one that carries the trace
    payload and parses it as JSON. If the URL isn't recognized, falls
    back to capturing all network requests and returning the most
    likely candidate (heuristic: largest JSON response).

    Parameters
    ----------
    url:
        The dashboard URL to scrape.
    session:
        An open :class:`BrowserSession`.
    wait_for_selector:
        Optional CSS selector to wait for before snapshotting (e.g.
        a "trace loaded" indicator the dashboard renders).
    timeout_seconds:
        How long to wait for the page + network to settle.
    """
    recipe = _recipe_for(url)
    vendor = recipe.get("vendor_hint", "unknown")

    await session.call_tool("navigate_page", {"url": url})
    if wait_for_selector:
        try:
            await session.call_tool(
                "wait_for",
                {"selector": wait_for_selector, "timeout": int(timeout_seconds * 1000)},
            )
        except BrowserToolError:
            logger.debug("wait_for selector failed; continuing with raw snapshot")

    requests_result = await session.call_tool("list_network_requests", {})
    captured = _extract_requests(requests_result)

    network_filter = recipe.get("network_filter")
    candidate = _pick_trace_request(captured, network_filter)
    if candidate is None:
        raise BrowserToolError(
            f"Could not identify the trace payload network request on {url}. "
            f"Try passing wait_for_selector= to give the page more time to "
            f"finish XHR loads, or fall back to manual extraction via "
            f"session.call_tool('get_network_request', ...)."
        )

    body_result = await session.call_tool("get_network_request", {"requestId": candidate["id"]})
    payload = _parse_body(body_result)

    suggested = str(recipe.get("default_target_pattern") or _guess_pattern_for(payload) or "aar")

    return ScrapedTrace(
        url=url,
        vendor=vendor,
        raw_payload=payload,
        suggested_pattern=suggested,
        captured_network_requests=captured,
    )


async def screenshot_url(
    url: str,
    *,
    session: BrowserSession,
    full_page: bool = True,
    wait_for_selector: str | None = None,
) -> bytes:
    """Take a screenshot of an arbitrary URL.

    Returns the screenshot as raw PNG bytes (decoded from the
    upstream's base64 envelope). Use for sharing detection reports in
    incident channels or for documenting evidence in an AAR.
    """
    await session.call_tool("navigate_page", {"url": url})
    if wait_for_selector:
        with _suppress_browser_error():
            await session.call_tool("wait_for", {"selector": wait_for_selector})
    result = await session.call_tool("take_screenshot", {"fullPage": full_page, "format": "png"})
    return _decode_image(result)


async def fill_form(
    url: str,
    *,
    session: BrowserSession,
    fields: dict[str, str],
    submit_selector: str | None = None,
) -> dict[str, Any]:
    """Open ``url``, populate fields, and optionally click submit.

    ``fields`` maps a CSS selector to the value to type. Returns a
    summary dict with the captured network responses after submit, so
    the caller can pull out an updated trace ID or status.
    """
    await session.call_tool("navigate_page", {"url": url})
    for selector, value in fields.items():
        await session.call_tool("fill", {"selector": selector, "value": value})
    if submit_selector:
        await session.call_tool("click", {"selector": submit_selector})

    requests_result = await session.call_tool("list_network_requests", {})
    return {
        "captured_network_requests": _extract_requests(requests_result),
        "filled_fields": list(fields),
    }


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _recipe_for(url: str) -> dict[str, Any]:
    for domain, recipe in KNOWN_DASHBOARDS.items():
        if domain in url:
            return recipe
    return {"vendor_hint": "unknown"}


def _extract_requests(result: Any) -> list[dict[str, Any]]:
    """Pull a flat list of {id, url, status, size, ...} from the upstream result."""
    rows: list[dict[str, Any]] = []
    payload = _result_structured(result)
    if isinstance(payload, dict):
        requests = payload.get("requests") or payload.get("data") or []
    elif isinstance(payload, list):
        requests = payload
    else:
        requests = []
    for entry in requests:
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "id": entry.get("requestId") or entry.get("id"),
                "url": entry.get("url"),
                "status": entry.get("status") or entry.get("statusCode"),
                "size": entry.get("size") or entry.get("contentLength") or 0,
                "method": entry.get("method") or "GET",
                "type": entry.get("type") or entry.get("resourceType"),
            }
        )
    return rows


def _pick_trace_request(
    captured: list[dict[str, Any]], network_filter: str | None
) -> dict[str, Any] | None:
    """Pick the most-likely trace-payload request from a captured list."""
    if not captured:
        return None
    if network_filter:
        for entry in captured:
            url = entry.get("url") or ""
            if network_filter in url and (entry.get("status") or 0) < 400:
                return entry
    # Fall back to "largest XHR JSON response with status < 400" heuristic.
    candidates = [
        e
        for e in captured
        if (e.get("status") or 0) < 400 and (e.get("type") in (None, "xhr", "fetch", "Document"))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: int(e.get("size") or 0), reverse=True)
    return candidates[0]


def _result_structured(result: Any) -> Any:
    """Extract structured content from a CallToolResult."""
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None


def _parse_body(result: Any) -> Any:
    """Parse the body of a ``get_network_request`` response."""
    payload = _result_structured(result) or {}
    if isinstance(payload, dict):
        body = payload.get("body") or payload.get("response_body")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
        if body is not None:
            return body
        return payload
    return payload


def _guess_pattern_for(payload: Any) -> str | None:
    """Heuristic: which vstack pattern does this payload look like?"""
    if not isinstance(payload, dict):
        return None
    keys = {k.lower() for k in payload.keys() if isinstance(k, str)}
    if "steps" in keys and ("outcome" in keys or "goal" in keys):
        return "aar"
    if "messages" in keys and "agents" in keys:
        return "lencioni"
    if "agents" in keys and "incoming_request_rate" in keys:
        return "span_of_control"
    if "observations" in keys:
        return "schein_culture"
    return None


def _decode_image(result: Any) -> bytes:
    """Decode a screenshot tool result's base64 payload."""
    import base64

    structured = _result_structured(result)
    if isinstance(structured, dict):
        data = structured.get("data") or structured.get("image") or ""
        if isinstance(data, str) and data:
            return base64.b64decode(data)
    content = getattr(result, "content", None) or []
    for item in content:
        # The MCP SDK ships ImageContent with .data already as base64.
        data = getattr(item, "data", None)
        if isinstance(data, str) and data:
            return base64.b64decode(data)
    raise BrowserToolError("take_screenshot returned no image data.")


def _suppress_browser_error() -> Any:
    """Local context manager that swallows :class:`BrowserToolError`.

    Defined as a function (not a decorator) so :func:`screenshot_url`
    can use it in a single ``with`` and still surface the underlying
    error through the ``raise from`` chain if something downstream
    cares to inspect ``__context__``.
    """
    import contextlib

    return contextlib.suppress(BrowserToolError)
