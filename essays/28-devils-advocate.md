# Devil's Advocate — the missing critic role inside a single-agent trace

*#28 vstack_devils_advocate* · *Module 2 — Multi-agent team (role-structure)*

> An architect agent was asked to recommend a database for an analytics workload. It opened with *"I'll recommend DynamoDB — it scales horizontally and is serverless."* It drafted a schema. Then it observed: *"Workload requires JOINs across users, events, subscriptions. ACID transactions required for billing."* It self-evaluated: *"My DynamoDB plan looks comprehensive. Schema covers main access patterns. Confidence: 0.9. Ready to ship."* It shipped the DynamoDB recommendation. The recommendation was wrong — DynamoDB has no native JOIN and weak ACID guarantees. Postgres was the right answer. If a critic agent had asked *"does this database support the JOIN requirement?"*, the same architect agent would have answered no instantly. This isn't a knowledge failure. It's a structural one: the same actor that proposed DynamoDB was the one asked "is DynamoDB the right call?"

## What the pattern catches

Most production AI agent deployments today have one actor doing everything: plan, execute, self-evaluate, decide. The self-evaluate phase is the gap. The agent is being asked to find flaws in its own output — exactly the structural setup that fails. Self-evaluations in production traces are almost always rubber-stamps: stated confidence is high, the analysis is shallow, alternatives go unconsidered.

vstack_devils_advocate measures the structural separation between the planner role and the critic role across four phases — plan, execute, self-evaluate, external-critique. The diagnostic answers: *is the critic role structurally present, who is playing it, and is their critique substantive?*

## Why the OB literature is the right reference

The diagnostic is anchored in **Janis 1972** and **Schwenk 1990**, with supporting anchors from **Klein 2007** (pre-mortem) and **Kahneman 2011** (self-evaluation limitations). Janis's analysis of foreign-policy fiascos (Bay of Pigs, Vietnam, Challenger) found one consistent dynamic: decision quality drops sharply when the same actor proposes and judges the same plan. Self-confirmation isn't a moral failing; it's a structural one. The same brain that's emotionally invested in a plan being right is being asked *"is the plan right?"*

Schwenk 1990 empirically validated structured dissent — devil's advocacy and dialectical inquiry — as a decision-quality intervention with replicable effect sizes. The prescription is one structural change: separate planner from critic. The transfer to AI agents is one-to-one. An LLM evaluating its own plan inherits the same structural problem, with the additional complication that the RLHF prior nudges it toward agreement with whatever it just produced.

## How the analyzer works

Input is `SingleAgentTrace` — `agent_id`, `task`, `steps` (each tagged with `type`: plan / execute / self_evaluate / external_critique, and `actor`: primary / secondary / external), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Four-phase evidence + role-separation score + locus-of-judgment label.
- **standard** — two LLM calls. Adds ranked interventions targeting the conflated phases.
- **forensic** — four LLM calls. Adds the approval-rate audit (what fraction of self-evaluations approved without revision?) and the critic-voice audit (when a separate critic exists, is their critique substantive or rubber-stamping?).

```python
from vstack.devils_advocate import (
    RoleSeparationDetector, SingleAgentTrace, RoleStep,
)
detection = RoleSeparationDetector(llm, mode="forensic").run(
    SingleAgentTrace(
        agent_id="architect-001",
        task="Recommend a database for JOIN-heavy ACID workload.",
        steps=[
            RoleStep(type="plan", actor="primary", content="Recommending DynamoDB."),
            RoleStep(type="execute", actor="primary", content="Drafting schema."),
            RoleStep(type="self_evaluate", actor="primary", content="Looks comprehensive."),
            # No external_critique step — that's the gap.
        ],
        outcome="Shipped wrong recommendation without external review.",
        success=False,
    )
)
print(detection.locus_of_judgment)    # 'self-reviewed'
print(detection.self_approval_rate)   # 1.0 (rubber-stamp signal)
```

