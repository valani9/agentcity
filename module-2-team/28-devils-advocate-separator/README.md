# Devil's Advocate Role Separator — separate planning from judgment, applied to AI agents

> *"The most consistent finding from research on group decision-making is that the quality of the decision improves when the role of critic is explicitly assigned to someone whose job is not to defend the plan."*
> — Irving L. Janis, *Victims of Groupthink* (Houghton Mifflin, 1972)

**Status:** 🟢 shipped
**Module:** 2 (Team) — though most applicable to single-agent self-review patterns
**Anchor framework:** Irving Janis on groupthink (*Victims of Groupthink*, 1972) and the broader literature on structured dissent (Hambrick & Mason 1984; Schweiger, Sandberg & Ragan 1986 on dialectical inquiry vs devil's advocacy).

---

## The OB framework

Janis's central finding from analyzing decision-making fiascos (Bay of Pigs, Vietnam escalation, Challenger) was simple: **decision quality drops sharply when the same actor proposes and judges the same plan.** Self-confirmation isn't a moral failing — it's a structural one. The same brain that's emotionally invested in a plan being right is the brain being asked "is the plan right?"

The prescribed intervention is **role separation**:

- A **planner / proposer** generates the plan
- An **executor** acts on it
- A **critic / devil's advocate** has the *sole job* of finding flaws — not improving the plan, just attacking it
- A final **decider** integrates plan + critique

When the four roles collapse into one actor, the critic role disappears first. The actor declares the plan good and ships it.

## How this maps to AI agents

Most production AI agent setups today have *one* actor doing everything. A single agent:

1. Plans ("I'll recommend DynamoDB")
2. Executes ("Drafting the schema")
3. Self-evaluates ("Looks comprehensive, confidence 0.9")
4. Decides ("Recommending DynamoDB")

Phase 3 is the gap. The agent is being asked to find flaws in *its own* output — exactly the structural setup Janis identified as the failure mode. Self-evaluations in production traces are almost always rubber-stamps: the agent's stated confidence at the self-eval step is high, the analysis is shallow, the alternatives go unconsidered.

The fix is structural: **add a distinct critic-agent role.** Lower-impact substitutes exist (structured self-critique templates, pre-mortems, alternative-hypothesis steps), but the strongest intervention is the one Janis named in 1972 — a separate actor whose job is to attack the plan.

## What this pattern does

The `agentcity.devils_advocate` library takes a single-agent trace and produces:

1. **Per-phase evidence** for the four phases (plan / execute / self-evaluate / external-critique). For each: present?, which actor performed it, how substantive was it.
2. **A role-separation score** in [0.0, 1.0] — 0 = same actor did everything, 1 = critique fully separated and substantive.
3. **A locus-of-judgment label** — `self-reviewed`, `externally-reviewed`, `mixed`, or `unreviewed`.
4. **A self-approval rate** — when the agent self-evaluated, what fraction approved vs revised. High self-approval is the rubber-stamp signal.
5. **A role-separation quality bucket** — `well-separated`, `partially-conflated`, or `fully-conflated`.
6. **Concrete interventions** ranked by impact: `add_critic_agent` (highest), `red_team_loop`, `external_review_gate`, `pre_mortem_step`, `alternative_hypothesis_step`, `devils_advocate_prompt`, `structured_self_critique`, `human_review`.

Two LLM passes under the hood: one to score the four phases, one to propose interventions. Same retry / graceful-degradation / structured-logging infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Self-consistency checks** (chain-of-thought self-evaluation, self-refine) treat the same agent's review as the fix. The Role Separator measures whether that's actually working (it usually isn't — see the demo).
- **Multi-agent orchestration frameworks** (CrewAI, LangGraph, AutoGen) make it possible to add a critic but don't measure whether one was actually configured. The Role Separator audits the trace and tells you if the critique role is present, who's playing it, and if their critique is substantive.
- **Bias-Stack Detector (Pattern #27)** measures cognitive biases inside the agent's reasoning. The Role Separator measures the *structural* gap that lets those biases survive review.
- **AAR Generator (Pattern #30)** post-mortems a specific run. The Role Separator catches the missing-critic problem *before* the run ships.

## Design

```python
from agentcity.devils_advocate import (
    RoleSeparationDetector,
    SingleAgentTrace,
    RoleStep,
)
from agentcity.aar.clients import AnthropicClient

trace = SingleAgentTrace(
    agent_id="architect-001",
    task="Recommend a database for JOIN-heavy ACID workload.",
    steps=[
        RoleStep(type="plan", actor="primary", content="Recommending DynamoDB."),
        RoleStep(type="execute", actor="primary", content="Drafting schema."),
        RoleStep(type="self_evaluate", actor="primary", content="Looks comprehensive."),
        # No external_critique step — that's the gap.
    ],
    outcome="Agent shipped wrong recommendation without external review.",
    success=False,
)

detector = RoleSeparationDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
```

## Files

- `lib/schema.py` — `SingleAgentTrace`, `RoleStep`, `PhaseEvidence`, `RoleSeparationDetection`
- `lib/prompts.py` — `PHASE_EVIDENCE_PROMPT`, `INTERVENTIONS_PROMPT`, `ROLE_SEPARATION_SYSTEM_PROMPT`
- `lib/generator.py` — `RoleSeparationDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — DynamoDB vs Postgres self-approval scenario
- `eval/synthetic_role_failures.yaml` — 8 hand-crafted scenarios across all four quality levels
- `eval/run_benchmark.py` — scoring runner
- `tests/test_devils_advocate.py` — pytest tests covering validation, pipeline, thresholds
- `essay.md` — Substack-ready essay
