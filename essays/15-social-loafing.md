# Social Loafing — your crew has a fact-checker who never fact-checks

*#15 vstack_social_loafing* · *Module 2 — Multi-agent team*

> A 5-agent research crew assembled to write a report on prompt-injection defenses. The researcher gathered eight papers, proposed a four-section structure, and *explicitly flagged* one claim — "Apollo 2026 reports 92% reduction in attack-success-rate" — as `needs verification`. The lead approved. Writer's contribution: "Drafting per researcher's framing." Reviewer: "Structure LGTM. Proceed." Fact-checker: "Citations look fine to me." The report shipped. Two days later someone noticed the Apollo paper actually reported 62%, not 92%. The researcher had done their job. The fact-checker — whose entire role existed for exactly this case — had produced zero tool calls and one four-word rubber-stamp. The shipped report would have been safer with *no fact-checker box at all* than with an empty one that conveyed false authority.

## What the pattern catches

When multiple agents share an output, contribution becomes pooled, individual effort becomes opaque, and per-agent work drops by ~50% — exactly as Latané, Williams & Harkins measured in human groups in 1979. In agent crews the dynamic is worse than in human teams because RLHF-trained models default to the linguistic shape of whatever the role suggests. The "reviewer" role suggests reviewers often say "looks good"; the model generates "looks good." No conscious choice to loaf. No embarrassment. No peer noticing. The loafing is *structural*.

Three failure modes recur:

- **Rubber-stamp loafing** — reviewer/fact-checker/QA agents that respond "Approved" with zero substantive evaluation. The most operationally dangerous because the existence of an empty verification role conveys verification that didn't happen.
- **Paraphrase loafing** — writer agents downstream of researchers whose entire output is restating upstream work. Common when downstream roles lack non-overlapping deliverables.
- **Absent loafing** — agents nominally on the team who never produce output. Common in over-staffed crews.

The analyzer answers: *which agents loafed, on what evidence, and what intervention restores accountability?*

## Why the OB literature is the right reference

The diagnostic is anchored in Latané, Williams & Harkins 1979 (the original "Many Hands Make Light the Work" experiments), Karau & Williams 1993 (the meta-analytic confirmation), Williams, Harkins & Latané 1981 (identifiability-as-deterrent), Comer 1995 (real-work-groups model), Hackman 2002 (team-effectiveness anchor), Salas et al. 2018 (modern review), Wang et al. 2023 on cooperative LLM agents, and Ingham et al. 1974 cross-referencing the Ringelmann effect.

**Latané-Williams-Harkins's 1979 finding** was that loafing scales with three factors: anonymity of contribution, group size, and pooled evaluation. The 50% effort drop in groups of six replicates across hundreds of studies. Karau & Williams's 1993 meta-analysis confirmed the effect and named the intervention pattern: *individual accountability collapses loafing*. Once each contributor's specific work is observable and evaluable, the dynamic reverses.

The transfer to agent crews is exact because crews exhibit all three loafing-amplifying conditions by default: shared output, orchestrator-level evaluation, over-staffing as the default deployment posture.

## How the analyzer works

