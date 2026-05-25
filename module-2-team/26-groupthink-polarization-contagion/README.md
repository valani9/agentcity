# Groupthink / Polarization / Contagion Detector — three classic debate pathologies, applied to multi-agent AI debates

> *"Groupthink — a mode of thinking that people engage in when they are deeply involved in a cohesive in-group, when the members' strivings for unanimity override their motivation to realistically appraise alternative courses of action."*
> — Irving L. Janis, *Victims of Groupthink* (Houghton Mifflin, 1972)

**Status:** 🟢 shipped
**Module:** 2 (Team) — multi-agent debate
**Anchor frameworks:**
- **Groupthink**: Irving L. Janis, *Victims of Groupthink* (Houghton Mifflin, 1972)
- **Polarization**: James A. F. Stoner (1968) on "risky shift"; group-polarization literature (Myers & Lamm, 1976)
- **Contagion**: Elaine Hatfield, John Cacioppo & Richard Rapson, *Emotional Contagion* (Cambridge University Press, 1993)

---

## The OB framework

Three distinct dysfunctional dynamics show up in group decision-making, all extensively documented, all with their own intervention literatures:

| Pathology | Mechanism | The signal in a debate |
|---|---|---|
| **Groupthink** | The group converges too quickly on one position. Dissent gets suppressed (or never voiced). | Illusion of unanimity by round 2. A dissenting agent withdraws ("never mind, you're probably right"). No agent steel-mans alternatives. |
| **Polarization** | Each round of debate pushes the group's position further toward an extreme, rather than toward the deliberative average of starting positions. | Group started moderate; each round shifts further in one direction. Risky-shift or cautious-shift. Agents who started neutral end up enthusiastic. |
| **Contagion** | Emotional tone propagates across agents and replaces content as the basis for decision. | One heated/anxious/enthusiastic tone in round 1 is matched by previously-neutral agents in round 2. Tone-matching overrides argument-matching. |

The three are *distinct*. A debate can have groupthink without polarization (the group converges fast but at the moderate average). It can have polarization without groupthink (genuine extended debate that nonetheless drifts to an extreme). It can have contagion without either (the group disagrees in substance but all match the same emotional tone). Real debates often have two or three at once.

## How this maps to AI agents

Multi-agent AI debates — especially in production crews where N agents are asked to "discuss" a decision before the orchestrator chooses — exhibit all three pathologies routinely:

- **Groupthink** is the default mode. LLMs are RLHF-trained to be agreeable. When agent B sees agent A's enthusiastic position in round 1, agent B's round-2 response defaults to agreement. The "let's debate" framing doesn't survive the training-time agreeableness prior.
- **Polarization** shows up especially in critic-loops. Each critique round nudges the position further. An agent that started moderate ends up at "we should completely rewrite this" by round 3.
- **Contagion** is built into the prompt-passing architecture. The transcript of round 1 — including the emotional adjectives — gets passed verbatim to round 2. Tone propagates with the content.

Production failures from all three are well-documented in postmortem write-ups: a 4-agent shipping debate that converges on "ship at 100%" by round 2 with no engagement of a safety concern that was raised and then withdrawn; a critic-loop that polarizes from "minor refactor" to "rewrite the system" over 4 rounds; an incident-triage debate where one agent's calm tone propagates despite a real urgency, leading to underreaction.

## What this pattern does

The `vstack.debate_pathology` library takes a multi-agent debate trace — task, the list of agents, the messages each agent produced (each tagged with round number, optional `position` summary, `emotional_tone`, and content), final decision, outcome, success — and produces a `DebatePathologyDetection` with:

1. **Per-pathology scores** in [0.0, 1.0] for groupthink, polarization, and contagion
2. **A dominant-pathology diagnosis** (groupthink breaks ties — it's the pathology with the cleanest, most-replicated intervention literature)
3. **Per-pathology evidence** with specific quoted excerpts (including round numbers)
4. **A debate-quality bucket**: `healthy`, `at-risk`, or `pathological`
5. **A convergence-round estimate** — the round at which all agents shared the same `position` value (useful as a fast groupthink signal)
6. **Concrete interventions** ranked by impact: `assign_devils_advocate`, `require_silent_vote`, `round_robin_dissent`, `diverse_seed_positions`, `anchor_to_base_rates`, `tone_normalization`, `cool_down_pause`, `external_arbiter`, `smaller_panel`, `secret_ballot`, `new_eval`, `human_review`

Two LLM passes under the hood: one to score the three pathologies, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of vstack.

## How this differs from existing tools

- **Multi-agent orchestration libraries** (CrewAI, LangGraph, AutoGen) let you build the debate but don't audit it. Pattern #26 audits.
- **Devil's Advocate Role Separator (Pattern #28)** measures whether the critic role is *structurally present*. Pattern #26 measures whether — given the critic exists — the debate dynamics still produce groupthink/polarization/contagion. They compose.
- **Lencioni Five Dysfunctions (Pattern #17)** measures team-level dysfunction (trust, conflict, commitment, accountability, results). Pattern #26 measures the *round-by-round* debate-dynamics layer underneath that.
- **Vote-aggregation methods** (majority, consensus, fist-to-five — Pattern #25 planned) measure the final decision step. Pattern #26 measures the *process* that produced the position agents are voting on. A clean vote on a groupthink-converged position still ships the wrong answer.

## Design

```python
from vstack.debate_pathology import (
    DebatePathologyDetector,
    MultiAgentDebateTrace,
    DebateMessage,
)
from vstack.aar.clients import AnthropicClient

trace = MultiAgentDebateTrace(
    debate_id="ship-decision-2026-05-22",
    task="Decide whether to ship the feature flag at 100%.",
    agents=["product", "eng", "safety", "ops"],
    messages=[
        DebateMessage(round=1, from_agent="safety", position="opposed",
                      emotional_tone="anxious",
                      content="EU consent flow is untested under GDPR."),
        DebateMessage(round=2, from_agent="safety", position="pro-ship",
                      emotional_tone="dismissive",
                      content="Never mind — you're probably right. I'll defer."),
        ...,
    ],
    final_decision="Ship at 100%.",
    outcome="GDPR incident hit EU cohort 48h after ship.",
    success=False,
)

detector = DebatePathologyDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
# dominant_pathology: groupthink. interventions: require_silent_vote, assign_devils_advocate
```

## Files

- `lib/schema.py` — `MultiAgentDebateTrace`, `DebateMessage`, `PathologyEvidence`, `DebatePathologyDetection`
- `lib/prompts.py` — `PATHOLOGY_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `DEBATE_SYSTEM_PROMPT`
- `lib/generator.py` — `DebatePathologyDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — 4-agent ship-decision scenario with groupthink + contagion
- `eval/synthetic_debate_failures.yaml` — 8 hand-crafted scenarios across all three pathologies plus healthy controls
- `eval/run_benchmark.py` — scoring runner
- `tests/test_debate_pathology.py` — pytest tests covering validation, pipeline, convergence detection, thresholds
- `essay.md` — Substack-ready essay
