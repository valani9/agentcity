# Your agent crew is a flat-peer brainstorm running an incident. Galbraith and Mintzberg called it.

*A twenty-fourth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A 3-agent crew is dispatched to an incident: p99 latency spike across the order pipeline, SLO is 15-minute MTTR. The three agents are interchangeable generalists. The orchestrator's design choice was simple: *"propose ideas in parallel, resolve disagreements by majority vote."* It feels democratic. It feels modern.

Forty-five minutes in, the incident is still open. The three agents have produced three credible hypotheses (database lock contention, cache stampede, queue backpressure). They have argued about which to pursue for thirty of those minutes. Resolution finally arrives when one of them gets impatient, ignores the vote, and pursues the queue thread unilaterally. Root cause is found in two minutes. The post-mortem will say *"we need better communication tools."* The post-mortem will be wrong.

The crew did not have a communication problem. It had a **structure problem**. A flat-peer crew with vote-based decisions is the right structure for a creative brainstorm. It is the wrong structure for incident response. Incident response needs **centralization** — a single commander who can cut off threads, prioritize one lead, and commit decisions on a 5-minute clock. The structure of this crew was fit for some task class. Just not this one.

In *Designing Organizations* (1995) and a dozen subsequent works, Jay Galbraith formalized what's now called the **Star Model**: organizations have five interlocking design variables, and choosing the wrong combination for the task is the most common cause of structural failure. Henry Mintzberg's *Structure in Fives* (1983) ran in parallel — same observation, different decomposition: organizations have five distinct structural configurations (simple structure, machine bureaucracy, professional bureaucracy, divisionalized form, adhocracy), and using the wrong configuration for the work is the recurring failure mode.

The consolidation across the org-design canon is that **structure decomposes into six measurable dimensions**: specialization, formalization, centralization, hierarchy, span of control, and departmentalization. Each one can be scored independently. Each one has a target value that depends on the task class. When the observed profile diverges from the target profile, you get structural failure — and the failure mode is *predictable from which dimension diverged*.

For AI agent crews, the same decomposition applies. The reason this isn't obvious is that we mostly don't *design* agent crews — we accrete them. Someone adds an orchestrator because routing got complex. Someone adds a reviewer because outputs got sloppy. Someone adds a critic because the team kept agreeing too easily. Each addition is locally rational. The cumulative result is a structure nobody designed, optimized for nothing in particular, and a poor fit for whatever the crew is actually running.

The Org-Structure Matrix Analyzer is the diagnostic for this. Six dimensions:

- **specialization** (0..1) — how narrowly are roles defined? Generalists score low; tightly-typed specialists score high.
- **formalization** (0..1) — how rule-bound vs improvisational? Templated prompts and rigid escalation paths score high.
- **centralization** (0..1) — where do decisions get made? One orchestrator scores 1.0; pure peer consensus scores 0.0.
- **hierarchy** (0..1) — how many levels deep? Flat crews score 0.0; orchestrator-supervisor-worker structures score 0.5+.
- **span_of_control** (0..1) — how many subordinates per supervisor? Wide spans score high.
- **departmentalization** (0..1) — by what dimension are agents grouped? Function-grouped, product-grouped, customer-grouped, matrix, or none.

Each task class implies a different target profile. **Incident response** needs high centralization (a commander), moderate hierarchy (escalation path), and high specialization (db / cache / queue tagged roles). **Creative brainstorm** needs the opposite — low centralization, zero hierarchy, low specialization. **High-throughput pipelines** need high formalization, moderate centralization, and high specialization. The same crew profile can be the right answer or the wrong answer depending on what they're running.

## What `agentcity.org_structure` does

The library takes a `CrewStructureTrace` containing:

- The **agent roster** with explicit `AgentRole` graph (agent_id, role_name, reports_to edges, grouped_by, decision_authority)
- The **task class** (creative_brainstorm / research_exploration / incident_response / regulated_workflow / customer_support / code_review / high_throughput_pipeline / general_purpose)
- The **observed behaviors** and outcome

and produces a `StructureAnalysis` with:

1. **Per-dimension profile** for each of the six dimensions: observed, target, fit, explanation, evidence quotes
2. **Archetype classification** — one of `flat-peer`, `hierarchical`, `centralized-functional`, `decentralized-product`, `matrix`, or `mixed`
3. **Overall fit** in [0.0, 1.0] — mean fit across the six
4. **Fit-quality bucket**: `well-fit`, `partial-fit`, `misfit`
5. **Biggest gap** — which dimension has the largest observed-vs-target delta
6. **A ranked list of interventions** targeting the biggest gap: add_supervisor_layer, flatten_hierarchy, consolidate_roles, split_roles, shift_decision_authority, regroup_by_product, regroup_by_function, introduce_matrix, add_routing_layer, remove_routing_layer, new_eval, human_review

Two LLM passes under the hood. The intervention pass is skipped when fit quality is `well-fit`. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The most expensive structural failure mode is the **flat-peer incident response** (the opening example). Production teams default to flat-peer crews because they're cheap to set up — no orchestrator, no role differentiation, just N copies of the same agent. The structure works fine for low-stakes parallel tasks. It catastrophically fails the moment something time-critical happens, because there is nobody who can cut off a thread.

The fix is `add_supervisor_layer` — introduce an explicit `incident-commander` role with FULL decision_authority. The other agents set `reports_to=[incident-commander]`. The commander has a hard 5-minute kill criterion per thread. This is not a sophisticated intervention. It is a structural change that the team should have made before the first incident, and that they often don't make until after the third one.

The second most expensive structural failure mode is the **hierarchical creative brainstorm**. Production teams that have learned to fear flat-peer crews over-correct by inserting orchestrators everywhere. The orchestrator then becomes a review bottleneck on creative work, killing novelty by pre-judging every idea before workers can explore. The fix is `flatten_hierarchy` — strip the orchestrator and let the workers operate as peers for brainstorm-class tasks specifically, while keeping the orchestrator for other task classes the same crew handles.

The diagnostic value is that you don't have to guess *which* fix. The biggest-gap dimension tells you which dial to turn. `centralization` divergence calls for adding or removing the commander. `specialization` divergence calls for splitting or consolidating roles. `departmentalization` divergence calls for regrouping. Each gap maps to a specific class of intervention.

## How this fits with the rest of AgentCity

This is pattern #33 of 34 — the twenty-fourth pattern shipped, and the **third Module 3 (Organizational) pattern.** Module 3 now covers the full organizational diagnostic surface:

- **#31 Schein Iceberg Culture Audit** — layer-coherence diagnostic
- **#32 Robbins & Judge 7-Characteristics** — multi-dim culture-shape diagnostic
- **#33 Org-Structure Matrix (this pattern)** — six-dimension structural-fit diagnostic

The three compose. Schein for culture coherence, Robbins/Judge for culture shape, Org-Structure Matrix for structural fit. A crew can be coherent (Schein) and well-shaped culturally (Robbins/Judge) and still fail because the structure is wrong for the task. The three diagnostics together cover the organizational-design surface from culture to org chart.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-3-organization/33-org-structure-matrix
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
