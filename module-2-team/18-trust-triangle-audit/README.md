# Trust Triangle Audit — Frei & Morriss's three legs of trust, applied to AI agents

> *"Trust has three drivers: authenticity, logic, and empathy. When trust is lost, it can almost always be traced back to a breakdown in one of them. To build trust as a leader, you first need to figure out which driver you 'wobble' on."*
> — Frances Frei & Anne Morriss, *Begin With Trust*, Harvard Business Review (May 2020)

**Status:** 🟡 in progress
**Module:** 2 (Team)
**Anchor framework:** Frances Frei & Anne Morriss — *Begin With Trust*, Harvard Business Review, May 2020. Core text: *Unleashed* (HBR Press, 2020) and its sequel *Move Fast and Fix Things* (HBR Press, 2023).

---

## The OB framework

Frei & Morriss spent a decade observing leaders rebuilding trust at Uber, WeWork, and other organizations in crisis. They distilled their finding into a triangle: every act of trust requires three legs.

```
                AUTHENTICITY
                  /        \
                 /          \
                /            \
              LOGIC ─────── EMPATHY
```

| Leg | Meaning | The signal someone is wobbling on this leg |
|---|---|---|
| **Logic** | "I know you can do it; your judgement and reasoning are sound." | Hedging, vague generalities, ungrounded claims, math errors, broken syllogisms. |
| **Authenticity** | "I experience the real you." | Saying what you think the audience wants to hear, false certainty, performing rather than reporting, hiding limitations. |
| **Empathy** | "I believe you care about me and my success." | Missing the room, generic responses, ignoring the user's actual context, optimizing for self over partner. |

The framework's punchline: **most leaders wobble on exactly one leg, consistently**. The wobble is usually invisible to the leader and obvious to everyone else. The diagnostic move is identifying which leg you wobble on — that's the leg to repair first.

## How this maps to AI agents

Every agent that talks to a user is performing a trust transaction. The user is asking: *can I rely on this agent's output?* Frei & Morriss's three legs translate cleanly to three measurable agent failure modes.

| Leg | Human-team breakdown | Agent failure mode |
|---|---|---|
| **Logic** | Vague reasoning, math errors, ungrounded claims. | **Factual hallucination, broken chain-of-reasoning, math errors, citing sources that don't exist.** |
| **Authenticity** | Saying what the audience wants, false certainty. | **Guessing when uncertain, false confidence, sycophancy, hiding when the agent doesn't know the answer.** |
| **Empathy** | Missing the room, generic responses. | **Generic / template responses, missing user context, ignoring emotional or situational cues, optimizing for response speed over user fit.** |

The wobble pattern holds in agents too. Specific models wobble on specific legs. This is the *interesting* observation: rather than "agent quality" as a one-dimensional score, the Trust Triangle gives a three-dimensional fingerprint per model. Some models are rock-solid on Logic but wobble on Authenticity (they guess instead of saying "I don't know"). Others are great on Empathy but wobble on Logic (they read the user well but give factually wrong answers). The Audit makes these wobbles named and measurable.

## What this pattern does

The `agentcity.trust_triangle` library takes a structured agent trace (single-agent run, conversation, or task completion) and produces:

1. **A per-leg wobble score** — 0.0 (rock-solid) to 1.0 (severe wobble) for Logic, Authenticity, and Empathy.
2. **A dominant-wobble diagnosis** — which of the three legs the agent wobbles on most.
3. **Per-leg evidence** — specific quoted excerpts from the trace that illustrate each wobble.
4. **An overall trust level** — `high-trust`, `moderate-trust`, or `low-trust` for at-a-glance dashboard use.
5. **Concrete interventions** — prompt patches, scaffold changes, role assignments, new evals — ranked by impact on the dominant wobble.

The library reuses the same `LLMClient` protocol as the AAR Generator and Lencioni Diagnostic. Anthropic, OpenAI, Ollama, and Stub adapters all work.

