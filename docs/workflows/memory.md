# Persistent state — `~/.vstack/`

vstack stores calibration baselines, session history, telemetry, learning records, and user preferences under `~/.vstack/`. Override the home directory with `VSTACK_HOME`.

## Layout

```
~/.vstack/
├── baselines/             # per-pattern calibration JSON
├── sessions/              # session-history JSONL (reserved)
├── analytics/             # opt-in telemetry sink output
│   └── telemetry.jsonl    # one line per LLM call
├── learnings.jsonl        # learning-store records
└── config.json            # user preferences
```

## `vstack-config` CLI

```bash
vstack-config list                       # current preferences
vstack-config get default_mode           # one key
vstack-config set default_mode forensic  # write a key (JSON-coerced)
vstack-config keys                       # documented preferences + defaults
vstack-config unset <key>                # delete a key
vstack-config path baselines             # print the baselines dir
vstack-config install-skills             # copy Claude Code skills to ~/.claude/
vstack-config gen-platform cursor        # paste-ready config for non-MCP-default clients
```

## Documented preference keys

| Key | Default | Purpose |
|---|---|---|
| `default_mode` | `standard` | Default analyzer mode |
| `default_model` | `claude-sonnet-4-6` | Default LLM model |
| `telemetry` | `off` | Telemetry sink (`off`/`memory`/`file`) |
| `log_level` | `WARNING` | Python logging level |
| `preferred_llm` | `auto` | MCP/REST LLM provider preference |
| `api_host` | `127.0.0.1` | `vstack-api serve` bind host |
| `api_port` | `8000` | `vstack-api serve` bind port |
| `skills_install_path` | `~/.claude/skills/vstack` | Where `install-skills` copies the skill set |

Unknown keys are stored verbatim — forward-compatible for plugins.
