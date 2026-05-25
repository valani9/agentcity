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

Optional extras (per LLM backend):

```bash
pip install "vstack[anthropic]"   # Anthropic
pip install "vstack[openai]"      # OpenAI
pip install "vstack[all]"         # both
```

Python 3.11+ required (3.11, 3.12, 3.13 tested in CI). For the absolute latest pre-release, install from source: `pip install git+https://github.com/valani9/vstack.git`.

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