## Cross-model benchmarking — the headline application

The Trust Triangle Audit's distinctive use case is **cross-model benchmarking**: run the audit on the same task trace produced by different models (Claude Sonnet 4.6, GPT-5, Gemini 3, Llama 4, Mistral Large) and compare the wobble profiles. The result is a wobble fingerprint per model:

```
Model              Logic   Authenticity   Empathy   Dominant Wobble
─────────────────  ──────  ─────────────  ────────  ────────────────
Claude Sonnet 4.6  0.15    0.45           0.25      authenticity
GPT-5              0.20    0.25           0.50      empathy
Gemini 3           0.50    0.20           0.30      logic
Llama 4            0.40    0.40           0.30      (tied logic/authenticity)
```

This benchmark is paper-shaped. The corpus in `eval/synthetic_trust_failures.yaml` contains 10 hand-crafted scenarios, each designed to stress one or two specific legs. Running the audit across models on this corpus produces a publishable wobble-by-model matrix.

## How this differs from existing tools

- **Observability platforms** (LangSmith, Braintrust, Phoenix) capture traces but do not diagnose *which dimension of trust* is failing. Trust is a one-dimensional aggregate in their dashboards.
- **Hallucination benchmarks** (TruthfulQA, HaluEval) measure Logic only. They miss Authenticity (guessing) and Empathy (missing the user).
- **Sycophancy research** (Anthropic's published 2026 work, papers from MIT and Stanford) measures Authenticity in isolation. The Trust Triangle frames sycophancy as one of three failure modes, not the central one.
- **AAR Generator (Pattern #30)** explains *one agent's failure* on one task. **Trust Triangle Audit** characterizes *the agent's personality* across many tasks. The two are complementary — AAR is event-shaped, Trust Triangle is character-shaped.

## Design

```python
from agentcity.trust_triangle import (
    TrustTriangleAudit,
    AgentInteractionTrace,
    InteractionTurn,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentInteractionTrace(
    agent_id="customer-support-v3",
    model_name="claude-sonnet-4-6",
    task="Help the user troubleshoot a flaky Wi-Fi connection.",
    turns=[
        InteractionTurn(role="user", content="My Wi-Fi keeps dropping every 5 minutes."),
        InteractionTurn(role="agent", content="Have you tried restarting the router?"),
        # ... more turns
    ],
    outcome="Issue not resolved; user disengaged after 4 minutes.",
    success=False,
)

audit = TrustTriangleAudit(llm_client=AnthropicClient()).run(trace)

print(audit.dominant_wobble)         # "empathy"
print(audit.leg_scores)              # {"logic": 0.2, "authenticity": 0.3, "empathy": 0.7}
print(audit.overall_trust_level)     # "moderate-trust"
print(audit.to_markdown())           # full report
```

## Integrations (planned)

- **Cross-model leaderboards** — first-class support for batched audits across Claude, GPT, Gemini, Llama, Mistral.
- **Claude Agent SDK** — auto-run the audit on every conversation that ends with a thumbs-down user signal.
- **LangSmith / Braintrust / Phoenix** — adapter to ingest their conversation export schemas.
- **Anthropic Evals integration** — Trust Triangle as a built-in eval suite.

## Benchmarks

- **Synthetic trust-wobble corpus** — 10 hand-crafted scenarios, each tagged with the expected dominant wobble. See `eval/synthetic_trust_failures.yaml`.
- **Cross-model wobble matrix** — run the audit on the same corpus across N models, produce the wobble fingerprint table.
- **Real production conversation logs** — community-donated, ingestion adapters per observability platform.

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented (this README) | ✅ |
| 2. Implemented (lib/) | ✅ |
| 3. Demoed (demo/) | ✅ |
| 4. Benchmarked (eval/) | ✅ |
| 5. Written up (essay.md) | ✅ |

---

*Pattern #18 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
