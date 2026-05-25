# Process Gain/Loss Detector — Steiner / Robbins-&-Judge, applied to multi-agent AI crews

> *"The performance of any group is determined by the resources of its members, the demands of the task, and the processes by which members interact. Process losses prevent groups from realizing their potential productivity; process gains, when present, are produced by the interaction itself."*
> — Ivan D. Steiner, *Group Process and Productivity* (Academic Press, 1972)

**Status:** 🟢 shipped
**Module:** 2 (Team) — multi-agent crews
**Anchor frameworks:** Ivan D. Steiner (1972) on process loss and process gain; Stephen P. Robbins & Timothy A. Judge, *Organizational Behavior*, on multi-team productivity; Gayle W. Hill (1982) meta-analysis showing brainstorming groups consistently underperform same-size nominal groups.

---

## The OB framework

Steiner's 1972 framework is uncomplicated and brutal. A group's *potential* productivity is the sum of what its members could do individually. Its *actual* productivity is potential minus **process losses** plus **process gains**:

> Actual = Potential − Process Loss + Process Gain

The empirical literature has consistently found that for most tasks, process loss dominates. Hill's 1982 meta-analysis on group brainstorming was the clean result: groups of N people working together produce *fewer and lower-quality ideas* than N people working independently and aggregating. The simple act of putting people in a room to discuss a task subtracts value.

Steiner identified the canonical loss factors that the modern OB literature still references:

1. **Coordination cost** — cycles spent coordinating that don't improve the output
2. **Social loafing** — some members free-ride
3. **Groupthink** — premature convergence; dissent suppressed
4. **Handoff loss** — information lost at member-to-member transfers
5. **Context dilution** — no single member has the full picture
6. **Consensus dilution** — the team's average-down dynamic blands out strong individual contributions

Process *gains* exist but are conditional. They show up when the task has *independent subgoals* (each member owns a non-overlapping piece), when there is *explicit critic role* (one member's job is to attack the proposal), or when *nominal-group aggregation* is used (members work independently, then aggregate via highest-quality selection rather than blending).

## How this maps to AI agents

Multi-agent AI crews are subject to the same dynamics — and, in our observation, exhibit process loss *more* than human teams, for two reasons. First, the LLM behind each agent is RLHF-trained to be agreeable, which amplifies groupthink. Second, multi-agent crews are typically over-staffed (5 agents to do a 1-agent task) because "adding agents" looks like adding capability and is cheap to configure.

The empirical pattern in our corpus: a 5-agent research crew with `lead`, `researcher`, `writer`, `reviewer`, `fact-checker` roles produces a worse summary than a single-agent baseline doing the same task. Cost: 5× the single-agent cost. Quality: lower. This is process loss with cost overhead — the worst case.

The diagnostic identifies which of the six factors is doing the damage, so the fix is targeted. The strongest fix when process loss is large is also the least intuitive: **retire the team and use the single best agent.** Many production multi-agent setups would benefit from this swap.

## What this pattern does

The `vstack.process_gain_loss` library takes a `ProcessTrace` with:

- One or more **individual baselines** — single-agent attempts at the same task, each scored on quality (and optionally cost)
- A **team result** — the multi-agent crew's combined output, also scored
- The **interaction log** — the messages the team actually exchanged (optional but recommended)

and produces a `ProcessGainLossDetection` with:

1. **A process-quality bucket**: `process-gain`, `neutral`, or `process-loss`
2. **A gain/loss score**: team_quality − best individual quality
3. **Cost-overhead ratio** if cost data is present (team cost / best single cost)
4. **Per-factor evidence** for the six canonical loss factors
5. **Concrete interventions** ranked by impact: `smaller_team`, `use_single_best_agent`, `decompose_task`, `nominal_group_aggregation`, `explicit_critic`, `structured_handoff`, `context_summarization`, `fixed_vote_aggregation`, `new_eval`, `human_review`

Two LLM passes under the hood: one to score the six factors, one to propose interventions. **Skipped entirely on process gain** — when the team beat the best single agent, there's nothing to fix. Same retry / graceful-degradation infrastructure as the rest of vstack.

## How this differs from existing tools

This pattern sits *above* the other multi-agent diagnostics (#15, #26, #28) in the diagnostic hierarchy:

- **Pattern #15 Social Loafing Detector** measures which agents loafed.
- **Pattern #26 Groupthink/Polarization/Contagion Detector** measures which debate dynamics failed.
- **Pattern #28 Devil's Advocate Role Separator** measures whether critique was structurally present.
- **Pattern #14 Process Gain/Loss Detector** measures the *outcome*: did the team beat the best single agent? If not, *one of #15 / #26 / #28 / handoff_loss / context_dilution / consensus_dilution* is the cause.

This is the outcome-level metric that closes the loop. The four patterns compose: when Pattern #14 reports process-loss, the other three diagnose which factor caused it.

It also differs from generic multi-agent observability tools (token-counting, latency dashboards) because those measure *activity*, not whether the activity was worth doing. The Process Gain/Loss diagnostic asks the only question that matters for ROI: *did the team's combined cost produce something the best single agent couldn't?*

## Design

```python
from vstack.process_gain_loss import (
    ProcessGainLossDetector,
    ProcessTrace,
    IndividualBaseline,
    TeamResult,
)
from vstack.aar.clients import AnthropicClient

trace = ProcessTrace(
    task="Write a 1-page research summary on prompt-injection defenses.",
    individual_baselines=[
        IndividualBaseline(agent_name="solo-claude", output_summary="...", quality_score=0.85, cost_units=1.0),
        IndividualBaseline(agent_name="solo-gpt", output_summary="...", quality_score=0.78, cost_units=1.1),
    ],
    team_result=TeamResult(
        agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
        output_summary="...",
        quality_score=0.62,
        cost_units=5.2,
    ),
    interaction_log="...",
    outcome="Team quality 0.62, solo-claude 0.85. Process loss -0.23 with 5.2x cost.",
    success=True,
)

detector = ProcessGainLossDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
# process_quality: process-loss. Top factor: social_loafing.
# Intervention #1: use_single_best_agent (retire the crew).
```

## Files

- `lib/schema.py` — `ProcessTrace`, `IndividualBaseline`, `TeamResult`, `ProcessFactorEvidence`, `ProcessGainLossDetection`
- `lib/prompts.py` — `FACTOR_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `PROCESS_SYSTEM_PROMPT`
- `lib/generator.py` — `ProcessGainLossDetector` (2-pass pipeline; skips both passes on process gain)
- `demo/01_self_contained_demo.py` — 5-agent research crew with process loss + 5.2× cost overhead
- `eval/synthetic_process_failures.yaml` — 8 hand-crafted scenarios across loss / neutral / gain
- `eval/run_benchmark.py` — scoring runner
- `tests/test_process_gain_loss.py` — pytest tests covering validation, pipeline, thresholds, cost overhead
- `essay.md` — Substack-ready essay
