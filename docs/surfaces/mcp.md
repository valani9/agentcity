# MCP server — Claude Desktop / Cursor / Cline / Continue / Zed / etc.

vstack ships an MCP (Model Context Protocol) server that exposes all 34 diagnostic patterns as MCP tools, plus per-pattern citations + playbooks + composition manifests as resources, plus invocation templates as prompts.

Local stdio subprocess. Zero hosting cost on the vstack side. Compatible with any MCP-aware client.

## Install + configure

```bash
pip install 'valanistack[anthropic,mcp]'
```

**Claude Desktop** — paste into `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "vstack": {
      "command": "vstack-mcp",
      "args": ["serve"],
      "env": {"ANTHROPIC_API_KEY": "sk-ant-..."}
    }
  }
}
```

**Cursor** — same JSON into `~/.cursor/mcp.json` (or project-level `.cursor/mcp.json`).

**Cline / Continue / Roo / Windsurf / Zed** — open the MCP-servers config in the extension settings and paste the same block.

Or auto-generate the snippet for any platform:

```bash
vstack-mcp config-snippet claude-desktop
vstack-config gen-platform cursor       # extends to 14 platforms
```

## What it exposes

- **34 tools** — one per pattern, named `vstack_<pattern_name>` (e.g. `vstack_lewin`, `vstack_aar`, `vstack_schein_culture`).
- **102 resources** — `vstack://patterns/index` (catalogue), `vstack://patterns/<name>/citations`, `vstack://patterns/<name>/playbooks`, `vstack://patterns/<name>/composition`.
- **35 prompts** — meta `vstack_pick_pattern` router + one `vstack_<name>_invoke` template per pattern.

## Usage

Once configured, ask your client to run any of the 34 patterns by name — _"Use the Schein culture audit on this trace…"_ — and the client picks the matching tool from the catalogue, the server runs the analyzer, and the detection comes back as structured JSON. The server runs as a local stdio subprocess; nothing leaves your machine except whatever LLM calls the analyzer itself makes.

## Utility CLI subcommands

```bash
vstack-mcp serve              # the daemon (your MCP client launches this)
vstack-mcp list-tools         # all 34 tool names + friendly labels
vstack-mcp list-resources     # all 102 resource URIs
vstack-mcp config-snippet <client>  # generate the config JSON for a client
```
