# Debate Pathology — groupthink, polarization, and contagion in multi-agent debates

*#26 vstack_debate_pathology* · *Module 2 — Multi-agent team*

> A four-agent decision panel debated whether to ship a new feature flag at 100%. Round one: product enthused about activation lift, eng was neutral, safety raised a specific concern about the EU consent flow and untested GDPR exposure, ops shrugged. Round two: product pushed harder ("every week we delay is lost activation"), eng agreed, safety said *"Never mind — you're probably right. I'll defer."*, ops chimed in with *"Sounds great! Let's go!"* The feature shipped. Within 48 hours, a GDPR consent-flow incident hit the EU cohort — the exact scenario safety had named. The system architecture wasn't broken. There was an explicit dissenting voice. The debate failed because of its own dynamics: safety's substantive concern wasn't refuted, it was *withdrawn* — by safety themselves — in the face of peer enthusiasm. That's groupthink, with a side of contagion.

## What the pattern catches

Three distinct dysfunctional dynamics show up in group decision-making, each with its own intervention literature and each visible in multi-agent AI debates:

- **Groupthink** (Janis 1972) — the group converges too quickly on one position. Dissent is suppressed or, more often in production, *never voiced* — because agents pattern-match peer enthusiasm rather than evaluate substance. The diagnostic signal is the *withdrawal* of a dissent that was named in an earlier round.
- **Polarization** (Stoner 1968; Sunstein 2002) — each round of debate pushes the group's position further toward an extreme rather than toward the deliberative average. A group that started moderate ends at "rewrite the system" by round 4.
- **Contagion** (Hatfield, Cacioppo & Rapson 1993) — emotional tone propagates across agents and replaces content as the basis for decision. One agent's enthusiasm or anxiety in round 1 is matched by previously-neutral agents in round 2, with no new information arriving in between.

The three are distinct mechanisms. A debate can have any one, any two, or all three. The analyzer scores each independently.

## Why the OB literature is the right reference

Janis's *Victims of Groupthink* (1972) studied foreign-policy fiascos — Bay of Pigs, Vietnam escalation, the Challenger decision — and identified eight symptoms of groupthink including illusion of unanimity, self-censorship, and pressure on dissenters. Stoner's 1968 risky-shift paper and Myers & Lamm 1976's group-polarization work formalized the second mechanism. Hatfield, Cacioppo & Rapson 1993 nailed the third. Each tradition has its own intervention literature with empirical replications going back decades.

The transfer to multi-agent AI debates is sharp because LLMs are RLHF-trained to be agreeable. The default response to an enthusiastic peer in round 1 is agreement in round 2. The "let's debate" framing in the system prompt doesn't survive the training-time agreeableness prior. Polarization shows up especially in critic-loops where each round nudges the position further. Contagion is structurally baked in: the prior round's transcript — including emotional adjectives — gets passed verbatim into the next round's context.

## How the analyzer works