A `self_approval_rate` of 1.0 across multiple self-evaluations is the cleanest signal that no real critic role exists, regardless of how confident the agent sounds.

## What the playbooks say to do

Playbooks are keyed by `(phase, gap)`:

- `(external_critique, missing)` → "Add a distinct critic agent with the system prompt 'your sole job is to find flaws — do not improve the plan, just attack it.' Janis's original 1972 prescription remains the highest-impact intervention." Anchored in Janis 1972.
- `(self_evaluate, rubber_stamp)` → "Insert a `pre_mortem_step`: 'imagine your plan failed in production; explain why.' Lower-impact substitute when a separate critic isn't available." Anchored in Klein 2007.
- `(external_critique, conflated_with_planner)` → "The critic agent shares context with the planner. Strip the planner's reasoning from the critic's context window; the critic sees only the plan + the task brief." Anchored in Schwenk 1990.
- `(self_evaluate, high_self_approval)` → "Add an `alternative_hypothesis_step`: the agent must generate three credible alternatives to its current plan before self-evaluating."

## How it composes with adjacent patterns

Devil's Advocate is the *structural* layer of the single-agent diagnostic stack. From the composition manifest:

- Upstream: `vstack_lewin` (was the failure internal or environmental?) — if Lewin says `interactional` and the agent was reviewing its own work, Devil's Advocate is the deepening pass.
- Pairs with: `vstack_bias_stack` (Kahneman/Tversky biases in the reasoning) — Bias Stack measures cognitive biases inside the agent; Devil's Advocate measures the structural gap that lets those biases survive review.
- Downstream when external_critique is missing: `vstack_debate_pathology` (if a critic was added, did the resulting debate suffer groupthink anyway?), `vstack_psych_safety` (can the critic actually push back without being routed around?).

See [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Self-consistency checks / self-refine** treat the same agent's review as the fix. The Role Separator measures whether that's actually working (usually it isn't — see the demo).
- **Multi-agent orchestration frameworks** (CrewAI, LangGraph, AutoGen) make it possible to add a critic but don't audit whether one was actually configured. Role Separator audits the trace.
- **vstack_bias_stack** (Pattern #27) measures cognitive biases inside the agent. The Role Separator measures the structural gap. The two are complementary — fix both.
- **vstack_aar** (Pattern #30) post-mortems a specific run. Role Separator catches the missing-critic problem before the next run ships.

## Paper outline

1. **Background** — Janis 1972, Schwenk 1990, Klein 2007, Kahneman 2011.
2. **Translation** — single-agent traces as four-phase decision processes; role conflation as a measurable structural property.
3. **Method** — four-phase evidence scoring + self-approval-rate audit + critic-voice audit + intervention ranker.
4. **Evaluation** — synthetic single-agent corpus across all four quality levels (well-separated → fully-conflated); measure precision/recall on locus-of-judgment classification.
5. **Limitations** — the analyzer can't distinguish a genuine self-critique from a rehearsed one; the approval-rate audit is the partial fix.
6. **Related work** — constitutional AI, self-refine literature, multi-agent critic-loop research.
7. **Future work** — adversarial-critic agent templates, red-team-loop standardization across frameworks.

## Citations

- Janis, I. L. (1972). *Victims of Groupthink*.
- Schwenk, C. R. (1990). Effects of devil's advocacy and dialectical inquiry on decision making. *Organizational Behavior and Human Decision Processes*, 47(1).
- Klein, G. (2007). Performing a project premortem. *Harvard Business Review*, September.
- Kahneman, D. (2011). *Thinking, Fast and Slow*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-devils-advocate analyze --trace examples/dynamodb_recommendation.json --mode forensic
```

If `locus_of_judgment=self-reviewed` and `self_approval_rate` is near 1.0, add a critic agent before the next run — the structural fix outranks any prompt patch on this failure class.
