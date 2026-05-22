# AAR Generator — Wharton's After-Action Review for AI Agents

> *"After-Action Reviews: A Simple Yet Powerful Tool"* — Wharton@Work

**Status:** 🟡 in progress (anchor pattern, ships first)
**Module:** 2 (Team) — though it also applies to single-agent
**Class anchor:** MO221 Class 22 (Evaluating Decision-Making)

---

## The OB framework

The After-Action Review (AAR) was codified by the US Army in the early 1970s (Training Circular 25-20) and re-popularized in business literature by Wharton, the Center for Army Lessons Learned (CALL), and Harvard Business Review case studies on companies like BP, GE, and Toyota.

An AAR is a structured reflection ritual conducted *immediately after a task or mission* — whether the task succeeded or failed. It has four steps:

1. **Goal.** What did we *want* to accomplish?
2. **Results.** What did we *actually* do?
3. **Lessons.** *Why* were there differences between #1 and #2?
4. **Next Steps.** What will we do *differently* next time — or, if we succeeded, what will we *repeat*?

Critical constraints (per Wharton@Work):
- Schedule AARs consistently after both *failures and successes*.
- Gather relevant data beforehand.
- Make participation mandatory.
- Follow rules of engagement: confidentiality, transparency, development-focused, future-focused.
- **Share learning across the organization** — individual comments stay private, but lessons get distributed.

The deepest insight from human practice: AARs are not about *discussion at the expense of action*. They are *about action*. The deliverable is a behavioral change, not a paragraph in a Confluence doc.

## The agent failure mode this addresses

> *"Most AI agents have amnesia — every conversation starts from zero, they forget context, and ask the same questions repeatedly. The fundamental problem is that agents can't learn from rejection."*
>
> — Omar Antonio Díaz Peña, *"Why Your AI Agent Keeps Making the Same Mistake,"* Medium, Feb 2026.

> *"One developer experienced five iterations with five rejections of the same fundamental mistake, because the agent couldn't learn from rejection."*

The named failure mode: **agent amnesia + no learning loop**. Concretely:

- An agent fails a task. The developer reports the failure (sometimes by rejecting an output, sometimes by writing a bug ticket, sometimes by just trying again).
- The agent retries with no awareness that this is attempt N of N.
- Same mistake. Same rejection. Same retry. Same mistake.
- Cumulatively: 76% of agent deployments fail in production (Snehal Singh, 2026 analysis of 847 deployments). $4,200 burned in 63 hours (Sattyam Jain, *"The Agent That Burned $4,200 in 63 Hours: A Production AI Postmortem,"* April 2026). 47% user abandonment after week one without proper memory systems.

The class of failure that AAR is *exactly* designed to address.

## What this pattern does

The `agentcity.aar` library takes a structured agent trace and produces:

1. **A written AAR document** following the Wharton 4-step structure (Goal / Results / Lessons / Next Steps).
2. **A specific prompt-patch suggestion** — concrete edit to the system prompt or instructions that, if applied, would prevent the failure on the next run.
3. **A new eval test** — a regression-style test that catches this specific failure mode going forward.
4. **A lesson record** — a structured object that can be injected into long-term agent memory so the agent itself can reference the lesson on subsequent runs.

The library is *not* an observability platform. It consumes traces from existing observability layers (LangSmith, Braintrust, Phoenix, Langfuse, OpenTelemetry, Claude Agent SDK's built-in tracing, OpenAI Agents SDK traces) and produces structured AARs as output.

## Why this is different from existing agent post-mortem patterns

- **Claude Agent SDK's site-reliability-agent cookbook** (Anthropic, 2026) ships post-mortem templates via PagerDuty/Confluence MCP tools. Those are SRE-flavored: an incident fires, the agent investigates, writes a Confluence page. AgentCity's AAR Generator is **OB-flavored**: every agent failure (not just paged incidents) gets the 4-step structure, and the output includes interventions (prompt patches, eval tests, lesson records) — not just documentation.
- **Sattyam Jain's $4,200 postmortem** is a *human writing about an agent's failure*. AgentCity's AAR Generator is *an automated AAR runnable after every agent run*, designed to be consumed by the agent itself.
- **Existing observability tools** (Phoenix, AgentOps, Braintrust, Latitude) capture traces and let humans dig through them. AAR Generator builds on top — it consumes their output and produces the *organizational learning artifact* the human team (or the agent itself) needs.

## Design (working draft)

The library exposes a single high-level call:

```python
from agentcity.aar import AARGenerator, AgentTrace

trace = AgentTrace(
    goal="Refactor the auth module to use JWTs",
    steps=[...],          # populated from observability tool
    outcome="Created tokens but broke the existing session middleware",
    success=False,
)

aar = AARGenerator(llm_client=anthropic).generate(trace)

print(aar.to_markdown())
print(aar.suggested_prompt_patch)
print(aar.suggested_eval_test)

# Optionally inject the lesson into agent memory:
agent.memory.add_lesson(aar.lesson_record)
```

Output schema is documented in [lib/schema.py](lib/schema.py) and the markdown rendering format follows [the canonical Wharton 4-step layout](#).

## Integrations (planned)

The library is framework-agnostic, but ships first-class adapters for:

- **Claude Agent SDK** — auto-run AAR after every `Agent.run()` failure; lesson injected into the agent's persistent memory.
- **LangGraph** — auto-run AAR after every graph run that exits with `error`; output piped to LangSmith as an annotated trace.
- **OpenAI Agents SDK** — same pattern, hooked into the SDK's tracing layer.
- **CrewAI** — runs AAR after the crew's final task; lessons inform next crew kickoff.
- **AutoGen / Microsoft Agent Framework** — adapter forthcoming.
- **Mastra** — adapter forthcoming.

## Benchmarks (planned)

The AAR Generator is benchmarked on three public agent-failure datasets:

- **GAIA** — measures lesson-quality on multi-step reasoning failures.
- **SWE-Bench-multi** — measures whether AAR-derived prompt patches improve agent performance on code-task retries.
- **AppWorld** — measures whether AAR-injected lessons improve agent performance on long-horizon application tasks.

Benchmark methodology: run agent → fail → generate AAR → apply prompt patch → re-run. Measure the delta in success rate, token usage, retry count.

## How to contribute

This pattern is the anchor pattern for AgentCity and the first community signal. Contributions especially welcome from:

- AI engineers shipping production agents who can validate the AAR output against real failures.
- OB researchers willing to review the framework anchoring for fidelity.
- Builders of agent frameworks (LangGraph, Claude SDK, etc.) who want to discuss the integration surface.

Open an issue with [`pattern: aar`] in the title or DM the maintainer.

## Citations

Primary anchor:
- **Wharton@Work** (2014). *After-Action Reviews for Leaders: A Simple Yet Powerful Tool.*
- **US Army TC 25-20** (1993). *A Leader's Guide to After-Action Reviews.*

See [/CITATIONS.md](../../CITATIONS.md) for the full citation index.

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented (this README) | ✅ |
| 2. Implemented (lib/) | 🟡 schema + class skeleton ready, full LLM-driven logic pending |
| 3. Demoed (demo/) | ⚪ TODO — first integration target: Claude Agent SDK |
| 4. Benchmarked (eval/) | ⚪ TODO — first dataset: SWE-Bench-multi failure traces |
| 5. Written up (essay.md) | ✅ first draft ready |

---

*Pattern #30 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
