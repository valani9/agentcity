"""``vstack-mcp`` CLI — boots the stdio MCP server.

Most users never invoke this directly; their MCP client (Claude
Desktop, Cursor, Cline, etc.) spawns it as a subprocess based on the
config snippet documented in the README.

The CLI also supports a couple of utility subcommands for setup and
debugging:

* ``vstack-mcp serve`` — start the stdio server (the default)
* ``vstack-mcp list-tools`` — print the 34 tool names for sanity check
* ``vstack-mcp list-resources`` — print the resource URI catalogue
* ``vstack-mcp config-snippet`` — print a ready-to-paste config block
  for a target MCP client
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Sequence

from ._registry import PATTERNS, tool_name_for
from ._resources import list_resource_uris


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-mcp",
        description=(
            "vstack MCP server. Exposes 34 organizational-behavior "
            "diagnostic patterns as MCP tools over stdio."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "serve",
        help="Run the stdio MCP server. This is the default.",
    )

    sub.add_parser(
        "list-tools",
        help="Print the registered MCP tool names.",
    )

    sub.add_parser(
        "list-resources",
        help="Print the registered MCP resource URIs.",
    )

    snippet = sub.add_parser(
        "config-snippet",
        help="Print a ready-to-paste config snippet for an MCP client.",
    )
    snippet.add_argument(
        "client",
        nargs="?",
        default="claude-desktop",
        choices=("claude-desktop", "cursor", "cline", "continue", "generic"),
        help="Target client (default: claude-desktop).",
    )

    args = parser.parse_args(argv)
    cmd = args.command or "serve"

    if cmd == "serve":
        return _run_serve()
    if cmd == "list-tools":
        return _run_list_tools()
    if cmd == "list-resources":
        return _run_list_resources()
    if cmd == "config-snippet":
        return _run_config_snippet(args.client)
    parser.error(f"Unknown command: {cmd}")
    return 2


def _run_serve() -> int:
    from ._server import run_stdio

    try:
        asyncio.run(run_stdio())
    except KeyboardInterrupt:
        return 0
    return 0


def _run_list_tools() -> int:
    for p in PATTERNS:
        print(f"{tool_name_for(p):<28} {p.friendly}")
    print(f"\nTotal: {len(PATTERNS)} tools")
    return 0


def _run_list_resources() -> int:
    for uri, name, _desc, mime in list_resource_uris():
        print(f"{uri:<55} ({mime}) {name}")
    return 0


def _run_config_snippet(client: str) -> int:
    snippet = _config_snippet_for(client)
    print(snippet)
    return 0


def _config_snippet_for(client: str) -> str:
    if client in ("claude-desktop", "cursor", "cline", "continue", "generic"):
        # All four clients use the same MCP-server config shape; only
        # the surrounding file location differs (handled in the README).
        config = {
            "mcpServers": {
                "vstack": {
                    "command": "vstack-mcp",
                    "args": ["serve"],
                    "env": {
                        # Replace with your real Anthropic API key
                        # (or set ANTHROPIC_API_KEY in your shell).
                        # "ANTHROPIC_API_KEY": "sk-ant-..."
                    },
                }
            }
        }
        header = {
            "claude-desktop": (
                "# Paste into ~/Library/Application Support/Claude/"
                "claude_desktop_config.json (macOS) or "
                "%APPDATA%\\Claude\\claude_desktop_config.json (Windows)."
            ),
            "cursor": ("# Paste into ~/.cursor/mcp.json or the project-level .cursor/mcp.json."),
            "cline": (
                "# Paste into the Cline VS Code extension settings "
                "(Cline -> Settings -> MCP Servers -> Edit "
                "Configuration)."
            ),
            "continue": (
                "# Paste into ~/.continue/config.json under "
                "experimental.modelContextProtocolServers."
            ),
            "generic": "# Generic MCP-server config block.",
        }[client]
        return f"{header}\n{json.dumps(config, indent=2)}"
    return json.dumps({"mcpServers": {}}, indent=2)


if __name__ == "__main__":
    sys.exit(main())