Input is `MultiAgentTaskTrace` — `team_id`, `task`, agent roster, `AgentMessage` log (each tagged with `from_agent` + `message_type`: proposal / critique / approval / rubber_stamp / paraphrase / tool_call / observation / decision / handoff / question / other), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Per-agent contribution scores + loafing-quality bucket.
- **standard** — two LLM calls. Adds `AgentContribution` evidence per agent and ranked interventions targeting the loafing agents.
- **forensic** — four LLM calls. Adds `AnonymityAudit`, `FreeRidingChain` (who's free-riding off whose work), and composition handoffs.

```python
from vstack.social_loafing import SocialLoafingAnalyzer, MultiAgentTaskTrace, AgentMessage
detection = SocialLoafingAnalyzer(llm, mode="forensic").run(
    MultiAgentTaskTrace(
        team_id="research-crew-001",
        task="Compile a report on prompt-injection defenses.",
        agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
        messages=[
            AgentMessage(from_agent="researcher", message_type="tool_call", content="..."),
            AgentMessage(from_agent="reviewer", message_type="rubber_stamp", content="LGTM."),
            AgentMessage(from_agent="fact-checker", message_type="rubber_stamp", content="Citations look fine."),
        ],
        outcome="Report shipped with the flagged claim wrong.",
        success=True,
    )
)
print(detection.loafing_quality)   # 'severe-loafing'
print(detection.gini_coefficient)  # ~0.65 — one agent did most of the work
```

The Gini coefficient is **the cleanest crew-level signal**. Gini ≈ 0 means evenly distributed work; Gini ≈ 1 means one agent did everything. Above ~0.5 is concerning.

## What the playbooks say to do

Ten interventions, ranked by impact on the dominant loafing pattern:

- `individual_accountability` → "For every numeric claim, the fact-checker must (1) state the claim, (2) execute the verifying tool call, (3) paste the verifying evidence. A response without these three elements is invalid." (Karau & Williams 1993; Williams/Harkins/Latané 1981.) The textbook Latané fix — make verification *observable*.
- `assign_subgoals` → Each agent gets a named, non-overlapping deliverable. (Latané 1979.)
- `decompose_task` → Counters paraphrase-loafing by giving downstream agents original work.
- `smaller_team` / `remove_loafer` → Loafing scales with size; shrink the crew or retire structurally redundant roles.
- `per_agent_evaluation` → Score agents individually rather than the crew as a unit.
- `explicit_critic_assignment` → Chains into `vstack_devils_advocate` (#28).

## How it composes with adjacent patterns

Social Loafing sits in the **multi-agent diagnostic stack** between Process Gain/Loss (#14, outcome-level) and Devil's Advocate (#28, role-structure):

- `vstack_process_gain_loss` reports *whether* the team beat the best single agent. If it didn't, Social Loafing answers *which agents are dragging quality down*.
- `vstack_lencioni` (#17) reports the team-shape dysfunction; Social Loafing is the per-agent contribution diagnostic that operationalizes the "avoidance of accountability" layer.
- `vstack_devils_advocate` (#28) reports whether the critic role exists at all; Social Loafing measures whether the critic (or any role) is actually doing its work.
- `vstack_superflocks` (#16) reports whether the *orchestrator* concentrates routing; Social Loafing reports whether the *agents* contribute. They're complements — if routing concentration is high, agents on the unrouted side are loafing by *system design*, not by their own behavior.

Cross-link to [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Token-usage-per-agent dashboards** measure *activity*; an agent producing 1000 tokens of "LGTM" has high activity and zero contribution.
- **LLM-as-judge** scores the product; it doesn't tell you which agents earned their seat.
- **`vstack_process_gain_loss`** measures outcome; Social Loafing measures cause.

## Paper outline

1. **Background** — Latané/Williams/Harkins 1979, Karau & Williams 1993, Comer 1995, Hackman 2002, Salas 2018, Ringelmann via Ingham 1974.
2. **Translation** — RLHF agreement-bias amplifies loafing; the three loafing-amplifying conditions are crew defaults.
3. **Method** — message-type tagging, contribution-share scoring, Gini computation, intervention ranking.
4. **Evaluation** — synthetic 5-agent crew benchmark with planted loafers; measure precision/recall of loafer identification across rubber-stamp, paraphrase, and absent patterns.
5. **Limitations** — short message logs are noisy; the pattern needs >15 inter-agent messages to discriminate cleanly.
6. **Related work** — CrewAI/AutoGen team metrics; Wang et al. 2023.
7. **Future work** — longitudinal loafing drift across repeated runs with the same crew.

## Citations

- Latané, B., Williams, K., & Harkins, S. (1979). Many hands make light the work: The causes and consequences of social loafing. *Journal of Personality and Social Psychology*, 37(6), 822-832.
- Karau, S. J., & Williams, K. D. (1993). Social loafing: A meta-analytic review and theoretical integration. *JPSP*, 65(4), 681-706.
- Williams, K., Harkins, S., & Latané, B. (1981). Identifiability as a deterrent to social loafing. *JPSP*, 40(2), 303-311.
- Comer, D. R. (1995). A model of social loafing in real work groups. *Human Relations*, 48(6), 647-667.
- Hackman, J. R. (2002). *Leading Teams*. HBS Press.
- Salas, E., et al. (2018). Science of team performance. *Annual Review of Org Psych*, 5, 593-620.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-social-loafing analyze --trace examples/research_crew.json --mode forensic
```

If Social Loafing returns `severe-loafing` with rubber-stamp loafers in verification roles, the cleanest intervention is `individual_accountability` — make verification observable. Chain into `vstack_process_gain_loss` next to confirm whether the loafing is actually dragging the crew below its best single agent.
