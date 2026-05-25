# Docker (`ghcr.io/valani9/vstack`)

```bash
docker pull ghcr.io/valani9/vstack:latest

# MCP server over stdio (the default CMD):
docker run --rm -i ghcr.io/valani9/vstack:latest

# REST API on port 8000:
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY="sk-ant-..." \
  ghcr.io/valani9/vstack:latest \
  vstack-api serve --host 0.0.0.0 --port 8000

# One-shot CLI invocation:
docker run --rm ghcr.io/valani9/vstack:latest vstack --help
```

Multi-arch (linux/amd64 + linux/arm64). Semver tags: `:0.5.0`, `:0.5`, `:0`, `:latest`. Built and pushed by `.github/workflows/docker.yml` on every `v*.*.*` tag.

## Image contents

- `python:3.13-slim` base
- `valanistack[all]` installed (everything: MCP / REST / Anthropic / OpenAI / Ollama / all framework adapters)
- Non-root user (uid 1000)
- `VSTACK_HOME=/var/lib/vstack` for persistent state
- `tini` as PID 1 for clean signal handling
- Default CMD: `vstack-mcp serve`

Override CMD to pick a different surface:

```bash
docker run --rm ghcr.io/valani9/vstack:latest vstack-config list
docker run --rm ghcr.io/valani9/vstack:latest vstack-analytics summary
docker run --rm ghcr.io/valani9/vstack:latest vstack-upgrade
```

## Persistent state

Mount a volume to `/var/lib/vstack` if you want baselines / learnings / telemetry to survive container restarts:

```bash
docker run --rm -v vstack-data:/var/lib/vstack \
  ghcr.io/valani9/vstack:latest vstack-config list
```

## docker-compose

Generate a paste-ready compose fragment:

```bash
vstack-config gen-platform docker-compose
```
