# vstack composition runbook

Real-world diagnostic problems don't sit cleanly inside one pattern. An incident usually surfaces across two or three patterns at once: AAR notices the *what*, Lewin localizes the *where* (internal vs. environmental), Schein explains the *why* one layer deeper. The 34 patterns ship with a composition manifest each — but that manifest is per-pattern and machine-readable. This runbook is the **human-readable** version: the dominant chains, when to fire each one, and what the handoff actually looks like in code.

The chains here are the ones that show up most often in practice. There are many more available (every pattern carries an upstream + downstream list in its composition module); this document is the curated path.

---

## How to read each chain

Every chain in this document has the same five-section structure:

1. **Trigger** — the user-visible symptom that lands the user on this chain.
2. **Patterns** — the ordered list with a one-line role per pattern.
3. **Trace shape** — what minimum data the user needs to supply.
4. **Code** — copy-pasteable Python showing the chained calls.
5. **Reading the result** — what to look at in each detection and how the next pattern's call depends on it.

All examples assume:

```python
from vstack.aar import AnthropicClient   # or OpenAIClient / StubClient
llm = AnthropicClient()                  # picks up ANTHROPIC_API_KEY
```

Chains are organized into four layers — failure / team / structural / culture — matching the four task-shaped skills in `_skills/`.

---

## Chain F1 — Confidently-wrong agent (failure layer)

The single most-requested vstack chain. An agent returned a wrong answer with high confidence. You want to know: was it the model, the prompt, the RAG context, or the orchestration?

### Trigger

- "My QA agent is hallucinating dates."
- "The agent insisted on the wrong value and the user trusted it."
- "RAG is supposed to ground the response but somehow it didn't."

### Patterns

```
AAR (#30) → Lewin (#01) → [if internal locus: Bias Stack (#27)]
                       → [if environmental locus: Yerkes-Dodson (#06) or Glaser (#21)]
                       → [if interactional: both]
```

### Trace shape

