# AgentCity

**Organizational behavior, practiced on AI agents.**

AgentCity is a curated library of design patterns for AI agents and multi-agent systems, anchored in named organizational-behavior (OB) literature — Wharton's After-Action Review, Lencioni's Five Dysfunctions, Edmondson's Psychological Safety, Frei & Morriss's Trust Triangle, Stone & Heen's "Thanks for the Feedback" — translated into runnable code, public benchmarks, and Substack-ready essays.

Most agent observability tools capture *what happened* (traces). Most incident-response tools handle *single events* (a postmortem per alert). AgentCity ships a curated library of *organizational practices* — the same frameworks human teams use to learn, debate, escalate, and improve — implemented as patterns AI agents can run themselves.

Where the existing agent ecosystem treats failures as bugs to debug, AgentCity treats them as learning events to organize around.

---

## Disambiguation

You may have seen ["AgentCity: Constitutional Governance for Autonomous Agent Economies via Separation of Power"](https://arxiv.org/abs/2604.07007) (NetX Foundation, April 2026). That paper is about blockchain-based governance for agent economies. **This is a different project.** AgentCity-the-library is an open-source pattern library for applying organizational-behavior frameworks to AI agent design — no blockchain, no governance protocols, no agent economies. Same name, different domain.

---

## What's in here

Three modules mirror the standard organizational-behavior curriculum:

- **Module 1 — Individual Agent Patterns** — Lewin's B=f(I,E), Goleman EI domains, Big Five/HEXACO personality, Vroom expectancy, 4 motivation traps, Yerkes-Dodson optimal workload, Johari Window self-audit.
- **Module 2 — Multi-Agent Team Patterns** — Lencioni Five Dysfunctions diagnostic, Frei & Morriss Trust Triangle audit, Edmondson Psychological Safety score, AAR generator, GRPI working agreement, Thomas-Kilmann conflict-style router, social-loafing and process-loss detectors.
- **Module 3 — System / Organizational Patterns** — Schein's Iceberg culture audit, span-of-control calculator, centralization/decentralization trade-off analyzer.

A full index is in [PATTERNS.md](PATTERNS.md). Academic citations are in [CITATIONS.md](CITATIONS.md).

## How each pattern is shipped

Every pattern in AgentCity ships five layers:

1. **Documented.** A README explaining the OB framework, the agent failure mode it addresses, the academic citation, and the proposed intervention.
2. **Implemented.** A working Python (and optionally TypeScript) library.
3. **Demoed.** A runnable example on at least one major agent framework (Claude Agent SDK, LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, Mastra, Strands).
4. **Benchmarked.** An eval on a public multi-agent task (GAIA, SWE-Bench-multi, AppWorld, AgentBench).
5. **Written up.** A Substack-ready essay drafting the pattern, the failure it addresses, and the underlying OB theory — paper outline included.

Patterns ship one at a time, fully completed. Quantity loses to quality. Currently shipping: *AAR Generator (Wharton 4-step).*

## Install

```bash
pip install git+https://github.com/valani9/AgentCity.git
```

Optional extras (per LLM backend):

```bash
pip install "agentcity[anthropic] @ git+https://github.com/valani9/AgentCity.git"   # Anthropic
pip install "agentcity[openai]    @ git+https://github.com/valani9/AgentCity.git"   # OpenAI
pip install "agentcity[all]       @ git+https://github.com/valani9/AgentCity.git"   # both
```

Python 3.11+ required.

## Quick start

```python
from datetime import datetime, timezone

from agentcity.aar import AARGenerator, AgentTrace, TraceStep
from agentcity.aar.clients import AnthropicClient

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

## Who this is for

- AI builders shipping agents in production who notice their systems failing in patterns that look like organizational problems, not just engineering ones.
- Multi-agent system developers tired of treating their orchestrator as a router and looking for vocabulary for what's actually happening.
- Researchers exploring the intersection of organizational behavior and AI agent design.
- Curious humans who want to think about what it means for AI agents to learn, disagree, escalate, and trust each other — and recognize that we have 80 years of human-organization research to draw on.

## Status

**Early.** Pattern 1 (AAR Generator) is in active development. 30+ patterns are planned. See [PATTERNS.md](PATTERNS.md) for the full roadmap.

## License

MIT.

## Maintainer

Ilhan Valani — builder, working in public.
Background: [github.com/valani9](https://github.com/valani9). Inspired by the open-source-as-credibility-engine practice of gstack.

---

*If you're an AI builder, an OB researcher, or an academic who'd like to collaborate on a pattern, open an issue or reach out.*
