# CLI reference

vstack ships 41 CLIs total: 7 top-level surface CLIs + 34 per-pattern CLIs.

## Top-level surfaces

| Command | Purpose |
|---|---|
| `vstack` | Foundational AAR generator (the `vstack.aar` CLI). |
| `vstack-mcp` | MCP stdio server. Subcommands: `serve`, `list-tools`, `list-resources`, `config-snippet <client>`. |
| `vstack-api` | FastAPI REST server. Subcommands: `serve`, `routes`, `openapi`. |
| `vstack-config` | `~/.vstack/` preferences. Subcommands: `get`, `set`, `list`, `unset`, `path`, `keys`, `install-skills`, `gen-platform`. |
| `vstack-upgrade` | PyPI version check + migration notes. |
| `vstack-learn` | Learning store. Subcommands: `record`, `recall`, `outcome`, `outcomes`, `path`, `clear`. |
| `vstack-analytics` | Telemetry aggregator. Subcommands: `summary`, `top-costs`, `cost`, `raw`, `path`. |
| `vstack-bench` | Benchmark + comparative-eval harness. Subcommands: `list`, `run`, `compare`. |
| `vstack-gbrain` | gbrain integration (optional). Subcommands: `status`, `sync`, `search`, `corpus`. |
| `vstack-browser` | Chrome DevTools MCP wrapper. Subcommands: `scrape`, `screenshot`, `tools`. |

## Per-pattern CLIs

See [Python imports + 34 CLIs](../surfaces/python-and-clis.md) for the full list.

Every per-pattern CLI has the same 7 subcommands: `analyze`, `batch`, `replay`, `validate`, `schema`, `playbooks`, `compose`.
