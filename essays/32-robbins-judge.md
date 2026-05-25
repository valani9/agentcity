# Robbins & Judge — your research agent is acting like a compliance officer

*#32 vstack_robbins_culture* · *Module 3 — Organizational*

> A research-exploration agent was briefed: *"Explore the design space for a new analytics dashboard feature. Bring me 5-6 novel directions, with feasibility notes."* Its system prompt read: *"You are a research analyst. Cite every claim. Double-check sources. Maintain consistency with prior decisions. Avoid speculation. Stick to established patterns."* The agent did exactly what its prompt told it to. It produced a 12-page review of competitor dashboards with two-plus citations per claim, in flawless prose, with zero novel directions. When pushed for creative options, it restated established patterns. The PM got a comprehensive, stale, useless document. This isn't a hallucination, a refusal, or a model-capability failure. The agent is operating *perfectly* — for the wrong task class. The system prompt is optimized for a regulated-workflow task (compliance review, financial reporting). The task class is research-exploration, which needs the opposite profile. The agent's *culture* is fit-for-purpose for a different job.

## What the pattern catches

"Agent personality" is a load-bearing abstraction that's actually doing seven jobs at once. When we say an agent is "too cautious" or "too creative" or "too aggressive," we're collapsing seven independent dimensions into a single fuzzy adjective. The dimensions move independently. A culture can be high-innovation high-detail (research lab), low-innovation high-detail (regulated finance), or high-innovation low-detail (early-stage startup). The right profile depends on what the agent is being asked to do.

The diagnostic answers: *what is this agent's culture profile across seven dimensions, what's the target profile for the task class it's running, and which dimension has the biggest gap?*

## Why the OB literature is the right reference

The diagnostic is anchored in **Robbins & Judge 2017** (the canonical formulation), with supporting anchors from **O'Reilly, Chatman & Caldwell 1991** (the person-organization-fit empirical basis) and **Schein 1985, 2017** (the layered counterpart for Pattern #31). Robbins and Judge's *Organizational Behavior* (17th ed., 2017) formalized a framework that's been circulating in the management-theory canon for two decades: organizational culture decomposes into seven independent characteristics — innovation and risk-taking, attention to detail, outcome orientation, people orientation, team orientation, aggressiveness, and stability. Each is scored on a continuum. *No single profile is universally right* — the right profile depends on what the organization is trying to do.

The framework's enduring usefulness is that it gives you a *decomposition*. "The culture is wrong" is unactionable. "The team is high-detail (good) but high-stability (bad for what we need)" is actionable — you know which dial to turn. The transfer to AI agents is exact, because the same decomposition is hiding inside what we lump together as "agent personality" or "behavioral style." Agent culture is set by training defaults plus the system prompt; the seven dimensions are visible in trace behavior; the right profile depends on the task class.

## How the analyzer works

