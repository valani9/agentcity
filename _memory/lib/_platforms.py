"""Per-platform config snippets for non-MCP and edge-case AI clients.

The MCP server (``vstack-mcp serve``) covers Claude Desktop, Cursor,
Cline, Continue.dev, Roo Code, Windsurf, JetBrains AI Assistant, and
anything else that speaks Model Context Protocol -- all those just
need ``vstack-mcp config-snippet <client>`` from the MCP CLI.

This module fills the remaining surface: clients with their own tool
specs (Aider hooks, Goose extensions, OpenAI Codex CLI tool config,
Cursor ``.cursorrules``, Kiro spec files, OpenClaw manifests, etc.).
Each generator returns either a JSON / YAML / plain-text body and
the recommended destination filename; the CLI writes it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PlatformSnippet:
    """One generator output."""

    platform: str
    """Platform identifier (matches the CLI ``--platform`` value)."""

    body: str
    """Ready-to-paste content. Already serialized as JSON/YAML/text."""

    suggested_path: str
    """Where the user should drop this file. Tilde-expanded paths use
    the home directory; relative paths are relative to the user's
    project root."""

    notes: str
    """One-paragraph guidance shown to the user after the body."""


def _claude_desktop() -> PlatformSnippet:
    return PlatformSnippet(
        platform="claude-desktop",
        body=json.dumps(
            {
                "mcpServers": {
                    "vstack": {
                        "command": "vstack-mcp",
                        "args": ["serve"],
                        "env": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path=(
            "~/Library/Application Support/Claude/claude_desktop_config.json "
            "(macOS) or %APPDATA%\\Claude\\claude_desktop_config.json (Windows)"
        ),
        notes=(
            "Set ANTHROPIC_API_KEY (or OPENAI_API_KEY / OLLAMA_HOST) in the "
            "env block. Restart Claude Desktop after saving."
        ),
    )


def _cursor() -> PlatformSnippet:
    return PlatformSnippet(
        platform="cursor",
        body=json.dumps(
            {
                "mcpServers": {
                    "vstack": {
                        "command": "vstack-mcp",
                        "args": ["serve"],
                        "env": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path="~/.cursor/mcp.json (or project-level .cursor/mcp.json)",
        notes=(
            "Cursor reads MCP servers from this file at startup. Set "
            "ANTHROPIC_API_KEY in the env block."
        ),
    )


def _cline() -> PlatformSnippet:
    return PlatformSnippet(
        platform="cline",
        body=json.dumps(
            {
                "mcpServers": {
                    "vstack": {
                        "command": "vstack-mcp",
                        "args": ["serve"],
                        "env": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path=("VS Code: Cline extension settings -> MCP Servers -> Edit Configuration"),
        notes="Paste the JSON above into Cline's MCP-servers panel.",
    )


def _continue() -> PlatformSnippet:
    return PlatformSnippet(
        platform="continue",
        body=json.dumps(
            {
                "experimental": {
                    "modelContextProtocolServers": [
                        {
                            "transport": {
                                "type": "stdio",
                                "command": "vstack-mcp",
                                "args": ["serve"],
                            }
                        }
                    ]
                }
            },
            indent=2,
        ),
        suggested_path="~/.continue/config.json",
        notes=(
            "Merge this 'experimental.modelContextProtocolServers' "
            "key into your existing Continue config."
        ),
    )


def _roo_code() -> PlatformSnippet:
    return PlatformSnippet(
        platform="roo-code",
        body=json.dumps(
            {
                "mcpServers": {
                    "vstack": {
                        "command": "vstack-mcp",
                        "args": ["serve"],
                        "env": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path="VS Code: Roo Code extension -> MCP Servers config",
        notes="Identical shape to Cline; paste into the Roo MCP-servers panel.",
    )


def _windsurf() -> PlatformSnippet:
    return PlatformSnippet(
        platform="windsurf",
        body=json.dumps(
            {
                "mcpServers": {
                    "vstack": {
                        "command": "vstack-mcp",
                        "args": ["serve"],
                        "env": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path="~/.codeium/windsurf/mcp_config.json",
        notes="Restart Windsurf after saving.",
    )


def _zed() -> PlatformSnippet:
    return PlatformSnippet(
        platform="zed",
        body=json.dumps(
            {
                "context_servers": {
                    "vstack": {
                        "command": {
                            "path": "vstack-mcp",
                            "args": ["serve"],
                            "env": {},
                        },
                        "settings": {},
                    }
                }
            },
            indent=2,
        ),
        suggested_path="~/.config/zed/settings.json (under context_servers)",
        notes="Zed restarts MCP servers on config change; no manual restart needed.",
    )


def _aider() -> PlatformSnippet:
    return PlatformSnippet(
        platform="aider",
        body=(
            "# Aider hook -- run vstack-mcp tools alongside Aider.\n"
            "# Aider doesn't speak MCP natively yet; bridge via vstack-api.\n"
            "# Start the REST server in another terminal:\n"
            "#     vstack-api serve\n"
            "# Then add this snippet to .aider.conf.yml:\n"
            "external_tools:\n"
            "  vstack:\n"
            "    base_url: http://127.0.0.1:8000\n"
            "    list_endpoint: /v1/patterns\n"
            "    invoke_endpoint_template: /v1/analyze/{tool}\n"
        ),
        suggested_path=".aider.conf.yml in your project root",
        notes=(
            "Aider's MCP support is in flux; this bridges via the "
            "vstack REST API which is always available."
        ),
    )


def _goose() -> PlatformSnippet:
    return PlatformSnippet(
        platform="goose",
        body=(
            "# Goose extension config -- adds vstack-mcp as a stdio extension.\n"
            "extensions:\n"
            "  vstack:\n"
            "    type: stdio\n"
            "    cmd: vstack-mcp\n"
            "    args:\n"
            "      - serve\n"
            "    enabled: true\n"
            "    timeout: 60\n"
        ),
        suggested_path="~/.config/goose/config.yaml",
        notes="Goose picks up stdio extensions on startup.",
    )


def _kiro() -> PlatformSnippet:
    return PlatformSnippet(
        platform="kiro",
        body=(
            "# Kiro spec for vstack.\n"
            "# Wraps the MCP server so Kiro's spec runner can call any\n"
            "# of the 34 vstack patterns.\n"
            "name: vstack\n"
            "description: Organizational behavior diagnostics for AI agents.\n"
            "version: 0.4.0\n"
            "tools:\n"
            "  source: mcp\n"
            "  command: vstack-mcp\n"
            "  args: [serve]\n"
        ),
        suggested_path=".kiro/specs/vstack.yaml (in your project)",
        notes="Kiro will spawn vstack-mcp as a child process on first use.",
    )


def _openclaw() -> PlatformSnippet:
    return PlatformSnippet(
        platform="openclaw",
        body=json.dumps(
            {
                "name": "vstack",
                "type": "mcp_stdio",
                "command": "vstack-mcp",
                "args": ["serve"],
                "description": (
                    "Organizational behavior diagnostics for AI agents. "
                    "34 patterns spanning individual, team, and "
                    "organizational scales."
                ),
            },
            indent=2,
        ),
        suggested_path="~/.openclaw/extensions/vstack.json",
        notes="OpenClaw treats vstack-mcp like any other MCP-stdio tool.",
    )


def _codex_cli() -> PlatformSnippet:
    return PlatformSnippet(
        platform="codex-cli",
        body=json.dumps(
            {
                "mcp_servers": {
                    "vstack": {
                        "transport": "stdio",
                        "command": "vstack-mcp",
                        "args": ["serve"],
                    }
                }
            },
            indent=2,
        ),
        suggested_path="~/.codex/config.toml or codex.json",
        notes=(
            "Codex CLI's exact config key has changed across releases; "
            "if 'mcp_servers' is rejected, try 'modelContextProtocolServers'."
        ),
    )


def _opencode() -> PlatformSnippet:
    return PlatformSnippet(
        platform="opencode",
        body=json.dumps(
            {
                "tools": {
                    "vstack": {
                        "type": "mcp",
                        "command": "vstack-mcp",
                        "args": ["serve"],
                    }
                }
            },
            indent=2,
        ),
        suggested_path="opencode.json in your project root",
        notes="OpenCode picks up MCP tool specs from this file on launch.",
    )


def _docker_compose() -> PlatformSnippet:
    return PlatformSnippet(
        platform="docker-compose",
        body=(
            "# docker-compose.yml fragment for vstack-api on port 8000.\n"
            "version: '3.9'\n"
            "services:\n"
            "  vstack:\n"
            "    image: ghcr.io/valani9/vstack:0.4.0\n"
            "    command: vstack-api serve --host 0.0.0.0 --port 8000\n"
            "    ports:\n"
            "      - '8000:8000'\n"
            "    environment:\n"
            "      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}\n"
            "      VSTACK_HOME: /var/lib/vstack\n"
            "    volumes:\n"
            "      - vstack-data:/var/lib/vstack\n"
            "    restart: unless-stopped\n"
            "volumes:\n"
            "  vstack-data: {}\n"
        ),
        suggested_path="docker-compose.yml in your project root",
        notes=(
            "The mounted volume keeps ~/.vstack/ baselines + telemetry across container restarts."
        ),
    )


GENERATORS: dict[str, Callable[[], PlatformSnippet]] = {
    "claude-desktop": _claude_desktop,
    "cursor": _cursor,
    "cline": _cline,
    "continue": _continue,
    "roo-code": _roo_code,
    "windsurf": _windsurf,
    "zed": _zed,
    "aider": _aider,
    "goose": _goose,
    "kiro": _kiro,
    "openclaw": _openclaw,
    "codex-cli": _codex_cli,
    "opencode": _opencode,
    "docker-compose": _docker_compose,
}


def list_platforms() -> list[str]:
    return sorted(GENERATORS)


def generate(platform: str) -> PlatformSnippet:
    if platform not in GENERATORS:
        raise KeyError(
            f"Unknown platform {platform!r}. Run 'vstack-config gen-platform "
            f"--list' to see valid options."
        )
    return GENERATORS[platform]()