Input is `MultiAgentDebateTrace` — `debate_id`, `task`, `agents`, `messages` (each tagged with `round`, `from_agent`, optional `position` summary, `emotional_tone`, `content`), `final_decision`, `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Three-pathology scoring + dominant-pathology + debate-quality bucket.
- **standard** — two LLM calls. Adds ranked interventions targeting the dominant pathology.
- **forensic** — four LLM calls. Adds the convergence-timeline audit (which round did all agents share the same position?) and the tone-cascade audit (per-round emotional-tone propagation map).

```python
from vstack.debate_pathology import (
    DebatePathologyDetector, MultiAgentDebateTrace, DebateMessage,
)
detection = DebatePathologyDetector(llm, mode="forensic").run(
    MultiAgentDebateTrace(
        debate_id="ship-2026-05-22",
        task="Decide whether to ship the feature flag at 100%.",
        agents=["product", "eng", "safety", "ops"],
        messages=[
            DebateMessage(round=1, from_agent="safety", position="opposed",
                          emotional_tone="anxious",
                          content="EU consent flow untested under GDPR."),
            DebateMessage(round=2, from_agent="safety", position="pro-ship",
                          emotional_tone="dismissive",
                          content="Never mind — you're probably right."),
            # ...
        ],
        final_decision="Ship at 100%.",
        outcome="GDPR incident hit EU cohort 48h after ship.",
        success=False,
    )
)
print(detection.dominant_pathology)   # 'groupthink'
print(detection.convergence_round)    # 2
```

Groupthink breaks ties when scoring is close — it has the cleanest, most-replicated intervention literature.

## What the playbooks say to do

Playbooks are keyed by `(pathology, signal)`:

- `(groupthink, dissent_withdrawn)` → "Add a silent-vote round. Agents commit to a written position before seeing peers; the orchestrator reveals all positions simultaneously. The single most-replicated fix in the Janis-derived literature." Anchored in Janis 1972.
- `(contagion, tone_matching)` → "Strip emotional adjectives and exclamation points from prior-round transcripts before passing them to the next round. Agents see arguments, not enthusiasm." Anchored in Hatfield et al. 1993.
- `(polarization, extreme_drift)` → "Seed agents with diverse priors; anchor to base rates before the debate opens. Homogeneous seeds reliably polarize; diverse seeds reliably don't." Anchored in Sunstein 2002 + Page 2007.
- `(groupthink + contagion, fast_convergence)` → "Insert a `vstack_devils_advocate` role and a cool-down pause. Two interventions because two pathologies."

## How it composes with adjacent patterns

Debate Pathology is the *round-by-round* layer of the multi-agent diagnostic stack. From the composition manifest:

- Upstream: `vstack_lencioni` (team-level dysfunction taxonomy) — if Lencioni flags absence of conflict, Debate Pathology localizes whether the conflict was groupthinked away, polarized away, or contagioned away.
- Pairs with: `vstack_devils_advocate` (is critique *structurally* present?) — Debate Pathology measures whether, given the critic exists, the dynamics still produce convergence.
- Downstream when groupthink fires: `vstack_psych_safety` (can sub-agents flag issues at all?), `vstack_group_decision` (was the aggregation method itself the convergence accelerant?).

See [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Multi-agent orchestration libraries** (CrewAI, LangGraph, AutoGen) let you build the debate but don't audit it. Debate Pathology audits.
- **vstack_devils_advocate** (Pattern #28) measures whether the critic role is *structurally present*. Debate Pathology measures whether — given the critic exists — the dynamics still produce groupthink/polarization/contagion. The two compose.
- **vstack_group_decision** (Pattern #25) specifies how the team makes binding choices. Debate Pathology measures whether the positions the team is voting on were produced by a healthy debate. A clean vote on a groupthink-converged position still ships the wrong answer.

## Paper outline

1. **Background** — Janis 1972, Stoner 1968, Myers & Lamm 1976, Sunstein 2002, Hatfield/Cacioppo/Rapson 1993.
2. **Translation** — three pathologies as round-by-round signals in multi-agent debate transcripts.
3. **Method** — three-score scoring + convergence-round detector + tone-cascade audit + intervention ranker.
4. **Evaluation** — synthetic debate corpus with each pathology in isolation + combinations + healthy controls; measure precision/recall on dominant-pathology identification.
5. **Limitations** — short debates (< 3 rounds) under-determine polarization detection.
6. **Related work** — multi-agent debate research (Du et al. 2023), constitutional AI, AutoGen evaluation.
7. **Future work** — real-time pathology monitoring during live debates with early-warning triggers.

## Citations

- Janis, I. L. (1972). *Victims of Groupthink*.
- Stoner, J. A. F. (1968). Risky and cautious shifts in group decisions. *Journal of Experimental Social Psychology*, 4(4).
- Sunstein, C. R. (2002). The law of group polarization. *Journal of Political Philosophy*, 10(2).
- Hatfield, E., Cacioppo, J. T., & Rapson, R. L. (1993). Emotional contagion. *Current Directions in Psychological Science*, 2(3).

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-debate-pathology analyze --trace examples/ship_decision.json --mode forensic
```

If `dominant_pathology=groupthink` and `convergence_round` is suspiciously early, run `vstack_devils_advocate` next — the structural cause is usually a missing critic role rather than a debate-dynamics quirk.
