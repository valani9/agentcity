# Process Gain/Loss — did the crew beat the best single agent?

*#14 vstack_process_gain_loss* · *Module 2 — Multi-agent team*

> A 5-agent research crew (`lead`, `researcher`, `writer`, `reviewer`, `fact-checker`) shipped a polished one-page summary of the prompt-injection-defense literature. Three numbers told the rest of the story: solo Claude on the same task scored 0.85; solo GPT scored 0.78; the crew scored 0.62. The team's output was worse than either single-agent baseline — and it cost 5.2× more. The team had been running in production for two months with a budget line item and an owner. No dashboard flagged anything wrong because every dashboard measured *activity* (token throughput, message counts), not *value-relative-to-counterfactual*. The crew was the wrong tool. Nobody knew until Steiner's arithmetic was applied.

## What the pattern catches

Multi-agent observability is dominated by activity metrics — tokens consumed, messages exchanged, latency per turn. None of those answer the only question that justifies the multi-agent architecture in the first place: *did the team's combined cost produce something the best single agent couldn't?* Ivan Steiner's 1972 *Group Process and Productivity* gave the canonical formulation:

    Actual = Potential − Process Loss + Process Gain

Six decades of replication on human teams — starting with Hill 1982's brainstorming meta-analysis — converge on one finding: for most tasks, **process loss dominates process gain**. Groups don't add value by default; they subtract it. Multi-agent AI crews exhibit the same dynamics, often worse, because RLHF-trained models are agreement-biased and crews are usually over-staffed.

vstack_process_gain_loss is the **outcome-level** diagnostic for multi-agent crews. The analyzer answers: *did this team beat its best individual? If not, which of Steiner's six loss factors did the damage?*

## Why the OB literature is the right reference

The diagnostic is anchored in Steiner 1972 (the canonical six-factor framework), Hill 1982 (the brainstorming meta-analysis), Hackman & Vidmar 1970 (group-size effects), Diehl & Stroebe 1987 (the productivity-loss-in-brainstorming finding), Salas et al. 2018 (modern review), and Wang et al. 2023 on cooperative LLM agents.

**Steiner's 1972 contribution** was naming the six canonical loss factors that the modern OB literature still uses: coordination cost, social loafing, groupthink, handoff loss, context dilution, consensus dilution. Each is a *named mechanism* by which the act of working together subtracts value. Process *gains* exist but are conditional — they show up when subgoals are independent (each member owns a non-overlapping piece), when there's an explicit critic role, or when nominal-group aggregation is used (members work independently, then a judge selects rather than blends).

The transfer to agent crews is exact. Each of the six factors has a textbook signature in inter-agent message logs. Handoff loss looks like a writer paraphrasing a researcher without preserving qualifications. Consensus dilution looks like a final report that's recognizably the mean of two strong positions with neither's argument intact.

## How the analyzer works

Input is `ProcessTrace` — one or more `IndividualBaseline` runs (each scored 0-1 on quality, optionally with cost), a `TeamResult` (also scored), an optional interaction log, and the outcome. The pipeline:

- **quick** — one LLM call. Process-quality bucket + dominant factor + top intervention.
- **standard** — two LLM calls. Per-factor `ProcessFactorEvidence` (each scored 0-1 with severity + evidence quotes) + ranked interventions.
- **forensic** — four LLM calls. Adds `InteractionLogAudit` (round-by-round dynamics), `CounterfactualAudit` ("what would the best single agent have done differently?"), and composition handoffs.

```python
from vstack.process_gain_loss import ProcessGainLossAnalyzer, ProcessTrace, IndividualBaseline, TeamResult
detection = ProcessGainLossAnalyzer(llm, mode="forensic").run(
    ProcessTrace(
        task="Write a 1-page research summary on prompt-injection defenses.",
        individual_baselines=[
            IndividualBaseline(agent_name="solo-claude", quality_score=0.85, cost_units=1.0),
            IndividualBaseline(agent_name="solo-gpt", quality_score=0.78, cost_units=1.1),
        ],
        team_result=TeamResult(
            agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
            quality_score=0.62,
            cost_units=5.2,
        ),
        outcome="Team -0.23 vs best single. 5.2x cost.",
        success=True,
    )
)
print(detection.process_quality)   # 'process-loss'
print(detection.dominant_factor)   # 'social_loafing' or 'consensus_dilution', etc.
```

