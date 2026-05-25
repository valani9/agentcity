"""vstack.mcp -- Model Context Protocol server exposing all 34
organizational-behavior diagnostic patterns as MCP tools, plus
per-pattern citations / playbooks / composition resources, plus
invocation prompt templates.

Designed to run as a local stdio subprocess of any MCP-compatible
client (Claude Desktop, Cursor, Cline, Continue, etc.). Zero hosting
cost on the vstack side -- the user installs ``valanistack``,
configures their client with a six-line JSON snippet, and the MCP
client spawns ``vstack-mcp`` on demand.

Quick start
-----------

Install:

    pip install valanistack[anthropic,mcp]

Add to ``~/Library/Application Support/Claude/claude_desktop_config.json``
(macOS) or the equivalent for your client:

    {
      "mcpServers": {
        "vstack": {
          "command": "vstack-mcp",
          "args": ["serve"],
          "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}
        }
      }
    }

Then in Claude Desktop, ask for any of the 34 diagnostics by name:

    "Use the Schein culture audit on this agent crew trace..."

The MCP client picks ``vstack_schein_culture`` from the tool list,
fills the input schema from the description, and surfaces the
detection back as structured JSON.

Programmatic surface
--------------------

* :data:`PATTERNS`, :data:`PATTERNS_BY_NAME` -- the registry tuple
* :class:`PatternEntry` -- one registry entry
* :func:`tool_name_for` -- registry entry -> MCP tool name
* :func:`build_server` -- construct the :class:`mcp.server.lowlevel.Server`
* :func:`run_stdio` -- entry point for the CLI
* :func:`resolve_llm_client` -- LLM-client factory used by the server
* :func:`render_prompt` -- render a prompt template to plain text
* :func:`read_resource` -- read a ``vstack://`` resource URI

CLI
---

    vstack-mcp serve
    vstack-mcp list-tools
    vstack-mcp list-resources
    vstack-mcp config-snippet claude-desktop
"""

from ._client import LLMResolutionError, default_model_for, resolve_llm_client
from ._prompts import (
    PICK_PATTERN_PROMPT,
    PromptArgSpec,
    PromptSpec,
    list_prompts,
    render_prompt,
)
from ._registry import (
    PATTERNS,
    PATTERNS_BY_NAME,
    PatternEntry,
    ResolvedPattern,
    tool_name_for,
)
from ._resources import INDEX_URI, list_resource_uris, read_resource
from ._server import (
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    SERVER_VERSION,
    build_server,
    run_stdio,
)

__all__ = [
    # Registry
    "PATTERNS",
    "PATTERNS_BY_NAME",
    "PatternEntry",
    "ResolvedPattern",
    "tool_name_for",
    # Server lifecycle
    "build_server",
    "run_stdio",
    "SERVER_NAME",
    "SERVER_VERSION",
    "SERVER_INSTRUCTIONS",
    # LLM client resolution
    "resolve_llm_client",
    "default_model_for",
    "LLMResolutionError",
    # Resources
    "list_resource_uris",
    "read_resource",
    "INDEX_URI",
    # Prompts
    "list_prompts",
    "render_prompt",
    "PromptSpec",
    "PromptArgSpec",
    "PICK_PATTERN_PROMPT",
]

__version__ = "0.2.0"
