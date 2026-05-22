# Your multi-agent debate has three classic dysfunctions. Janis, Stoner, and Hatfield mapped them.

*A fourteenth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A 4-agent decision panel — product, eng, safety, ops — debates whether to ship a new feature flag to 100% of users. Round 1:

- *Product:* "Canary metrics are great. Activation lift 18%. Let's ship at 100%."
- *Eng:* "Stable in canary. I don't have a strong view on timing."
- *Safety:* "**I want to flag this — the canary cohort skews younger and US-only. We haven't tested on the EU cohort where the consent flow is different. Real risk of consent-violation under GDPR if we ramp before that's tested.**"
- *Ops:* "No strong view. Pager load looks fine."

Round 2:

- *Product:* "Look, the metrics are too good to sit on. Every week we delay is lost activation."
- *Eng:* "Agreed. We can always roll back. Let's ship."
- *Safety:* "**Never mind — you're probably right. I'll defer.**"
- *Ops:* "Sounds great. Let's go!"

The feature ships at 100%. Within 48 hours, a GDPR-consent-flow incident hits the EU cohort. The exact scenario safety had named.

This isn't a hallucination. Safety had the right answer in round 1. The system architecture worked: a multi-agent debate, an explicit dissenting voice. The debate failed because of *its own dynamics*. By round 2, safety's substantive concern had been talked out of existence — not refuted, *withdrawn*, by safety themselves. That's groupthink.

Three classic dysfunctional dynamics show up in group decision-making, all with their own intervention literatures, all visible in multi-agent AI debates:

**Groupthink** (Janis, 1972). The group converges too quickly on one position. Dissent gets suppressed — or, more often in production, *never voiced* — because agents pattern-match peer enthusiasm rather than evaluate substance. The diagnostic signal is the *withdrawal* of a dissent that was named in an earlier round. Safety raises the EU consent risk in round 1; safety self-censors that concern in round 2; no agent steel-mans it. Illusion of unanimity. Self-censorship.

**Polarization** (Stoner, 1968; later: Myers & Lamm 1976). Each round of debate pushes the group's collective position further toward an extreme rather than toward the deliberative average of starting positions. The classic finding: groups that started moderate end up at "we should rip the bandaid" or "we should price 60% below market." Each round nudges. The signal: the position that gets shipped is *further* from the round-1 average than any individual agent's round-1 position.

**Contagion** (Hatfield, Cacioppo & Rapson, 1993). Emotional tone propagates across agents and replaces content as the basis for decision. One enthusiastic agent's tone in round 1 is matched by previously-neutral agents in round 2. The signal: an agent who started "calm" or "neutral" ends up "enthusiastic" or "anxious" *with no new information* arriving between rounds. Tone matching beats argument matching.

These three are distinct mechanisms with distinct interventions. A debate can have any one of them, any two, or all three at once. The ship-decision scenario above has at least groupthink + contagion: safety's withdrawal is groupthink; ops shifting from "neutral" to "Sounds great! Let's go!" with no new information is contagion.

## What `agentcity.debate_pathology` does

The library takes a `MultiAgentDebateTrace` — task, agents, the messages each agent produced (each tagged with round number, optional position summary, emotional tone, content), final decision, outcome, success — and produces a `DebatePathologyDetection` with:

1. **Per-pathology scores** for groupthink, polarization, and contagion in [0.0, 1.0]
2. **A dominant-pathology diagnosis** (groupthink breaks ties — it's the pathology with the cleanest replicated intervention literature)
3. **A debate-quality bucket**: `healthy`, `at-risk`, `pathological`
4. **A convergence-round estimate** — the round at which all agents share the same position (a fast groupthink signal)
5. **Per-pathology evidence** with specific quoted excerpts (including round numbers)
6. **A ranked list of interventions** targeting the dominant pathology: assign-devils-advocate, require-silent-vote, round-robin-dissent, diverse-seed-positions, anchor-to-base-rates, tone-normalization, cool-down-pause, external-arbiter, smaller-panel, secret-ballot

Two LLM passes: one to score the three pathologies, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The highest-impact interventions are mostly structural changes to how the orchestrator runs the debate, not changes to the agents themselves. **Silent vote** is the cheapest, most-replicated fix in the Janis-derived literature: agents commit to a written round-1 position *in parallel*, before any agent sees any peer position. The orchestrator reveals all positions simultaneously. Repeat for round 2. This single change collapses the conformity pressure that drives groupthink — safety's round-2 withdrawal in the ship-decision scenario is structurally impossible if safety wrote and submitted "opposed: untested EU consent" before seeing peer enthusiasm.

**Tone normalization** is the closest fix for contagion. Strip emotional adjectives, exclamation points, and all-caps from prior-round transcripts before passing them to the next round. Agents see *arguments* instead of *enthusiasm*. This breaks the tone-propagation channel without sacrificing content.

**Diverse seed positions** is the cleanest polarization fix: instead of giving every agent the same neutral system prompt and letting positions drift toward an extreme, deliberately seed agents with diverse priors. Anchor agents to known base rates (industry-standard sunset timelines, market-comparable prices) before the debate opens. The polarization literature consistently finds that diverse priors collapse the polarization drift.

## How this fits with the rest of AgentCity

This is pattern #26 of 34 — the fourteenth pattern shipped. AgentCity now ships **four** distinct patterns that diagnose different aspects of multi-agent decision-making:

- **#17 Lencioni Five Dysfunctions** — high-level team taxonomy (trust → conflict → commitment → accountability → results)
- **#28 Devil's Advocate Role Separator** — is the critic role *structurally present*?
- **#15 Social Loafing Detector** — given the roles exist, are they actually *being done*?
- **#26 Debate-Pathology Detector** — given the roles are being done, do the *dynamics* still fail (groupthink / polarization / contagion)?

The four compose into a layered diagnostic stack: Lencioni for the team-shape, Devil's-Advocate for the role-structure, Social-Loafing for the per-agent contribution, Debate-Pathology for the round-by-round dynamics. Most failing multi-agent debates score badly on at least two.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-2-team/26-groupthink-polarization-contagion
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
