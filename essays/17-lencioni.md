# Lencioni Five Dysfunctions — the multi-agent crew pyramid

*#17 vstack_lencioni* · *Module 2 — Multi-agent team*

> A three-agent crew shipped a Q3 marketing campaign on time. The campaign delivered 12% of target. The team's first reaction was to blame the model layer — "the critic agent is too soft." But pulling the inter-agent message log surfaced something else: the critic *did* push back, repeatedly, in the first two passes. The strategist agent just kept agreeing with the researcher, then re-routing around the critic's notes. The critic eventually stopped pushing. By the time the campaign shipped, every agent was deferring to the same path. There wasn't a model problem. There was a trust problem.

## What the pattern catches

Patrick Lencioni's 2002 *Five Dysfunctions of a Team* names a pyramid: **absence of trust → fear of conflict → lack of commitment → avoidance of accountability → inattention to results**. The bottom dysfunction enables the one above it. A team can ship — even ship well — with the top three dysfunctions present, as long as the bottom two are healthy. When the bottom two break, every layer above eventually follows.

vstack_lencioni runs this pyramid on a multi-agent crew. The diagnostic answers: *which layer is the lowest unhealthy one?* That layer is the root; everything above it is symptom.

## Why the OB literature is the right reference

Lencioni 2002 + Lencioni 2005 stack with Edmondson 1999 (psychological safety as the foundation), Hackman 2002 (real teams + compelling direction + enabling structure), Salas et al 2018 (team science meta-analysis). All four frameworks converge: **the underlying conditions** (trust, safety, structure) are necessary for the surface behaviors (good debate, commitment, accountability) to function.

The Lencioni pyramid transfers cleanly to agent crews. Agent crews are exactly multi-agent systems that need trust (will another agent's output be honored?), safety (can an agent dissent?), commitment (do agents converge on a decision?), accountability (do agents flag deviations?), and results-focus (does the crew share a target metric?). LangGraph and CrewAI don't enforce any of these; they're emergent properties of how the agents talk to each other.

## How the analyzer works

Input is `MultiAgentTrace` — goal, agent roster, inter-agent message log, outcome, success. The pipeline:

- **quick** — one LLM call. Severity + dominant_dysfunction.
- **standard** — two LLM calls. Full pyramid scoring + 4-6 interventions targeting the lowest unhealthy layer.
- **forensic** — four LLM calls. Adds a cascade audit (how the lowest layer's failure manifests in each upper layer) + a parallel psychological-safety check that grounds the trust score in dissent rate + dissent-suppression detection.

```python
from vstack.lencioni import LencioniAnalyzer, MultiAgentTrace
diag = LencioniAnalyzer(llm, mode="forensic").run(MultiAgentTrace(
    goal="Generate a Q3 marketing campaign",
    agents=["researcher", "strategist", "critic"],
    messages=[...],
    outcome="Shipped on time, conversion 12% of target.",
    success=False,
))
print(diag.dominant_dysfunction)   # 'absence_of_trust'
print(diag.pyramid_scores)         # 5 axes, 0-10 each
```

## What the playbooks say to do

Lencioni's interventions are layer-keyed:

- **Absence of trust** → "Force vulnerability moments. Add a designated devil's advocate role with a hard floor on dissent count; don't let the orchestrator collapse advocate + critic into one role."
- **Fear of conflict** → "Reframe conflict as productive. Move agreement-reaching to a separate pass *after* a mandatory disagreement-surfacing pass."
- **Lack of commitment** → "Force a written commitment artifact per decision. Crews that never write down the decision drift toward whoever last spoke."
- **Avoidance of accountability** → "Each agent owns a measurable. The crew can't ship until every agent has signed off on its measurable."
- **Inattention to results** → "Display the target metric every turn. Agents drift to local-optimum rituals; surfacing the metric keeps them honest."

## How it composes with adjacent patterns

Lencioni is the **primary diagnostic** in chain T1 (crew is "off"). The four parallel supporting audits:

- `vstack_psych_safety` (Edmondson) — the per-axis score that grounds Lencioni's "absence of trust" finding.
- `vstack_trust_triangle` (Frei & Morriss) — *which leg* of trust (logic / authenticity / empathy) is wobbling.
- `vstack_process_gain_loss` (Steiner) — coordination cost.
- `vstack_bias_stack` (Kahneman/Tversky) — top bias active in reasoning.

When Lencioni's lowest layer is "absence of trust" + Trust Triangle says "authenticity gap" + Edmondson says "low dissent rate", that's the *same problem at three resolutions*. The executive readout names it once, with the deepest finding as the headline.

If Lencioni surfaces "lack of commitment", chain into structural patterns — that often masks a load / structure problem. If it surfaces "absence of trust" at the foundation, chain into culture (`vstack_schein_culture`).

## Comparison to adjacent tools

- **Edmondson alone** scores one axis. Lencioni is the *layered* diagnostic.
- **CrewAI's built-in "manager" role** assumes the team works. Lencioni asks whether it does.
- **LangGraph debugger / trace viewers** show *what* happened. They don't say *which dysfunction the crew is exhibiting*.

## Paper outline

1. **Background** — Lencioni 2002, Lencioni 2005, Edmondson 1999, Hackman 2002, Salas et al 2018.
2. **Translation** — multi-agent crews as bona fide teams.
3. **Method** — pyramid scoring, cascade audit, psych-safety overlay.
4. **Evaluation** — multi-agent benchmark suite (e.g. CrewAI's `examples/` or AppWorld traces); measure whether Lencioni's lowest-dysfunction call matches an independent human rater.
5. **Limitations** — small message logs are noisy; the pattern needs >20 inter-agent turns to discriminate cleanly.
6. **Related work** — Crew effectiveness research (Hackman 2002, Wageman 2008), AI multi-agent eval (Wang et al 2023).
7. **Future work** — longitudinal cascade detection across many crew runs.

## Citations

- Lencioni, P. (2002). *The Five Dysfunctions of a Team*.
- Lencioni, P. (2005). *Overcoming the Five Dysfunctions of a Team*.
- Edmondson, A. (1999). Psychological safety and learning behavior in work teams.
- Hackman, J. R. (2002). *Leading Teams*.
- Salas, E., Reyes, D. L., & McDaniel, S. H. (2018). The science of teamwork: progress, reflections, and the road ahead.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-lencioni analyze --trace examples/campaign_crew.json --mode forensic
```

If Lencioni surfaces "absence of trust", run `vstack_trust_triangle` next — it'll tell you whether logic, authenticity, or empathy is the wobbling leg.
