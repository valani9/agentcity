# SMART Goal Generator — Doran's 1981 framework, applied to AI agent goal-setting

> *"How do you write meaningful objectives? — that is, frame a statement of results to be achieved. Managers are confused by all the verbiage that has been provided in the literature describing goal setting. Ideally speaking, each corporate, department, and section objective should be Specific, Measurable, Achievable, Relevant, and Time-bound."*
> — George T. Doran, *There's a S.M.A.R.T. Way to Write Management's Goals and Objectives* (Management Review, 70(11), 1981)

**Status:** 🟢 shipped
**Module:** 2 (Team) — applies anywhere an agent or agent-team accepts a goal
**Anchor framework:** George T. Doran, *Management Review* (1981). The SMART acronym is the most-cited goal-setting framework in management literature. Influenced by Locke & Latham's goal-setting theory (1968-2002).

---

## The OB framework

Doran's 1981 paper made a deceptively simple claim: most stated objectives in organizations are unactionable because they're vague. "Improve customer satisfaction" is unactionable. "Lift CSAT from 3.4 to >=4.0 on the support survey by end of Q2" is. The difference isn't the *intent* — both managers want the same thing. The difference is whether the goal contains the information the person doing the work actually needs to know whether they're done.

Doran's five criteria:

| Criterion | What it checks | A failing example | A passing example |
|---|---|---|---|
| **Specific** | Well-defined target, not a category | "Improve onboarding" | "Reduce workspace-setup drop-off from 65% to <40%" |
| **Measurable** | Objective completion criterion | "Get better at X" | "Pass when metric Y >= Z on a 7-day rolling window" |
| **Achievable** | Within reach given current resources | "Eliminate all churn" | "Reduce churn from 8% to 6%" |
| **Relevant** | Connected to underlying problem | "Increase email open rate" (when churn is the problem) | "Reduce churn-attributed cancellation reasons" |
| **Time-bound** | Has a deadline or budget | "Someday" | "End of Q2 (2026-06-30)" |

The framework's enduring usefulness is the *Achievable* criterion specifically. The other four are mechanical (anyone can append a deadline to a goal); achievable forces an honest accounting of resources vs. ambition. Goals that fail the achievable check should be marked as such and flagged for open questions, not papered over.

## How this maps to AI agents

AI agents are exquisitely vulnerable to vague goals. Given "improve the website," a frontier-model agent will produce ambitious-sounding plans, spend budget exploring tangentially-related directions, and produce work the user doesn't recognize as progress. The agent has no internal sense that the goal is unactionable. It will burn through its token budget executing on the vagueness.

Three specific failure modes the SMART spec catches:

1. **Unbounded budget consumption.** The single biggest agent-incident class in our corpus is "agent ran for 63 hours / 4200 dollars / 25 retries because no kill criterion was defined." Doran's framework treats kill criteria as a first-class output, not an afterthought.
2. **Vanity-metric optimization.** Agents handed vague goals will pick whatever metric is easiest to move (open rates, message counts, surface-level engagement). The Relevant criterion forces an explicit connection to the underlying problem.
3. **Scope creep.** Without explicit completion criteria, agents keep extending the work — "I could also..." — long past the point a human would have shipped. The completion criteria checklist makes "done" observable.

## What this pattern does

The `vstack.smart_goal` library takes a `GoalRequest` containing a vague goal plus context, available resources, known constraints, and an optional deadline hint, and produces a `SMARTGoal` with:

1. **A single-paragraph SMART restatement** of the goal
2. **Per-criterion statements** (one per SMART dimension) with self-reported quality scores
3. **A checklist of completion criteria** — observable conditions for "done"
4. **Success metrics** — concrete metric name + target + measurement method
5. **Kill criteria** — conditions under which the agent ABANDONS the goal (with action-on-trigger: usually `escalate_to_human` or `rollback_and_escalate`)
6. **A concrete deadline** — ISO date, duration, or token/cost budget
7. **Open questions** — gaps the agent should resolve before starting (rather than papering over)
8. **An overall SMART score** in [0.0, 1.0] and a quality bucket: `strong` / `acceptable` / `weak`

The output also exposes `to_agent_preamble()` which renders a condensed text block to prepend to the working agent's system prompt — so the agent literally executes the SMART version, not the vague original.

Single LLM pass under the hood; the generator post-processes the response to fill missing criteria, recompute the overall score if absent, and reconcile the quality bucket with the score. Same retry / graceful-degradation infrastructure as the rest of vstack.

## How this differs from existing tools

- **#13 GRPI Working Agreement Generator** is generative like this pattern but operates at the *team* level (goals + roles + processes + interactions). #24 operates at the *individual goal* level. They compose: GRPI sets up the team; SMART specs the individual goals each team member owns.
- **Locke & Latham's goal-setting research** establishes the empirical case for specific + challenging goals over vague + easy ones; Doran's framework is the operationalization.
- **OKRs** are a goal-aggregation framework (Objectives + Key Results); each KR should be SMART. This pattern produces SMART KRs.
- Other agent-frameworks (CrewAI Tasks, LangGraph state) require a `description` field but don't enforce SMART criteria. This pattern fills that gap.

## Design

```python
from vstack.smart_goal import SMARTGoalGenerator, GoalRequest
from vstack.aar.clients import AnthropicClient

request = GoalRequest(
    goal_id="onboarding-q2",
    vague_goal="Improve the user onboarding flow.",
    context="B2B SaaS; current activation 35%; benchmark 50%.",
    available_resources=["Mixpanel access", "design team"],
    known_constraints=["no engineering bandwidth"],
    deadline_hint="end of Q2",
    framework="crewai",
)

generator = SMARTGoalGenerator(llm_client=AnthropicClient())
goal = generator.run(request)
print(goal.to_markdown())  # Full spec for humans
print(goal.to_agent_preamble())  # Condensed for agent system prompt
```

## Files

- `lib/schema.py` — `GoalRequest`, `SMARTCriterion`, `SuccessMetric`, `KillCriterion`, `SMARTGoal`
- `lib/prompts.py` — `SMART_GENERATION_PROMPT`, `SMART_SYSTEM_PROMPT`
- `lib/generator.py` — `SMARTGoalGenerator` (single-pass pipeline with robust post-processing)
- `demo/01_self_contained_demo.py` — vague "improve onboarding" -> full SMART spec with stub client
- `eval/synthetic_smart_requests.yaml` — 8 hand-crafted vague-goal scenarios across all 3 quality levels
- `eval/run_benchmark.py` — scoring runner
- `tests/test_smart_goal.py` — pytest tests covering validation, pipeline, schema-fill, malformed inputs, quality reconciliation
- `essay.md` — Substack-ready essay
