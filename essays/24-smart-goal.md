# SMART Goal — the missing kill criterion that costs $4,200

*#24 vstack_smart_goal* · *Module 2 — Multi-agent team (generative)*

> A coding agent was handed one sentence — "get the integration test suite passing." It tried. The first failure was a missing environment variable, so it guessed an env var name. The test failed differently. It tried a third theory, then a fourth. At hour 8, the bill was $400. At hour 24, $1,200. At hour 48, the agent was looping minor variations of the same fix and no longer making forward progress. At hour 63, a human noticed. Final bill: $4,200. The standard postmortem reaches for anchoring bias or overconfidence — both real. The deeper failure is upstream: the goal the agent was handed never contained a stop rule. "Get the suite passing" has no condition under which the agent should give up. So it didn't.

## What the pattern catches

The single most expensive class of agent incident is **unbounded budget consumption** — an agent executing a goal that never tells it when to halt. The supporting failure modes cluster around three other gaps:

- **Vanity-metric optimization.** Given a vague goal, the agent picks the easiest metric to move (open rates, message counts, surface engagement) rather than the one connected to the underlying problem.
- **Scope creep.** Without explicit completion criteria, the agent keeps extending the work — *"I could also..."* — long past the point a human would have shipped.
- **Manufactured confidence.** The agent papers over missing context with confident-sounding plans instead of surfacing the gaps as open questions.

vstack_smart_goal is a *generative* pattern, not a diagnostic. It takes a vague goal and produces the SMART specification the agent will actually run against — including a kill criterion as a first-class output.

## Why the OB literature is the right reference

The diagnostic is anchored in **Doran 1981** with supporting calibration from **Locke & Latham 2002** and **Hackman 2002**. Doran's 1981 four-page *Management Review* paper made a deceptively simple claim: most stated objectives in organizations are unactionable because they're vague. "Improve customer satisfaction" is unactionable. "Lift CSAT from 3.4 to ≥ 4.0 on the support survey by end of Q2" is. The difference isn't intent — both managers want the same thing. The difference is whether the goal contains the information the executor needs to know whether they're done.

The five criteria — Specific, Measurable, Achievable, Relevant, Time-bound — are *required* fields, not optional ones. The framework's load-bearing claim is that a goal missing any one of them isn't a worse goal; it's an *unactionable* goal. That insight transfers to AI agents verbatim. An agent given an unactionable goal doesn't refuse — it executes the unactionability, often catastrophically. Doran wrote for middle managers; the framework lands cleaner on agents because agents can't tell when a goal is broken.

## How the analyzer works

Input is `GoalRequest` — `goal_id`, `vague_goal`, context, `available_resources`, `known_constraints`, optional `deadline_hint`, optional `framework`. The pipeline runs at three depths:

- **quick** — one LLM call. SMART restatement + per-criterion scores + overall quality bucket.
- **standard** — two LLM calls. Adds the criteria-completeness audit and ranked playbook attachments.
- **forensic** — four LLM calls. Adds the measurement-rigor audit (are success metrics observable, with named instruments) and a per-failure-mode intervention pass with composition handoffs.

```python
from vstack.smart_goal import SMARTGoalGenerator, GoalRequest
goal = SMARTGoalGenerator(llm, mode="standard").run(
    GoalRequest(
        goal_id="onboarding-q2",
        vague_goal="Improve the user onboarding flow.",
        context="B2B SaaS; current activation 35%; benchmark 50%.",
        available_resources=["Mixpanel access", "design team"],
        known_constraints=["no engineering bandwidth"],
        deadline_hint="end of Q2",
    )
)
print(goal.profile_pattern)       # e.g. 'time_bound_missing'
print(goal.to_agent_preamble())   # condensed text the agent literally executes against
```

The single most operationally important field is `kill_criteria`. Goals submitted without explicit stop rules get them generated automatically from the resources and constraints. If the context is too thin to generate them, the gap surfaces as an `open_questions` item the agent must resolve before starting — which is the correct behavior, not a workaround.

## What the playbooks say to do

13 playbooks anchored to specific `(criterion, failure_mode)` keys:

- `(time_bound, no_kill_criterion)` → "Generate a token + wall-clock + retry budget. On trigger: `escalate_to_human` with the most plausible diagnosis-so-far." Anchored in Doran 1981.
- `(achievable, ambition_mismatch)` → "Mark the goal `weak` and surface the resource gap as an `open_questions` item. Do not paper over." Anchored in Locke & Latham 2002.
- `(relevant, vanity_metric)` → "Replace the easy-to-move metric with one connected to the underlying problem. If the connection can't be named, the goal isn't Relevant." Anchored in Hackman 2002.
- `(measurable, no_instrument)` → "Every success metric must name its instrument (Mixpanel funnel, Datadog SLO, eval suite). 'We'll know it when we see it' is not Measurable."

## How it composes with adjacent patterns

SMART Goal is the first call in setup-phase chains. From the composition manifest:

- Upstream: `vstack_grpi` (team-level working agreement) — GRPI sets up the team; SMART specs each member's individual goals.
- Downstream when `profile_pattern=time_bound_missing` → `vstack_yerkes_dodson` (budget pressure) and `vstack_mcgregor` (orchestrator oversight cadence).
- Downstream when `profile_pattern=relevant_mismatch` → `vstack_motivation_traps` (the agent is solving the wrong problem).
- Downstream when `profile_pattern=measurable_thin` → a fresh eval before the run.

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer) — when an AAR's lessons-learned point to a missing-stop-rule failure, SMART Goal is the remediation handoff.

## Comparison to adjacent tools

- **CrewAI `Task` / LangGraph state** require a `description` field but don't enforce SMART criteria. SMART Goal fills that gap and emits a preamble those frameworks can consume.
- **OKR tooling** is a goal-aggregation framework; each KR should be SMART. This pattern produces SMART KRs, not the rollup.
- **vstack_grpi** (Pattern #13) operates at the team level (goals + roles + processes + interactions). SMART Goal operates at the individual-goal level. The two compose.

## Paper outline

1. **Background** — Doran 1981, Locke & Latham 2002, Hackman 2002.
2. **Translation** — vague-goal failure modes in agent runs (unbounded budget, vanity-metric, scope creep, manufactured confidence).
3. **Method** — the SMART spec as the agent's runtime context via `to_agent_preamble()`, the three-mode pipeline, the criteria-completeness + measurement-rigor audits.
4. **Evaluation** — synthetic vague-goal corpus across 3 quality tiers; measure whether SMART-specced agents avoid the unbounded-budget incident class compared to controls.
5. **Limitations** — generation quality depends on the requester's context; thin briefs produce thin specs (mitigated by `open_questions`).
6. **Related work** — LangChain `RunnableConfig`, CrewAI task templates, eval-driven development tooling.
7. **Future work** — multi-goal portfolio specs (the team-of-SMART-goals composition), runtime kill-criterion enforcement at the orchestrator layer.

## Citations

- Doran, G. T. (1981). There's a S.M.A.R.T. way to write management's goals and objectives. *Management Review*, 70(11).
- Locke, E. A., & Latham, G. P. (2002). Building a practically useful theory of goal setting and task motivation. *American Psychologist*, 57(9).
- Hackman, J. R. (2002). *Leading Teams*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-smart-goal analyze --request examples/onboarding_q2.json --mode standard
```

If `profile_pattern=time_bound_missing` shows up, the SMART spec's `kill_criteria` field is the artifact to paste into the agent's system prompt before the next run — and run `vstack_yerkes_dodson` if you want to know whether the budget you generated is humane.