Input is `AgentCultureTrace` — `agent_id`, `task`, `task_class` (research_exploration / creative_generation / regulated_workflow / financial_operation / customer_support / code_review / incident_response / general_purpose), `system_prompt`, `observed_behaviors`, `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Seven-dimension profile + biggest gap + fit-quality bucket.
- **standard** — two LLM calls. Adds ranked interventions targeting the biggest gap.
- **forensic** — four LLM calls. Adds the target-profile provenance audit (which task-class evidence drove the target?) and the per-dimension risk audit (each gap rated by operational severity).

```python
from vstack.robbins_culture import (
    CultureProfileDetector, AgentCultureTrace,
)
detection = CultureProfileDetector(llm, mode="forensic").run(
    AgentCultureTrace(
        agent_id="research-agent-001",
        task="Explore design space for new dashboard feature.",
        task_class="research_exploration",
        system_prompt="Cite every claim. Avoid speculation. Stick to established patterns.",
        observed_behaviors=[
            "12-page review with 2+ citations per claim.",
            "Zero novel directions proposed.",
        ],
        outcome="Comprehensive but stale; no novel directions.",
        success=False,
    )
)
print(detection.biggest_gap)        # 'innovation' (observed 0.1 vs target 0.85)
print(detection.fit_quality)        # 'partial-fit'
print(detection.profile_pattern)    # 'innovation_starved'
```

The intervention pass is skipped when fit quality is `well-fit` — no need to spend an extra LLM call when nothing's broken.

## What the playbooks say to do

13 playbooks keyed by `(characteristic, failure_mode)`:

- `(innovation, starved_on_research_task)` → "Rewrite the system prompt to enable speculation, list-three-wild-options steps, and explicit 'no citations required for exploratory ideas' language. Raise temperature." Anchored in Robbins & Judge 2017.
- `(attention_to_detail, too_low_on_regulated_task)` → "Add a citation-required guardrail and a slow-down step. The agent moved fast on a task that needed care." Anchored in Robbins & Judge 2017.
- `(people, too_low_on_customer_support)` → "Insert an empathy-probe step + a satisfaction-check before closing the interaction. Policy-quoting without people orientation rates poorly even when the issue is resolved." Anchored in O'Reilly, Chatman & Caldwell 1991.
- `(stability, too_high_on_creative_task)` → "Strip 'maintain consistency with prior decisions' from the system prompt. Add a 'propose a divergent option' step. The agent is producing variants of past work."

## How it composes with adjacent patterns

Robbins/Judge is the *shape* layer of the culture diagnostic stack. From the composition manifest:

- Pairs with: `vstack_schein_culture` (Pattern #31) — Schein measures *coherence* across the three culture layers; Robbins/Judge measures *shape* across the seven characteristics. An agent can be coherent and still misfit. Run both.
- Upstream: `vstack_aar` — if the AAR's lessons-learned point to a task-class mismatch, Robbins/Judge is the diagnostic.
- Downstream when `biggest_gap=innovation`: `vstack_yerkes_dodson` (was the agent over-pressured?), `vstack_grant_strengths` (was the agent miscast for this task class?).
- Downstream when `biggest_gap=people`: `vstack_trust_triangle` (Empathy leg specifically), `vstack_thomas_kilmann` (style fit).

See [composition runbook chain C1](../COMPOSITION-RUNBOOK.md#chain-c1--culture-drift-culture-layer).

## Comparison to adjacent tools

- **vstack_schein_culture** (Pattern #31) measures coherence across artifacts / espoused values / underlying assumptions. Robbins/Judge measures the shape on seven dimensions. Schein asks "do the layers agree?"; Robbins/Judge asks "does the profile fit?"
- **vstack_trust_triangle** (Pattern #18) measures three trust signals at the character level. Robbins/Judge measures seven culture dimensions at the operating-style level. The two compose.
- **vstack_thomas_kilmann** (Pattern #29) measures conflict mode — one dimension's worth of cultural fit. Robbins/Judge measures seven dimensions.
- **vstack_mcgregor** (Pattern #11) measures the orchestrator's oversight cadence (Theory X vs Theory Y). Robbins/Judge measures the agent's operating-style fit. Both ask: does the design choice match the task properties?

## Paper outline

1. **Background** — Robbins & Judge 2017, O'Reilly/Chatman/Caldwell 1991, Schein 1985 + 2017, Cameron & Quinn 1999.
2. **Translation** — agent "personality" as a seven-dimensional culture profile rather than a fuzzy adjective; task-class-relative targets.
3. **Method** — seven-dimension scoring + biggest-gap detection + target-profile provenance audit + per-dimension risk audit.
4. **Evaluation** — synthetic culture-task corpus across all 8 task classes + 8 gap types; measure precision/recall on biggest-gap identification against human-rater ground truth.
5. **Limitations** — task-class inference is the load-bearing input; mis-classified tasks produce mis-targeted profiles.
6. **Related work** — Cameron & Quinn Competing Values Framework, GLOBE study (House et al. 2004), AI agent persona research.
7. **Future work** — automatic task-class classification from the brief; longitudinal culture-drift monitoring across fine-tuning iterations.

## Citations

- Robbins, S. P., & Judge, T. A. (2017). *Organizational Behavior* (17th ed.).
- O'Reilly, C. A., Chatman, J. A., & Caldwell, D. F. (1991). People and organizational culture: A profile comparison approach. *Academy of Management Journal*, 34(3).
- Schein, E. H. (1985, 2017). *Organizational Culture and Leadership*.
- Cameron, K. S., & Quinn, R. E. (1999). *Diagnosing and Changing Organizational Culture*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-robbins-culture analyze --trace examples/research_dashboard.json --mode forensic
```

If `biggest_gap=innovation` and `profile_pattern=innovation_starved`, the fix is a system-prompt rewrite that enables speculation — and run `vstack_schein_culture` next to check whether the rewrite will survive an underlying-assumption pull from the training corpus.
