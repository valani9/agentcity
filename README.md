# vstack

[![CI](https://github.com/valani9/vstack/actions/workflows/ci.yml/badge.svg)](https://github.com/valani9/vstack/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/valanistack.svg)](https://pypi.org/project/valanistack/)
[![Python versions](https://img.shields.io/pypi/pyversions/valanistack.svg)](https://pypi.org/project/valanistack/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Patterns shipped](https://img.shields.io/badge/patterns-34%2F34-brightgreen.svg)](PATTERNS.md)

**Organizational behavior, practiced on AI agents.**

vstack is a curated library of design patterns for AI agents and multi-agent systems, anchored in named organizational-behavior (OB) literature — Wharton's After-Action Review, Lencioni's Five Dysfunctions, Edmondson's Psychological Safety, Frei & Morriss's Trust Triangle, Stone & Heen's "Thanks for the Feedback" — translated into runnable code, public benchmarks, and Substack-ready essays.

Most agent observability tools capture *what happened* (traces). Most incident-response tools handle *single events* (a postmortem per alert). vstack ships a curated library of *organizational practices* — the same frameworks human teams use to learn, debate, escalate, and improve — implemented as patterns AI agents can run themselves.

Where the existing agent ecosystem treats failures as bugs to debug, vstack treats them as learning events to organize around.

---

## Disambiguation

You may have seen ["vstack: Constitutional Governance for Autonomous Agent Economies via Separation of Power"](https://arxiv.org/abs/2604.07007) (NetX Foundation, April 2026). That paper is about blockchain-based governance for agent economies. **This is a different project.** vstack-the-library is an open-source pattern library for applying organizational-behavior frameworks to AI agent design — no blockchain, no governance protocols, no agent economies. Same name, different domain.

---

## What's in here

Three modules mirror the standard organizational-behavior curriculum:

- **Module 1 — Individual Agent Patterns** — Lewin's B=f(I,E), Goleman EI domains, Big Five/HEXACO personality, Vroom expectancy, 4 motivation traps, Yerkes-Dodson optimal workload, Johari Window self-audit.
- **Module 2 — Multi-Agent Team Patterns** — Lencioni Five Dysfunctions diagnostic, Frei & Morriss Trust Triangle audit, Edmondson Psychological Safety score, AAR generator, GRPI working agreement, Thomas-Kilmann conflict-style router, social-loafing and process-loss detectors.
- **Module 3 — System / Organizational Patterns** — Schein's Iceberg culture audit, span-of-control calculator, centralization/decentralization trade-off analyzer.

A full index is in [PATTERNS.md](PATTERNS.md). Academic citations are in [CITATIONS.md](CITATIONS.md).

## How each pattern is shipped

Every pattern in vstack ships five layers:

1. **Documented.** A README explaining the OB framework, the agent failure mode it addresses, the academic citation, and the proposed intervention.
2. **Implemented.** A working Python (and optionally TypeScript) library.
3. **Demoed.** A runnable example on at least one major agent framework (Claude Agent SDK, LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, Mastra, Strands).
4. **Benchmarked.** An eval on a public multi-agent task (GAIA, SWE-Bench-multi, AppWorld, AgentBench).
5. **Written up.** A Substack-ready essay drafting the pattern, the failure it addresses, and the underlying OB theory — paper outline included.

Patterns ship one at a time, fully completed. Quantity loses to quality. **All 34 patterns from the roadmap are shipped.** v0.1.0 adds the production-readiness layer (structured logging with run-id correlation, optional token/cost telemetry, prompt-injection input guards, async LLM clients, configurable timeouts, py.typed marker, security policy, release automation).

## Install

```bash
pip install valanistack
```

Optional extras (per LLM backend / per surface):

```bash
pip install "valanistack[anthropic]"   # Anthropic
pip install "valanistack[openai]"      # OpenAI
pip install "valanistack[ollama]"      # Ollama (local models)
pip install "valanistack[mcp]"         # MCP server (vstack-mcp)
pip install "valanistack[api]"         # REST API (vstack-api, FastAPI)
pip install "valanistack[all]"         # everything above
```

Python 3.11+ required (3.11, 3.12, 3.13 tested in CI). For the absolute latest pre-release, install from source: `pip install git+https://github.com/valani9/vstack.git`.

After install, every CLI ships on PATH:

```bash
vstack --help                # foundational AAR generator
vstack-mcp serve             # MCP server (stdio)
vstack-api serve             # REST API (FastAPI on 127.0.0.1:8000)
vstack-config list           # ~/.vstack/ preferences
vstack-upgrade               # check PyPI for newer releases
vstack-learn recall          # browse the learning store (~/.vstack/learnings.jsonl)
vstack-analytics summary     # aggregate LLM-call telemetry from ~/.vstack/analytics/
vstack-<pattern> --help      # one CLI per pattern (vstack-lewin, vstack-schein-culture, ...)
```

## Use vstack from a framework (LangChain / CrewAI / AutoGen / ...)

For agent-builder workflows, ``vstack.adapters`` wraps every pattern as a native tool in your favorite framework. The shape stays consistent — same input model, same detection output, same registry — only the framework wrapper differs.

```python
# LangChain
from vstack.adapters.langchain import as_langchain_tools
tools = as_langchain_tools()                # ['StructuredTool', ...] × 34

# LangGraph
from vstack.adapters.langgraph import as_langgraph_nodes
nodes = as_langgraph_nodes()                # {'vstack_lewin': node_fn, ...}

# CrewAI
from vstack.adapters.crewai import as_crewai_tools
tools = as_crewai_tools()

# AutoGen (no autogen import required — pure JSON manifest + Python callables)
from vstack.adapters.autogen import as_autogen_function_manifest, as_autogen_callables
manifest = as_autogen_function_manifest()
callables = as_autogen_callables()

# LlamaIndex
from vstack.adapters.llamaindex import as_llamaindex_tools
tools = as_llamaindex_tools()

# Pydantic AI
from vstack.adapters.pydantic_ai import as_pydantic_ai_tools
tools = as_pydantic_ai_tools()

# OpenAI Assistants API / function calling (pure JSON)
from vstack.adapters.openai import as_openai_tool_schemas, as_anthropic_tool_schemas
openai_tools = as_openai_tool_schemas()
anthropic_tools = as_anthropic_tool_schemas()

# Open WebUI tool manifest pointing at a running vstack-api
from vstack.adapters.openwebui import as_openwebui_manifest
manifest = as_openwebui_manifest(api_base_url="http://127.0.0.1:8000")
```

Install only the framework extras you need (`valanistack[langchain]`, `valanistack[crewai]`, etc.) — `valanistack[adapters]` bundles all of them.

## Use vstack from your AI client (MCP)

vstack ships an MCP (Model Context Protocol) server that exposes all 34 diagnostic patterns as tools, plus per-pattern citations + playbooks + composition manifests as resources, plus invocation templates as prompts. Compatible with any MCP-aware client — Claude Desktop, Cursor, Cline, Continue, and others.

Install the MCP extra and bind to your client.

```bash
pip install "valanistack[anthropic,mcp]"
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

**Cursor** — paste the same `mcpServers` block into `~/.cursor/mcp.json` (or the project-level `.cursor/mcp.json`).

**Cline / Continue** — open the MCP-servers config in the extension settings and paste the same block.

You can also auto-generate a config snippet:

```bash
vstack-mcp config-snippet claude-desktop
vstack-mcp config-snippet cursor
vstack-mcp list-tools
vstack-mcp list-resources
```

Once configured, ask your client to run any of the 34 patterns by name — for example, _"Use the Schein culture audit on this trace..."_ — and the client will call the matching tool, the server will run the analyzer, and the detection comes back as structured JSON. The server runs as a local stdio subprocess; nothing leaves your machine except whatever LLM calls the analyzer itself makes.

## Run vstack as a REST service (HTTP)

For server-side use cases (background workers, non-Python clients, multi-tenant dashboards), vstack ships a FastAPI app that exposes every pattern as a POST endpoint plus auto-generated OpenAPI.

```bash
pip install "valanistack[anthropic,api]"
export ANTHROPIC_API_KEY="sk-ant-..."
vstack-api serve                  # 127.0.0.1:8000 by default
```

Endpoints:

- `GET  /healthz` — liveness probe
- `GET  /v1/patterns` — catalogue of 34 patterns + tool names + analyze URLs
- `GET  /v1/patterns/{name}` — one pattern's record
- `GET  /v1/patterns/{name}/playbooks` — per-pattern failure-mode playbooks
- `GET  /v1/patterns/{name}/citations` — per-pattern CITATIONS.md
- `GET  /v1/patterns/{name}/composition` — cross-pattern handoff manifest
- `POST /v1/analyze/{name}` — run the pattern; body is the pattern's input trace (with optional `mode` / `model`)
- `GET  /openapi.json` — full OpenAPI 3.x spec; feed it into any client SDK generator
- `GET  /docs` — interactive Swagger UI

No auth in v0; bind to `127.0.0.1` only and put a real reverse proxy in front if you go remote.

## Run vstack from Docker

For zero-Python-toolchain deployments, the container ships every CLI + the MCP server + the REST API.

```bash
docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY="sk-ant-..." \
  ghcr.io/valani9/vstack:latest \
  vstack-api serve --host 0.0.0.0 --port 8000
```

Images are multi-arch (linux/amd64 + linux/arm64) and pinned per release (`:0.3.0`, `:0.3`, `:0`, `:latest`). The `docker.yml` workflow builds + pushes on every tag.

## Use vstack from Claude Code (slash-skills)

Seven task-shaped Claude Code skills ship under `_skills/`, composing the 34 patterns into real workflows:

| Skill | Composes |
|---|---|
| `/vstack` | Meta entry — routes a free-form complaint to the right skill |
| `/vstack-pick-pattern` | Interview-based pattern picker |
| `/vstack-post-incident` | AAR → Lewin attribution → 1-2 downstream |
| `/vstack-audit-crew` | Lencioni + Edmondson + Trust Triangle + Process Gain/Loss + Bias Stack |
| `/vstack-bottleneck` | Span-of-Control + Org-Structure + Social Loafing + Superflocks |
| `/vstack-culture-check` | Schein + Robbins-Judge (+ optional McGregor) |
| `/vstack-baseline` | Record + compare calibration baselines per pattern |

Install:

```bash
vstack-config install-skills              # copies to ~/.claude/skills/vstack/
vstack-config install-skills --dry-run    # preview first
```

## Persistent state — `~/.vstack/`

vstack stores calibration baselines, session history, and user preferences in `~/.vstack/`. Override the home directory with `VSTACK_HOME`. Inspect or change preferences with `vstack-config`:

```bash
vstack-config list                       # current preferences
vstack-config get default_mode           # one key
vstack-config set default_mode forensic  # write a key (JSON-coerced)
vstack-config keys                       # documented preferences + defaults
vstack-config path baselines             # print the baselines dir
```

## Quick start

```python
from datetime import datetime, timezone

from vstack.aar import AARGenerator, AgentTrace, TraceStep
from vstack.aar.clients import AnthropicClient

# Build (or import from your observability tool) a structured trace of a
# failed agent run.
trace = AgentTrace(
    goal="Refactor the auth module to use JWTs.",
    steps=[
        TraceStep(
            timestamp=datetime.now(timezone.utc),
            type="tool_call",
            content="edit_file(path='auth/middleware.py')",
        ),
        # ... more steps
    ],
    outcome="Created JWT logic but broke the session middleware.",
    success=False,
)

# Run the Wharton 4-step AAR.
aar = AARGenerator(llm_client=AnthropicClient()).generate(trace)

print(aar.to_markdown())                  # human-readable AAR
print(aar.suggested_prompt_patch)         # concrete prompt edit
print(aar.lesson_record_for_memory)       # inject into agent memory
```

See [`module-2-team/30-aar-generator/demo/`](module-2-team/30-aar-generator/demo/) for a self-contained example you can run with no API key (uses a deterministic `StubClient`).

## Command-line interface

Installing the package also installs an `vstack` CLI binary:

```bash
# Generate an AAR from a JSON trace, read from a file, write markdown to stdout
vstack aar --trace path/to/trace.json --client anthropic

# Pipe a trace from stdin (useful in shell pipelines)
cat trace.json | vstack aar --client openai

# Get JSON output instead of markdown
vstack aar --trace trace.json --client anthropic --format json > aar.json

# Try the pipeline without an API key (deterministic stub responses)
echo '{"goal":"x","outcome":"y","success":false,"steps":[]}' | vstack aar --client stub

# Verbose mode (-v INFO, -vv DEBUG)
vstack aar -vv --trace trace.json --client anthropic

# Print version
vstack version
```

The `--client` flag accepts `stub`, `anthropic`, `openai`, or `ollama`. The `stub` client is deterministic and requires no API key, useful for trying the pipeline before committing to a provider. The Anthropic and OpenAI clients read API keys from `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` environment variables.

## Production-readiness

The library is built to ship:

- **Retry with exponential backoff** on rate limits, transient network errors, and provider 5xx — configurable via `max_retries`.
- **Graceful degradation** on malformed LLM JSON output — bad lessons/next-steps are dropped with a warning log, not raised; a partial AAR is more useful than no AAR.
- **Trace truncation** for inputs larger than `max_trace_chars` (default 200K characters) — middle-truncated to keep the most informative head and tail of the agent run.
- **Structured logging** via Python `logging` under the `vstack.aar` namespace.
- **Type-safe** — `mypy --strict` clean across the library.
- **CI** — GitHub Actions runs tests, ruff lint, ruff format check, mypy strict, and a wheel-build sanity check on every push and pull request, across Python 3.11 / 3.12 / 3.13 on Linux and macOS.

## Who this is for

- AI builders shipping agents in production who notice their systems failing in patterns that look like organizational problems, not just engineering ones.
- Multi-agent system developers tired of treating their orchestrator as a router and looking for vocabulary for what's actually happening.
- Researchers exploring the intersection of organizational behavior and AI agent design.
- Curious humans who want to think about what it means for AI agents to learn, disagree, escalate, and trust each other — and recognize that we have 80 years of human-organization research to draw on.

## Status

**Complete.** All 34 patterns shipped at the 5-layer quality bar (docs + lib + demo + benchmark + essay):

- `vstack.aar` (#30) — After-Action Review generator
- `vstack.lencioni` (#17) — Five-Dysfunctions diagnostic
- `vstack.trust_triangle` (#18) — Frei & Morriss Trust Triangle audit
- `vstack.johari` (#03) — Johari Window self-audit
- `vstack.grpi` (#13) — GRPI Working Agreement generator
- `vstack.bias_stack` (#27) — Kahneman/Tversky Bias-Stack detector
- `vstack.psych_safety` (#20) — Edmondson Psychological Safety score
- `vstack.thomas_kilmann` (#29) — Thomas-Kilmann Conflict Style selector
- `vstack.feedback_triggers` (#22) — Stone & Heen 3-Trigger feedback diagnostic
- `vstack.devils_advocate` (#28) — Critical-Evaluator / Devil's Advocate role separator
- `vstack.lewin` (#01) — Lewin Formula B = f(I, E) attribution diagnostic
- `vstack.mcallister_trust` (#19) — McAllister Cognitive vs Affective Trust dimensions
- `vstack.social_loafing` (#15) — Latané Social Loafing detector
- `vstack.debate_pathology` (#26) — Groupthink / Polarization / Emotional Contagion detector
- `vstack.process_gain_loss` (#14) — Steiner / Robbins & Judge Process Gain/Loss detector
- `vstack.smart_goal` (#24) — Doran SMART Goal generator
- `vstack.mcgregor` (#11) — McGregor Theory X/Y Orchestrator Mode detector
- `vstack.group_decision` (#25) — Stewart / Kaner Group Decision Models generator (fist-to-five + 4 others)
- `vstack.schein_culture` (#31) — Schein Iceberg Culture Audit (first Module 3 pattern)
- `vstack.grant_strengths` (#08) — Adam Grant Strengths-as-Weaknesses detector
- `vstack.plus_delta` (#23) — Brené Brown Plus/Delta inter-agent feedback format generator
- `vstack.robbins_culture` (#32) — Robbins & Judge 7-Characteristics Culture profile diagnostic
- `vstack.superflocks` (#16) — Heffernan/Muir Superflocks routing-fragility detector
- `vstack.yerkes_dodson` (#06) — Yerkes-Dodson Optimal Workload pressure-curve diagnostic
- `vstack.org_structure` (#33) — Galbraith/Mintzberg Org-Structure Matrix analyzer (third Module 3 pattern)
- `vstack.motivation_traps` (#09) — Saxberg 4 Motivation Traps diagnostic (Values / Self-Efficacy / Emotions / Attribution)
- `vstack.glaser_conversation` (#21) — Glaser Cortisol/Oxytocin Conversation Steering diagnostic
- `vstack.goleman_ei` (#02) — Goleman/Boyatzis 4-Domain Emotional Intelligence audit (SELF/OTHER × RECOGNITION/REGULATION)
- `vstack.sdt_reward` (#10) — Deci & Ryan Self-Determination Theory intrinsic reward shaping (autonomy / competence / relatedness)
- `vstack.span_of_control` (#34) — deterministic Span-of-Control / Centralization calculator (fourth Module 3 pattern)
- `vstack.danva_emotion` (#04) — Nowicki/Duke DANVA-style emotion recognition (deterministic per-emotion accuracy + confusion + intensity)
- `vstack.cognitive_reappraisal` (#05) — Gross emotion-regulation strategy diagnostic (reappraisal vs suppression vs rumination vs avoidance)
- `vstack.hexaco` (#07) — Lee & Ashton 6-factor personality + H-factor safety risk
- `vstack.vroom_expectancy` (#12) — Vroom E × I × V motivation calculus with bottleneck-term diagnostic

**The 34-pattern roadmap is complete.** See [PATTERNS.md](PATTERNS.md) for the full list.

## License

MIT.

## Maintainer

Ilhan Valani — builder, working in public.
Background: [github.com/valani9](https://github.com/valani9). Inspired by the open-source-as-credibility-engine practice of gstack.

---

*If you're an AI builder, an OB researcher, or an academic who'd like to collaborate on a pattern, open an issue or reach out.*