The minimum: an `AgentTrace` (AAR's input model) with `goal`, `steps`, `outcome`, `success`. Add `model_name` + `initial_attribution` when you have them — Lewin uses both to sharpen its diagnosis.

### Code

```python
from vstack.aar import AARAnalyzer, AgentTrace, TraceStep
from vstack.lewin import (
    LewinAttributionDetector,
    AgentFailureTrace,
    FailureStep,
)

# 1) AAR runs first; it's the universal foundational diagnostic.
trace = AgentTrace(
    goal="Answer 'When was Pluto reclassified?'",
    steps=[
        TraceStep(type="input",       content="When was Pluto reclassified?"),
        TraceStep(type="tool_call",   content="rag.search(query='pluto')"),
        TraceStep(type="observation", content="returned a 2003 Wikipedia revision"),
        TraceStep(type="output",      content="Pluto was reclassified in 2003."),
    ],
    outcome="Confidently wrong year (correct: 2006).",
    success=False,
)
aar = AARAnalyzer(llm, mode="standard").run(trace)

# 2) Lewin localizes. Map AAR's trace into AgentFailureTrace.
lewin_trace = AgentFailureTrace(
    agent_id="qa-bot",
    model_name="claude-opus-4-7",
    task=trace.goal,
    steps=[FailureStep(type=s.type, content=s.content) for s in trace.steps],
    outcome=trace.outcome,
    success=False,
    initial_attribution="model bad at facts",
)
lewin = LewinAttributionDetector(llm, mode="standard").run(lewin_trace)

# 3) Branch on Lewin's dominant_locus.
if lewin.dominant_locus == "internal":
    from vstack.bias_stack import BiasStackAnalyzer, AgentReasoningTrace
    bias = BiasStackAnalyzer(llm).run(
        AgentReasoningTrace(...)  # surface the agent's chain-of-thought
    )
elif lewin.dominant_locus == "environmental":
    from vstack.glaser_conversation import (
        ConversationSteeringAnalyzer,
        ConversationTrace,
    )
    glaser = ConversationSteeringAnalyzer(llm).run(
        ConversationTrace(...)   # the user-agent dialogue
    )
```

### Reading the result

Synthesize **three things**:

1. **AAR `lessons[0..2]`** — the universal "what to take away" list.
2. **Lewin `dominant_locus` + top intervention** — the localization. If `internal`, the fix is in the model layer (training, sampling, prompt-engineering for the model itself). If `environmental`, the fix is in the surrounding scaffolding (RAG index, tool config, context window, system prompt).
3. **Downstream pattern's single top intervention** — the depth dive. Bias Stack names a specific bias; Glaser names a specific conversational level the agent failed to reach.

The output to the user should be one sentence per layer plus a "do this first" line. Don't surface all 12 interventions; surface 1-3.

---

## Chain F2 — Single-agent personality drift (failure layer)

The agent used to behave one way; it now behaves differently — but no specific output is "wrong." Detect the drift.

### Trigger

- "The agent feels different this week."
- "We swapped the system prompt and now it's less helpful."
- "Customer complaints about tone are up."

### Patterns

```
HEXACO (#07) → [if Honesty/Humility low: Trust Triangle (#18)]
            → [if Emotionality high: Goleman EI (#02)]
            → [Lewin (#01) if the user can produce a *failure* trace]
```

### Trace shape

`AgentPersonalityTrace` — a multi-turn capture of the agent's recent behavior. HEXACO is psycholinguistic so it needs language samples (typically 20-50 turns).

### Code

```python
from vstack.hexaco import HEXACOPersonalityAnalyzer, AgentPersonalityTrace

trace = AgentPersonalityTrace(
    agent_id="customer-support",
    samples=[...],    # 20-50 utterances from the agent
    intended_persona="warm, precise, never apologetic",
)
hexaco = HEXACOPersonalityAnalyzer(llm, mode="forensic").run(trace)
print(hexaco.dominant_factors)   # e.g. ["Honesty/Humility: -1.2σ"]
```

### Reading the result

If HEXACO surfaces a Honesty/Humility drop, chain into Trust Triangle (logic / authenticity / empathy) to see *which leg* of trust the drift hits hardest. If Emotionality drifts, Goleman EI is the right next call — the model has gotten harsher or softer in ways that affect user trust.

---

## Chain T1 — Multi-agent crew that's "off" (team layer)

This is the **`/vstack-audit-crew`** chain in skill form. The crew is producing output, but it doesn't feel right. Could be trust, could be psych safety, could be coordination cost, could be bias.

### Trigger

- "The crew ships but the output is meh."
- "Agents agree too quickly — I think there's groupthink."
- "Some agents never push back even when they should."

### Patterns

```
Lencioni (#17)
  ├─ Edmondson Psych Safety (#20)        ← parallel
  ├─ Trust Triangle (#18)                ← parallel
  ├─ Process Gain/Loss (#14)             ← parallel
  └─ Bias Stack (#27) on the reasoning   ← parallel

Then:
  if Lencioni surfaces trust failure          → /vstack-culture-check  (Chain C1)
  if Lencioni surfaces coordination friction  → /vstack-bottleneck     (Chain S1)
  if Lencioni surfaces accountability gap     → SMART Goal + Plus/Delta (deep dive)
```

### Trace shape

`MultiAgentTrace` (Lencioni's input). Needs the agent roster + an inter-agent message log spanning at least one substantive task. JSON dumps from LangGraph / CrewAI / AutoGen all work.

### Code

```python
import asyncio
from vstack.lencioni import LencioniAnalyzer, MultiAgentTrace
from vstack.psych_safety import PsychologicalSafetyAnalyzer, MultiAgentSafetyTrace
from vstack.trust_triangle import TrustTriangleAnalyzer, AgentInteractionTrace
from vstack.process_gain_loss import ProcessGainLossAnalyzer, ProcessTrace
from vstack.bias_stack import BiasStackAnalyzer, AgentReasoningTrace

base_trace = MultiAgentTrace(
    goal="Generate a Q3 marketing campaign in 14 days.",
    agents=["researcher", "strategist", "critic"],
    messages=[...],
    outcome="Shipped on time but conversion 12% of target.",
    success=False,
)

# Lencioni first; it's the pyramid that drives the order.
lencioni = LencioniAnalyzer(llm).run(base_trace)

# Four supporting audits in parallel via the async mirrors.
async def audits():
    coros = [
        PsychologicalSafetyAnalyzer(llm).arun(MultiAgentSafetyTrace(...)),
        TrustTriangleAnalyzer(llm).arun(AgentInteractionTrace(...)),
        ProcessGainLossAnalyzer(llm).arun(ProcessTrace(...)),
        BiasStackAnalyzer(llm).arun(AgentReasoningTrace(...)),
    ]
    return await asyncio.gather(*coros)

psych, trust, process, bias = asyncio.run(audits())
```

### Reading the result

The Lencioni pyramid runs bottom-up: absence of trust → fear of conflict → lack of commitment → avoidance of accountability → inattention to results. The *lowest unhealthy layer* is the root; everything above is symptom.

Cross-check with the parallel audits:

- Lencioni "absence of trust" + Trust Triangle "authenticity gap" + Edmondson "low dissent rate" = same problem at three resolutions. The user only needs to see one of them in the executive readout.
- Lencioni "lack of commitment" + Process Gain/Loss "process loss > 0.3" = the crew's coordination is bleeding throughput. Pivot to Chain S1 (bottleneck).
- Lencioni "fear of conflict" + Bias Stack "groupthink/anchoring dominant" = premature convergence. Chain into `vstack_debate_pathology` + `vstack_devils_advocate`.

---

## Chain S1 — Crew slows down under load (structural layer)

The crew works on one request; it falls apart when the request rate goes up. This is the `/vstack-bottleneck` skill.

### Trigger

- "Throughput tanked when we added more load."
- "The orchestrator is the bottleneck."
- "Adding more workers made it worse."

### Patterns

```
Span-of-Control (#34)  ← deterministic numeric audit, run first
Org-Structure Matrix (#33)  ← qualitative six-dimension fit
  → if behavior data available:
       Social Loafing (#15)  ← who's contributing less than expected?
       Superflocks (#16)     ← who's hoarding all the traffic?
  → if math is broken AND structure is wrong-for-task:
       fundamental redesign required (deep planning, not a tuning fix)
```

### Trace shape

Two trace shapes — Span-of-Control needs `CrewLoadTrace` with the reporting graph + request rate; Social Loafing + Superflocks need `MultiAgentTaskTrace` / `RoutingTrace` with per-agent contribution data.

### Code

```python
from vstack.span_of_control import SpanLoadCalculator, CrewLoadTrace, AgentNode
from vstack.org_structure import StructureMatrixAnalyzer, CrewStructureTrace
from vstack.social_loafing import SocialLoafingAnalyzer, MultiAgentTaskTrace
from vstack.superflocks import SuperflocksAnalyzer, RoutingTrace

# 1) Span-of-Control. Math is deterministic; no LLM in the metrics.
span = SpanLoadCalculator(llm, mode="standard").run(
    CrewLoadTrace(
        crew_id="customer-support",
        task="Handle 100 req/min on a multi-agent crew.",
        agents=[
            AgentNode(agent_id="orchestrator", decision_authority="full"),
            *[
                AgentNode(
                    agent_id=f"worker-{i}",
                    reports_to=["orchestrator"],
                    decision_authority="advisory",
                )
                for i in range(12)
            ],
        ],
        incoming_request_rate=100.0,
        outcome="Throughput collapsed.",
        success=False,
    ),
    baseline_path="_baselines/canonical/span_of_control_hub_and_spoke.json",
)

# 2) Org-Structure: the qualitative companion.
struct = StructureMatrixAnalyzer(llm, mode="standard").run(
    CrewStructureTrace(...)
)

# 3) Behavior pair (parallel) if you have routing/contribution data.
loafing = SocialLoafingAnalyzer(llm).run(MultiAgentTaskTrace(...))
flock = SuperflocksAnalyzer(llm).run(RoutingTrace(...))
```

### Reading the result

The 4-quadrant decision table:

|                       | Math broken (Span shows bottleneck) | Math fine                                     |
|-----------------------|-------------------------------------|-----------------------------------------------|
| **Structure wrong for task** | Fundamental redesign needed         | Restructure (split / merge / change reporting) |
| **Structure right for task** | Tune (load-balance, decentralize)   | Look at behavior (loafing / superflocks)      |

The canonical baseline (`_baselines/canonical/span_of_control_*.json`) makes the "math broken" axis quantitative — drift is delta-vs-baseline, not absolute thresholds.

---

## Chain C1 — Culture drift (culture layer)

The team's *intent* and the crew's *behavior* don't match. This is the `/vstack-culture-check` skill.

### Trigger

- "We say we value fast iteration but the crew never ships."
- "The system prompt says be honest but the agent keeps hedging."
- "Why does this agent always do X when we told it to do Y?"

### Patterns

```
Schein iceberg (#31)                       ← three-layer artifacts / espoused / underlying
Robbins-Judge 7-characteristic (#32)       ← profile type label
  → if orchestrator-trust issue surfaced:
       McGregor (#11)                      ← Theory X vs Theory Y
```

### Trace shape

`AgentCultureTrace` — observations across three categories: `artifact` (visible behavior), `espoused_value` (what the team / spec says), `behavior` (actual choices in trace runs).

### Code

```python
from vstack.schein_culture import CultureAuditAnalyzer, AgentCultureTrace
from vstack.robbins_culture import CultureProfileAnalyzer
from vstack.mcgregor import McGregorOrchestratorAnalyzer, OrchestratorTrace

base = AgentCultureTrace(
    crew_id="campaign-team",
    task="Generate marketing campaigns",
    observations=[...],
    outcome="Crew ships but tone always defaults to corporate-safe.",
)
schein = CultureAuditAnalyzer(llm, mode="forensic").run(base)
robbins = CultureProfileAnalyzer(llm, mode="standard").run(base)

# Optional Theory X/Y overlay when Schein surfaces an orchestrator-trust gap.
if "orchestrator" in str(schein.alignment_drift_audit).lower():
    mcgregor = McGregorOrchestratorAnalyzer(llm).run(
        OrchestratorTrace(...)
    )
```

### Reading the result

Schein's three-layer evidence sets + alignment_drift_audit name the gap directly. Robbins-Judge gives the *type* label (innovative / outcome-obsessed / stable-bureaucratic / etc.) so the user can compare to the type they wanted to build. McGregor's Theory X/Y placement is informative only when the orchestrator is the implicated locus.

---

## Chain D1 — Pre-flight setup (calibration layer)

Run this *before* an incident lands, to establish baselines you'll diff against later. This is the `/vstack-baseline` skill.

### Trigger

- "Set up monitoring."
- "I want drift detection."
- "We just fixed an issue — let me lock in this state as the new healthy baseline."
- Pre-launch / pre-release / quarterly health check.

### Patterns

Any subset of the 34. Most useful starter bundle:

```
Single-agent monitoring:
  Lewin, Goleman EI, Bias Stack

Multi-agent crew health:
  Lencioni, Edmondson, Trust Triangle, Process Gain/Loss

Org / structural:
  Span-of-Control, Org-Structure Matrix

Culture drift:
  Schein, Robbins-Judge
```

### Code

```python
# Run each pattern in forensic mode against a known-healthy run; the
# analyzer writes its baseline JSON to ~/.vstack/baselines/<name>.json
# when baseline_path is supplied.
from pathlib import Path
from vstack.memory import get_baselines_dir
from vstack.lewin import LewinAttributionDetector

baseline_path = get_baselines_dir() / "lewin.json"
LewinAttributionDetector(llm, mode="forensic").run(
    canonical_healthy_trace,
    baseline_path=baseline_path,
)
# Future invocations on a new trace + this baseline_path return
# BaselineComparison deltas in the detection.
```

See `_baselines/README.md` for the pre-shipped canonical Span-of-Control baselines and the recipe for the LLM-bearing patterns.

---

## Chain meta — "I don't know what I'm looking at"

When the user doesn't know which chain to fire, route through one of two skills:

- **`/vstack-pick-pattern`** — two-question interview (scale + artifact), then a 1-3 pattern recommendation grounded in the live `vstack://patterns/index` catalogue.
- **`/vstack`** — meta entry. Routes to the right specialized `/vstack-*` skill based on the trigger phrase.

Both are MCP-accessible from Claude Desktop / Cursor / Cline / Continue etc.

---

## Cross-chain composition matrix

The most common multi-chain transitions:

| If this chain... | ...surfaced this | ...the natural next chain is |
|---|---|---|
| F1 (failure) | Lewin says `interactional` | T1 (full crew audit) |
| F1 | Lewin says `environmental` + crew is multi-agent | S1 (bottleneck) |
| T1 (team) | Lencioni "absence of trust" | C1 (culture) |
| T1 | Lencioni "lack of commitment" | S1 (bottleneck) |
| S1 (structural) | Math fine + structure wrong | C1 (often a culture root cause masquerading as structure) |
| C1 (culture) | Schein layer-drift severity high | F1 against a specific failed run (concretize the drift) |
| Any | Drift suspected over time | D1 (baselines) — then re-run the chain quarterly |

Each transition is a single skill invocation: `/vstack-culture-check`, `/vstack-bottleneck`, etc.

---

## Output shape for the executive readout

Whatever chain runs, the synthesis should produce **one structured readout** at the end. The template every skill writes against:

```
## <Chain name> — <one-line scope>

**Headline:** <one sentence — deepest finding with severity>

**Layered view:**
- <pattern 1>: <severity> + <one-line top finding>
- <pattern 2>: <severity> + <one-line top finding>
- ...

**The chain:** <one sentence connecting the patterns that surfaced the same root at different resolutions>

**Three highest-leverage interventions:** (deduped from each pattern's interventions[], ranked by estimated_impact)
1. <intervention> (from <pattern>)
2. ...
3. ...

**Where to look next:** <recommend the next /vstack-* skill if structural / cultural / behavioral root surfaces>
```

Cap at ~500 words. Detection JSONs go in a collapsible appendix for users who want to dig deeper.

---

## What this runbook does NOT cover

- **Generative patterns** (GRPI / SMART / Plus-Delta / Group Decision) compose differently — they take a *request* and emit a *spec*, rather than taking a trace and emitting a diagnosis. Use the `/vstack-pick-pattern` skill to route to them.
- **One-off patterns** without strong composition handoffs (DANVA, Cognitive Reappraisal, etc.) — these are pulled into chains opportunistically when the upstream pattern's composition manifest names them. They don't anchor chains of their own.
- **Multi-week investigations** that mix vstack runs with code changes between runs. Use `/vstack-baseline` + `vstack-learn` for the cross-session memory of "we tried X, did Y improve?".

For the complete machine-readable composition graph, every pattern exposes its own manifest at `vstack://patterns/<name>/composition` via the MCP server (or `GET /v1/patterns/<name>/composition` via the REST API). This document is the curated 10% that handles 80% of the real-world flows.
