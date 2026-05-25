# Config keys

`vstack-config keys` prints these at runtime; this page mirrors them with rationale.

| Key | Default | Purpose |
|---|---|---|
| `default_mode` | `standard` | Default analyzer mode. Cheapest signal during day-to-day use. |
| `default_model` | `claude-sonnet-4-6` | Default LLM model passed to analyzers. |
| `telemetry` | `off` | Telemetry sink. `off` disables; `memory` uses `InMemoryTelemetrySink`; `file` writes JSONL to `~/.vstack/analytics/telemetry.jsonl`. |
| `log_level` | `WARNING` | Default Python logging level for vstack CLIs. |
| `preferred_llm` | `auto` | Preferred LLM provider for `vstack-mcp` / `vstack-api` (`'anthropic'` / `'openai'` / `'ollama'` / `'auto'`). |
| `api_host` | `127.0.0.1` | Default bind host for `vstack-api serve`. |
| `api_port` | `8000` | Default bind port for `vstack-api serve`. |
| `skills_install_path` | `~/.claude/skills/vstack` | Where `vstack-config install-skills` copies the skill set. |

Unknown keys are stored verbatim — plugins can piggyback. Strict validation will land alongside the first plugin spec.

## Env vars

| Variable | Purpose |
|---|---|
| `VSTACK_HOME` | Override `~/.vstack/`. |
| `VSTACK_MCP_LLM` | `anthropic` / `openai` / `ollama` / `stub` — forces the MCP server's LLM client choice. |
| `VSTACK_MCP_LOG_LEVEL` | Logging level for the MCP server (defaults to `WARNING` — stdio mode requires quiet stdout). |
| `VSTACK_DEVTOOLS_MCP_COMMAND` | Override the `chrome-devtools-mcp` spawn command (default: `npx chrome-devtools-mcp@latest`). |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST` | Standard provider credentials. |
