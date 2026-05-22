# McGregor Theory X/Y Orchestrator Mode — match oversight to task properties, applied to AI agent orchestration

> *"The conventional view (Theory X) — that the average human being has an inherent dislike of work and will avoid it if possible — leads to a management style based on direction and control. An alternative view (Theory Y) — that the expenditure of physical and mental effort in work is as natural as play — leads to a style of integration: enabling subordinates to direct their efforts toward objectives they understand."*
> — Douglas McGregor, *The Human Side of Enterprise* (McGraw-Hill, 1960)

**Status:** 🟢 shipped
**Module:** 1 (Individual) — orchestration design pattern
**Anchor framework:** Douglas McGregor, *The Human Side of Enterprise* (1960). Adopted across the management-theory canon, including its dialectical extensions (Theory Z by William Ouchi, 1981; participative-management literature; situational-leadership models that map the same axis onto follower-readiness).

---

## The OB framework

McGregor's 1960 framework was originally a meta-claim about how managers' implicit assumptions about workers drive their oversight style:

| | Theory X | Theory Y |
|---|---|---|
| **Assumed worker disposition** | Avoids work; needs direction | Wants to do good work; self-motivated |
| **Management style** | Tight oversight; every action approved | Broad goals; autonomy granted |
| **Trust posture** | Low | High |
| **Failure mode** | Wastes cycles on routine work | Invites incidents on risky work |

Modern management literature treats these not as personality types but as **modes that should be chosen per situation.** The right mode depends on task properties:

- High-risk + irreversible + unproven worker → **Theory X** is warranted
- Low-risk + reversible + proven worker → **Theory Y** is warranted
- Mixed properties → **Hybrid** mode (Theory-X on risky steps, Theory-Y on routine ones)

The empirical finding from situational-leadership research: misuse on either side is expensive. Theory-X applied to Theory-Y-appropriate work *wastes cycles* — the oversight overhead dominates without mitigating any risk that was actually present. Theory-Y applied to Theory-X-appropriate work *invites incidents* — autonomy granted on high-risk irreversible work without adequate gates produces the publishable failures.

## How this maps to AI agents

Multi-agent AI systems with an orchestrator + sub-agents have the same choice. The orchestrator can:

- Approve every step (Theory-X)
- Delegate end-to-end (Theory-Y)
- Pick per-step based on risk classification (Hybrid)

In production we see both misuse patterns:

**Theory-X on routine tasks.** A CI runner agent with a clean track record is gated by per-step orchestrator approvals because that's the conservative default. The result is 5× wall-clock time and 5× cost, with no risk-mitigation benefit. The orchestrator overhead dominated because there was no meaningful risk to mitigate.

**Theory-Y on regulated tasks.** A privacy-deletion agent is given "handle the GDPR deletion request end-to-end" with no pre-approval gates. The agent purges the user record *plus* the audit logs the regulator requires the company to retain. A pre-approval gate ("orchestrator must approve before any deletion that touches logs") would have caught it. The mode was wrong for the task.

The hybrid mode is what most production systems should converge on, but it requires explicit risk classification on each agent action — which is itself an engineering task. Most systems default to one mode or the other and live with the mismatch.

## What this pattern does

The `agentcity.mcgregor` library takes an `OrchestratorTrace` with:

- The **task** + **sub-agents** assigned
- **Task properties**: `risk_level` (low/medium/high), `complexity`, `reversibility`, `regulatory_exposure`, `agent_capability`
- The **steps** of the orchestrator-agent interaction (each tagged with `step_type`: delegate, check_in, approve, reject, intervene, broaden, narrow, abort, observation)
- Outcome and success signal

and produces an `OrchestratorModeDetection` with:

1. **Observed mode**: `theory_x` / `theory_y` / `hybrid`
2. **Optimal mode** (given the task properties): same set
3. **Mode mismatch**: 0.0 (matched) to 1.0 (opposite)
4. **Mode indicators**: quantitative scores for `check_in_frequency`, `autonomy_granted`, `pre_approval_required`, `intervention_rate`
5. **Mode quality**: `well-matched` / `mild-mismatch` / `severe-mismatch`
6. **Rationale** for why this mismatch matters for the task
7. **Concrete interventions** ranked by impact: `tighten_oversight`, `loosen_oversight`, `add_pre_approval_gates`, `remove_pre_approval_gates`, `add_risk_classifier`, `increase_check_in_cadence`, `decrease_check_in_cadence`, `redefine_agent_boundaries`, `new_eval`, `human_review`

Two LLM passes under the hood (skipped on `well-matched`). Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Devil's Advocate Role Separator (Pattern #28)** asks whether a critic role exists. The Orchestrator Mode diagnostic asks how much oversight the *orchestrator* itself is providing. They sit at different layers (within-agent critique vs. orchestrator-to-agent oversight).
- **AAR Generator (Pattern #30)** post-mortems specific events. The Orchestrator Mode diagnostic is preventative — diagnose the mode *before* the event.
- **Lewin Attribution (Pattern #01)** classifies failures as internal (model) vs environmental (scaffolding). When the diagnosis is "environmental," the Orchestrator Mode pattern often refines further: was the failure caused by *too much* oversight or *too little*?
- **Generic multi-agent observability** measures activity. This pattern measures the *appropriateness* of the orchestrator's oversight pattern given the task class.

## Design

```python
from agentcity.mcgregor import (
    OrchestratorModeDetector,
    OrchestratorTrace,
    OrchestratorStep,
    TaskProperties,
)
from agentcity.aar.clients import AnthropicClient

trace = OrchestratorTrace(
    trace_id="ci-runner-001",
    task="Run the test suite on every PR.",
    sub_agents=["runner-1"],
    task_properties=TaskProperties(
        risk_level="low",
        complexity="routine",
        reversibility="reversible",
        agent_capability="proven",
    ),
    steps=[...],  # orchestrator approvals + agent observations
    outcome="Test run correct; 5x slower than necessary due to per-step approval.",
    success=True,
)

detection = OrchestratorModeDetector(llm_client=AnthropicClient()).run(trace)
print(detection.to_markdown())
# observed: theory_x. optimal: theory_y. mode_quality: severe-mismatch.
# Intervention #1: remove_pre_approval_gates.
```

## Files

- `lib/schema.py` — `OrchestratorTrace`, `OrchestratorStep`, `TaskProperties`, `ModeIndicators`, `OrchestratorModeDetection`
- `lib/prompts.py` — `MODE_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `MCGREGOR_SYSTEM_PROMPT`
- `lib/generator.py` — `OrchestratorModeDetector` (2-pass pipeline; skips pass 2 when mode is well-matched)
- `demo/01_self_contained_demo.py` — Theory-X-on-routine-CI scenario with stub client
- `eval/synthetic_orchestrator_failures.yaml` — 8 hand-crafted scenarios across observed × optimal × quality buckets
- `eval/run_benchmark.py` — scoring runner
- `tests/test_mcgregor.py` — pytest tests covering validation, pipeline, mode coercion, threshold reconciliation
- `essay.md` — Substack-ready essay