The intervention pass is **skipped entirely on process gain** — when the team actually beat the best single, there's nothing to fix.

## What the playbooks say to do

The intervention catalog runs in order of impact:

- `use_single_best_agent` → "When the gain/loss score is large-negative and cost overhead is large-positive, retire the crew. Steiner's framework is unambiguous: if process loss dominates and the task lacks non-overlapping subgoals, the team is the wrong tool." (Steiner 1972; Hill 1982.)
- `smaller_team` → "Loss scales with size. A 3-agent crew loses less than a 5-agent crew." (Hackman & Vidmar 1970.)
- `decompose_task` → "Process loss collapses when each agent owns a non-overlapping subgoal — section-1-author, section-2-author beats lead-writer-reviewer-fact-checker." (Steiner 1972.)
- `nominal_group_aggregation` → "Agents work independently; a separate judge selects the best output rather than blending. The classical process-gain construction." (Diehl & Stroebe 1987.)
- `explicit_critic` → Chains into `vstack_devils_advocate` (Pattern #28).
- `structured_handoff` + `context_summarization` → Counter the handoff-loss and context-dilution factors.

## How it composes with adjacent patterns

Process Gain/Loss sits at the **top of the multi-agent diagnostic hierarchy**. It reports the *outcome*; the lower-level patterns diagnose the *cause*:

- `vstack_social_loafing` (#15) → which agents loafed.
- `vstack_groupthink_polarization` (#26) → which debate dynamics failed.
- `vstack_devils_advocate` (#28) → was critique structurally present?
- `vstack_lencioni` (#17) → which dysfunction class is the team showing?

If Pattern #14 returns `process-loss` with `dominant_factor=social_loafing`, run #15. If `dominant_factor=consensus_dilution`, run #26. If Pattern #14 reports process gain, none of the lower diagnostics are urgent.

Cross-link to [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Multi-agent observability dashboards** (LangSmith, CrewAI telemetry, Helicone team metrics) measure *activity*, not value-relative-to-counterfactual.
- **LLM-as-judge** measures the *final product* against a rubric; it doesn't compare to the best single agent — the cost-justifying question.
- **`vstack_social_loafing`** measures contribution shares; Process Gain/Loss measures outcome. Both compose.

## Paper outline

1. **Background** — Steiner 1972, Hill 1982, Diehl & Stroebe 1987, Hackman & Vidmar 1970, Salas 2018.
2. **Translation** — agent crews as bona fide groups subject to the six loss factors.
3. **Method** — paired-baseline scoring, six-factor evidence pass, intervention ranking, deterministic gain/loss arithmetic.
4. **Evaluation** — paired benchmark: same task, multi-agent vs best-of-N single-agent; measure how often the team beats its best member across task classes (research, code, creative).
5. **Limitations** — requires individual baselines; cost units need to be consistent across runs.
6. **Related work** — CrewAI / AutoGen / LangGraph multi-agent evaluation; Wang et al. 2023.
7. **Future work** — adaptive routing: shrink the team when Pattern #14 returns repeated process-loss.

## Citations

- Steiner, I. D. (1972). *Group Process and Productivity*. Academic Press.
- Hill, G. W. (1982). Group versus individual performance: Are N + 1 heads better than one? *Psychological Bulletin*, 91, 517-539.
- Hackman, J. R., & Vidmar, N. (1970). Effects of size and task type on group performance and member reactions. *Sociometry*, 33, 37-54.
- Diehl, M., & Stroebe, W. (1987). Productivity loss in brainstorming groups. *JPSP*, 53, 497-509.
- Salas, E., et al. (2018). Science of team performance. *Annual Review of Org Psych*, 5, 593-620.
- Wang, X., et al. (2023). Cooperative LLM agents. (LLM multi-agent analog.)

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-process-gain-loss analyze --trace examples/research_crew.json --mode forensic
```

If Pattern #14 returns `process-loss` with high cost overhead, the strongest fix is often `use_single_best_agent`. If you need the team for organizational reasons, chain into `vstack_social_loafing` to identify which roles to consolidate first.
