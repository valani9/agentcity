"""Low-level MCP client wrapper around chrome-devtools-mcp.

Most users won't construct :class:`BrowserSession` directly -- the
``scrape_trace`` / ``screenshot_url`` / ``fill_form`` helpers in
:mod:`_scrape` cover the 90% case. This module exists so power users
(and future skill workflows) can drive arbitrary chrome-devtools-mcp
tools without re-implementing the protocol handshake.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

DEFAULT_DEVTOOLS_COMMAND = ("npx", "chrome-devtools-mcp@latest")
"""Default command for spawning the upstream chrome-devtools-mcp server.

The MCP server ships as an npm package and is the canonical bridge
between any MCP client and Chrome's DevTools Protocol. Users can
override with the ``VSTACK_DEVTOOLS_MCP_COMMAND`` env var (space-
separated) or by passing ``command=...`` to :func:`open_session`.
"""


class BrowserToolError(RuntimeError):
    """Raised when a chrome-devtools-mcp tool call returns an error."""


@dataclass
class BrowserSession:
    """A live MCP session against a chrome-devtools-mcp subprocess.

    Holds the read/write streams plus an ``mcp.ClientSession`` and
    a ready-to-use list of the upstream tools. Use ``call_tool``
    to invoke any one of them.
    """

    session: Any
    """``mcp.client.session.ClientSession`` from the MCP Python SDK."""

    tool_names: tuple[str, ...] = field(default_factory=tuple)
    """Names of every tool the upstream server published, captured at
    initialize time. Useful for tab-completion / discovery."""

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke an upstream tool and unwrap its content.

        Returns the raw ``CallToolResult`` from the MCP SDK; callers
        can introspect ``.content``, ``.structuredContent``, or
        ``.isError`` as needed. Raises :class:`BrowserToolError` if
        the upstream marked the result as an error.
        """
        result = await self.session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            raise BrowserToolError(
                f"chrome-devtools-mcp tool {name!r} returned an error: {_summarize_content(result)}"
            )
        return result

    async def list_tools(self) -> list[Any]:
        """Return the full list of tool descriptors from the server."""
        result = await self.session.list_tools()
        return list(result.tools)


@contextlib.asynccontextmanager
async def open_session(
    *,
    command: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    initialize_timeout: float = 30.0,
) -> AsyncIterator[BrowserSession]:
    """Spawn chrome-devtools-mcp and yield a connected :class:`BrowserSession`.

    Usage::

        async with open_session() as session:
            await session.call_tool("navigate_page", {"url": "https://..."})

    Resolution order for the spawn command:
        1. ``command`` argument
        2. ``VSTACK_DEVTOOLS_MCP_COMMAND`` env var (space-separated)
        3. :data:`DEFAULT_DEVTOOLS_COMMAND`

    The session is cleaned up automatically on context exit.
    """
    # The MCP Python SDK is the same one ``vstack.mcp`` depends on.
    # We import lazily so importing ``vstack.browser`` doesn't drag in
    # the SDK for users who never call ``open_session``.
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        raise ImportError(
            "vstack.browser.open_session requires the 'mcp' Python SDK. "
            "Install with: pip install 'valanistack[browser]'"
        ) from e

    env = env if env is not None else dict(os.environ)
    cmd_tuple = _resolve_command(command, env)
    if not cmd_tuple:
        raise BrowserToolError(
            "No chrome-devtools-mcp command resolved. Set "
            "VSTACK_DEVTOOLS_MCP_COMMAND or pass command=(...) explicitly."
        )

    server_params = StdioServerParameters(
        command=cmd_tuple[0],
        args=list(cmd_tuple[1:]),
        env=env,
        cwd=cwd,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            try:
                await asyncio.wait_for(session.initialize(), timeout=initialize_timeout)
            except asyncio.TimeoutError as e:
                raise BrowserToolError(
                    f"chrome-devtools-mcp did not respond to initialize within "
                    f"{initialize_timeout}s. Is the command path correct? "
                    f"Tried: {' '.join(cmd_tuple)}"
                ) from e

            tools_result = await session.list_tools()
            tool_names = tuple(t.name for t in tools_result.tools)
            logger.debug("Connected to chrome-devtools-mcp; %d tools available", len(tool_names))
            yield BrowserSession(session=session, tool_names=tool_names)


def _resolve_command(
    command: tuple[str, ...] | None,
    env: dict[str, str],
) -> tuple[str, ...]:
    if command:
        return tuple(command)
    raw = env.get("VSTACK_DEVTOOLS_MCP_COMMAND")
    if raw and raw.strip():
        return tuple(raw.split())
    return DEFAULT_DEVTOOLS_COMMAND


def _summarize_content(result: Any) -> str:
    """Best-effort one-line summary of a CallToolResult error body."""
    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text.splitlines()[0][:200])
    if not parts:
        try:
            return json.dumps(getattr(result, "model_dump", lambda: {})())[:200]
        except Exception:
            return "<no content>"
    return " | ".join(parts)


if sys.platform == "win32":  # pragma: no cover - smoke test
    # chrome-devtools-mcp spawns Chrome which behaves differently on
    # Windows; emit a hint at import time so users hit a useful error
    # message rather than an opaque subprocess failure.
    logger.info(
        "vstack.browser: chrome-devtools-mcp on Windows requires Chrome "
        "installed at the default path. See chrome-devtools-mcp docs."
    )
