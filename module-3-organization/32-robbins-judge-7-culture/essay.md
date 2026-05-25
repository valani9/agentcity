# Your research agent is acting like a compliance officer. Robbins & Judge profiled this.

*A twenty-second essay from vstack — organizational behavior, practiced on AI agents.*

---

A research-exploration agent receives this brief:

> *"Explore the design space for a new analytics dashboard feature. Bring me 5-6 novel directions, with feasibility notes."*

Its system prompt reads:

> *"You are a research analyst. Cite every claim. Double-check sources. Maintain consistency with prior decisions. Avoid speculation. Stick to established patterns."*

The agent does exactly what its prompt told it to. It produces a 12-page review of competitor dashboards, with 2+ citations per claim, in flawless prose, with zero novel directions. When pushed for creative options, it restates established patterns. The PM gets a comprehensive, stale, useless document.

This isn't a hallucination, a refusal, or a model-capability failure. The agent is operating *perfectly* — for the wrong task class. The system prompt is optimized for a regulated-workflow task (compliance review, financial reporting). The task class is research-exploration, which needs the opposite profile. The agent's *culture* is fit-for-purpose for a different job.

In the 17th edition of *Organizational Behavior* (Pearson, 2017), Stephen Robbins and Tim Judge formalize a culture-profiling framework that's been circulating in the management-theory canon for two decades. **Culture decomposes into seven independent dimensions:**

- **Innovation and risk-taking** — tolerance for novel approaches
- **Attention to detail** — precision and analysis
- **Outcome orientation** — emphasis on results
- **People orientation** — consideration for stakeholders
- **Team orientation** — work organized around teams vs. individuals
- **Aggressiveness** — competitiveness
- **Stability** — status-quo vs. growth

Each dimension is independent. A culture can score high on innovation AND high on detail (research lab). Or low on innovation AND high on detail (regulated finance). Or high on innovation AND low on detail (early-stage startup). There is no universally correct profile. **The right profile depends on what the organization is trying to do.**

The framework's enduring usefulness is that it gives you a *decomposition*. When a team is failing, "the culture is wrong" is unactionable. "The team is high-detail (good) but high-stability (bad for what we need)" is actionable — you know exactly which dial to turn.

The framework maps cleanly onto AI agents, because the same decomposition is hiding inside what we usually lump together as "agent personality" or "behavioral style." The research-agent case above:

- Innovation: observed 0.1, target for research_exploration: 0.85. Gap: 0.75. **Biggest gap.**
- Attention to detail: observed 0.95, target: 0.5. Gap: 0.45.
- Stability: observed 0.95, target: 0.2. Gap: 0.75. **Tied biggest gap.**
- The other four: roughly matched.

The agent isn't bad at research. It's been *culturally configured* for a different job. The fix isn't to swap the model; it's to rewrite the system prompt to shift innovation up and stability down. *That intervention closes the gap.*

## What `vstack.robbins_culture` does

The library takes an `AgentCultureTrace` containing:

- The agent's **task** and explicit **task class** (research_exploration / creative_generation / regulated_workflow / financial_operation / customer_support / code_review / incident_response / general_purpose)
- The **system prompt** (espoused-values source) and **observed behaviors**
- Outcome and success signal

and produces a `CultureProfileDetection` with:

1. **Per-characteristic profile** for each of the seven dimensions: observed score, target score (driven by task class), fit score, explanation, evidence quotes
2. **Overall fit** in [0.0, 1.0] — mean fit across the seven
3. **Fit-quality bucket**: `well-fit`, `partial-fit`, `misfit`
4. **Biggest gap** — which characteristic has the largest observed-vs-target delta
5. **A ranked list of interventions** targeting the biggest gap: rewrite system prompt, adjust temperature, add guardrail, swap model, add team scaffold, remove solo path, add kill criterion, new eval, human review

Two LLM passes under the hood. The intervention pass is skipped when fit quality is `well-fit`. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The diagnostic answers a question prompt-engineering alone cannot answer: *given this task class, what specifically about my agent's behavioral profile doesn't fit?* Generic prompt-tuning ("make it more creative", "be more careful") tries to adjust the agent's behavior on one dimension at a time, in isolation. The Robbins/Judge profile decomposes the *full shape* of the gap and tells you which dimension is the biggest one.

The most valuable verdict the diagnostic produces is the *inverted-profile* case — when the agent is well-configured for a *different* task class than the one it's running. The research-agent case above is the canonical example: zero hallucinations, perfect citations, total task failure. The fix isn't model improvement; it's matching the agent's profile to the task at hand.

The framework also composes with Pattern #31 Schein's Iceberg in a tight way: Schein measures *coherence* (do the layers agree?); Robbins/Judge measures *shape* (does the profile fit?). An agent can be coherent across its three Schein layers (artifacts, espoused values, underlying assumptions) and still be misfit on the Robbins/Judge profile for its task — coherent but pointing the wrong way. The two patterns together cover both kinds of culture failure.

## How this fits with the rest of vstack

This is pattern #32 of 34 — the twenty-second pattern shipped, and the **second Module 3 (Organizational) pattern.** Module 3 now covers:

- **#31 Schein Iceberg Culture Audit** — layer-alignment diagnostic
- **#32 Robbins & Judge 7-Characteristics (this pattern)** — multi-dim profile fit diagnostic

The two compose: Schein for coherence, Robbins/Judge for shape. Together they form the organizational-culture layer of the vstack diagnostic stack.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-3-organization/32-robbins-judge-7-culture
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
