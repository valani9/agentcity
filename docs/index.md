# vstack

**Organizational behavior, practiced on AI agents.**

vstack is a curated library of 34 diagnostic patterns for AI agents and multi-agent systems, anchored in named organizational-behavior literature — Wharton's After-Action Review, Lencioni's Five Dysfunctions, Edmondson's Psychological Safety, Frei & Morriss's Trust Triangle, Schein's culture iceberg, Galbraith-Mintzberg structural fit — translated into runnable Python with public benchmarks and Substack-ready essays.

Most agent-observability tools capture *what happened* (traces). Most incident-response tools handle *single events* (a postmortem per alert). vstack ships a curated library of *organizational practices* — the same frameworks human teams use to learn, debate, escalate, and improve — implemented as patterns AI agents can run themselves.

Where the existing agent ecosystem treats failures as bugs to debug, vstack treats them as learning events to organize around.

## Twelve ways to use it

1. **Python imports** — `from vstack.lewin import LewinAttributionDetector`
2. **34 per-pattern CLIs** — `vstack-lewin analyze --trace trace.json`
3. **MCP server** — `vstack-mcp serve` for Claude Desktop, Cursor, Cline, Continue, Zed, etc.
4. **REST API** — `vstack-api serve` (FastAPI on 127.0.0.1:8000) with auth, rate limiting, and observability baked in
5. **Docker** — `docker run ghcr.io/valani9/vstack:0.7.0`
6. **Claude Code skills** — 7 task-shaped `SKILL.md` files: `/vstack-aar`, `/vstack-audit-crew`, `/vstack-post-incident`, and more
7. **Framework adapters** — LangChain, LangGraph, CrewAI, AutoGen, LlamaIndex, Pydantic AI
8. **OpenAI Assistants + Anthropic Messages tool JSON** — pure JSON, no install on the consumer side
9. **Open WebUI plugin** — drop-in tool manifest pointing at a running `vstack-api`
10. **Tier B platform generators** — Aider, Goose, Kiro, OpenClaw, Codex CLI, OpenCode (`vstack-config gen-platform`)
11. **Browser dev tooling** — `vstack-browser` scrapes agent traces from LangSmith / Phoenix / Helicone / Langfuse / Arize
12. **First-run smoke (`vstack-hello`)** — 30-second end-to-end demo with graceful no-key fallback

## Three things to read next

- [Quick start](quickstart.md) — install + first detection in 60 seconds.
- [The 5-layer pattern shape](concepts/pattern-shape.md) — how every pattern is documented + implemented + demoed + benchmarked + written up.
- [Composition runbook](concepts/composition.md) — how the 34 patterns chain into real diagnostic workflows.

## Quick install

```bash
pip install valanistack                # core library + 34 CLIs
pip install 'valanistack[anthropic]'   # + Anthropic client
pip install 'valanistack[mcp]'         # + MCP server
pip install 'valanistack[api]'         # + FastAPI REST surface
pip install 'valanistack[adapters]'    # + LangChain/LangGraph/CrewAI/LlamaIndex/Pydantic AI
pip install 'valanistack[all]'         # everything
```

Python 3.11+ required. MIT-licensed. Sole author: Ilhan Valani ([valani@bu.edu](mailto:valani@bu.edu)).
