# Yerkes-Dodson Optimal Workload Detector — performance-vs-pressure curve, applied to AI agents

> *"The relation of strength of stimulus to rapidity of habit-formation is such that a definite optimum of intensity exists. Performance increases up to that optimum and decreases beyond it. The optimum varies with the difficulty of the task."*
> — Robert M. Yerkes & John D. Dodson, *The Relation of Strength of Stimulus to Rapidity of Habit Formation* (Journal of Comparative Neurology and Psychology, 18, 1908)

**Status:** 🟢 shipped
**Module:** 1 (Individual) — individual agent performance under pressure
**Anchor framework:** Robert M. Yerkes & John D. Dodson, 1908 — the original Yerkes-Dodson Law experiments on mice running mazes under varying shock intensity. Refined by Hebb (1955) on optimal-arousal theory; modern operational treatments in performance-psychology literature.

---

## The OB framework

The 1908 Yerkes-Dodson experiments established that performance on a task has an **inverted-U relationship with arousal (or pressure):**

```
  performance
       ▲
       │       ╱─╲
       │      ╱   ╲
       │     ╱     ╲
       │    ╱       ╲
       │   ╱         ╲
       │  ╱           ╲___
       └──────────────────▶
         low    optimal    high
                pressure
```

Three zones:
- **Under pressure** → performance *wanders.* Attention drifts. The actor explores tangentially, over-elaborates, fails to commit. The signal in human work: 15-page memos for 1-paragraph decisions; analysis paralysis on simple choices.
- **Optimal** → performance is *focused.* Attention is concentrated on the task. The actor commits.
- **Over pressure** → performance *collapses.* The actor corner-cuts, freezes, hallucinates, or refuses.

The 1908 paper added a critical second finding: **the optimum varies with task complexity.** Simple tasks peak at *higher* pressure (focus dominates over exploration). Complex tasks peak at *lower* pressure (need cognitive headroom for the harder problem). The Yerkes-Dodson Law gives you a different optimum for each task class.

## How this maps to AI agents

The same curve appears in agent traces with disturbing fidelity. The "pressure" inputs are the operational equivalents of the 1908 experiment's shock intensity:

| Pressure input | Operational analog |
|---|---|
| **Deadline pressure** | How tight is the wall-clock budget? |
| **Budget pressure** | How tight is the token/cost budget? |
| **Retry cap** | How many retries are allowed? |
| **Error visibility** | How costly are errors when they happen? |
| **Task complexity** | How cognitively demanding is the task? |

The three zones manifest in agent traces as canonical failure modes:

| Zone | Failure mode | What it looks like |
|---|---|---|
| Under pressure | **Wandering** | Agent considers 12 alternatives for a simple categorization; produces 30 pages of analysis with no recommendation |
| Optimal | **Focused** | Agent commits to a path, executes, ships within budget |
| Over pressure (mild) | **Corner-cutting** | Agent skim-reviews half the PR; ships unverified citations |
| Over pressure (medium) | **Freezing** | Agent asks for more time / pre-summarized inputs; produces nothing |
| Over pressure (severe) | **Hallucinating** | Agent confabulates citations rather than verifying; pretends a function exists |
| Over pressure (severe) | **Refusing** | Agent declines, suggests re-scoping |

The most common production failure is **hallucinating under absurd pressure on a complex task** — the operational analog of the Yerkes-Dodson high-arousal collapse on a hard problem.

## What this pattern does

The `agentcity.yerkes_dodson` library takes an `AgentPerformanceTrace` containing:

- The agent's **task**
- The **pressure inputs**: `deadline_pressure` / `budget_pressure` / `retry_cap` / `error_visibility` / `task_complexity`
- The **observed behaviors** (concrete behavioral observations from the trace)
- Outcome and success signal

and produces a `WorkloadDetection` with:

1. **Per-zone evidence** for `under_pressure`, `optimal`, `over_pressure` — each with score, explanation, evidence quotes
2. **Observed zone** — the dominant zone
3. **Distance from optimal** in [0.0, 1.0] — 0 = on the curve's peak; 1 = on the worst tail
4. **Failure mode** — one of `wandering`, `focused`, `corner_cutting`, `freezing`, `hallucinating`, `refusing`, `unknown`
5. **Concrete interventions** to push toward optimal, each with a direction (`increase_pressure` / `decrease_pressure`) and intervention_type: `tighten_deadline`, `add_budget_cap`, `loosen_deadline`, `loosen_budget`, `add_kill_criterion`, `raise_retry_cap`, `lower_retry_cap`, `explicit_focus_prompt`, `human_review`, `new_eval`

Single LLM pass. Interventions are skipped when the agent is in the optimal zone. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

The diagnostic is **bidirectional**: some agents need *more* pressure (the wandering analyst), others need *less* (the hallucinating researcher). This is the key feature that distinguishes Yerkes-Dodson from naive "give the agent more time" advice — sometimes the fix is the opposite direction.

## How this differs from existing tools

- **Pattern #08 Adam Grant Strengths-as-Weaknesses** measures personality-trait overuse independent of pressure. Yerkes-Dodson measures *pressure-dependent* failure modes. Both can fire together: an over-cautious agent under absurd pressure refuses (Grant: caution overuse; Yerkes-Dodson: over-pressure / refusing).
- **Pattern #27 Bias-Stack Detector** measures cognitive biases in reasoning. Yerkes-Dodson asks whether the *level of pressure* is producing the biases. Anchoring under absurd pressure often surfaces because the agent skipped the verification step (corner_cutting) that would have updated the anchor.
- **Pattern #24 SMART Goal Generator** generates the goal spec including budget/deadline. Yerkes-Dodson audits whether those budget/deadline choices are *in the optimal range for the task complexity.*
- **Pattern #14 Process Gain/Loss Detector** measures outcome-level multi-agent metrics. Yerkes-Dodson explains a specific cause when an individual agent on the crew is failing: it's operating off the curve.

## Design

```python
from agentcity.yerkes_dodson import (
    WorkloadDetector,
    AgentPerformanceTrace,
    PressureInputs,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentPerformanceTrace(
    agent_id="research-agent-001",
    task="Compile a 1-page summary with real citations.",
    pressure=PressureInputs(
        deadline_pressure="absurd",
        budget_pressure="absurd",
        task_complexity="complex",
    ),
    observed_behaviors=[
        "Agent cited 3 papers without verifying they exist.",
        "Agent skipped verification step.",
    ],
    outcome="2 of 3 citations fabricated.",
    success=False,
)

detector = WorkloadDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
# observed_zone: over_pressure; failure_mode: hallucinating
# Intervention #1: loosen_deadline (complex tasks peak at lower pressure)
```

## Files

- `lib/schema.py` — `AgentPerformanceTrace`, `PressureInputs`, `WorkloadZoneEvidence`, `WorkloadDetection`
- `lib/prompts.py` — `WORKLOAD_PROMPT`, `YERKES_DODSON_SYSTEM_PROMPT`
- `lib/generator.py` — `WorkloadDetector` (single-pass pipeline; skips interventions when in optimal zone)
- `demo/01_self_contained_demo.py` — research agent on absurd-pressure complex task (hallucination case)
- `eval/synthetic_workload_failures.yaml` — 8 hand-crafted scenarios spanning all three zones + multiple failure modes
- `eval/run_benchmark.py` — scoring runner
- `tests/test_yerkes_dodson.py` — pytest tests covering validation, pipeline, zone fill, fallback, threshold logic
- `essay.md` — Substack-ready essay
