# Org-Structure Matrix — your agent crew is a flat-peer brainstorm running an incident

*#33 vstack_org_structure* · *Module 3 — Organizational*

> A three-agent crew was dispatched to an incident: p99 latency spike across the order pipeline, SLO 15-minute MTTR. The three agents were interchangeable generalists. The orchestrator's design choice was simple — propose ideas in parallel, resolve disagreements by majority vote. It felt democratic. It felt modern. Forty-five minutes in, the incident was still open. The three agents had produced three credible hypotheses (database lock contention, cache stampede, queue backpressure) and had been arguing about which to pursue for thirty of those minutes. Resolution finally arrived when one of them got impatient, ignored the vote, and pursued the queue thread unilaterally. Root cause was found in two minutes. The postmortem said "we need better communication tools." The postmortem was wrong. The crew didn't have a communication problem. It had a structure problem. A flat-peer crew with vote-based decisions is right for a creative brainstorm. It is wrong for incident response, which needs a single commander who can cut off threads, prioritize one lead, and commit on a 5-minute clock.

## What the pattern catches

Most agent crews aren't designed — they're *accreted*. Someone adds an orchestrator because routing got complex. Someone adds a reviewer because outputs got sloppy. Someone adds a critic because the team kept agreeing too easily. Each addition is locally rational. The cumulative result is a structure nobody designed, optimized for nothing in particular, and a poor fit for whatever the crew is actually running.

The diagnostic answers: *what structural archetype is this crew, what's the target archetype for the task class, and which structural dimension has the biggest gap?* Six dimensions, each scored independently: specialization, formalization, centralization, hierarchy, span of control, departmentalization. Each task class implies a different target profile.

## Why the OB literature is the right reference

The diagnostic is anchored in **Galbraith 1995** and **Mintzberg 1983**, with supporting anchors from **Burns & Stalker 1961** and **Lawrence & Lorsch 1967**. Galbraith's *Designing Organizations* formalized the Star Model — five interlocking design variables, where choosing the wrong combination for the task is the most common cause of structural failure. Mintzberg's *Structure in Fives* ran in parallel with the same observation and a different decomposition: organizations have five canonical configurations (simple structure, machine bureaucracy, professional bureaucracy, divisionalized form, adhocracy), and using the wrong configuration for the work is the recurring failure mode.

The consolidation across the org-design canon is that structure decomposes into six measurable dimensions, each with task-class-dependent targets. Burns & Stalker's mechanistic vs organic structures map onto the formalization × centralization quadrants. Lawrence & Lorsch's differentiation-integration framework grounds the departmentalization dimension. The transfer to AI agent crews is one-to-one because the same observable properties exist in any multi-agent system: who reports to whom, who has commit authority, how rule-bound the prompts are, how narrowly roles are defined.

## How the analyzer works

Input is `CrewStructureTrace` — `crew_id`, `task`, `task_class`, `agents` (each an `AgentRole` with `agent_id`, `role_name`, `reports_to`, `grouped_by`, `decision_authority`), `observed_behaviors`, `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Six-dimension profile + archetype classification + biggest gap + fit-quality bucket.
- **standard** — two LLM calls. Adds ranked interventions targeting the biggest-gap dimension.
- **forensic** — four LLM calls. Adds the reporting-graph audit (does the declared `reports_to` graph match the behavioral evidence?) and the decision-bottleneck audit (where commit authority concentrates and whether it matches the task's required cadence).

```python
from vstack.org_structure import (
    StructureMatrixAnalyzer, CrewStructureTrace, AgentRole,
)
analysis = StructureMatrixAnalyzer(llm, mode="forensic").run(
    CrewStructureTrace(
        crew_id="incident-001",
        task="Investigate latency spike.",
        task_class="incident_response",
        agents=[
            AgentRole(agent_id="a1", role_name="generalist"),
            AgentRole(agent_id="a2", role_name="generalist"),
            AgentRole(agent_id="a3", role_name="generalist"),
        ],
        observed_behaviors=["No agent owns the incident; majority vote."],
        outcome="MTTR exceeds SLO by 3x.",
        success=False,
    )
)
print(analysis.archetype)         # 'flat-peer'
print(analysis.biggest_gap)       # 'centralization'
print(analysis.profile_pattern)   # 'too_flat_for_critical_task'
```

The intervention pass is skipped on `well-fit`. The reporting-graph audit catches the most common debugging surprise: the declared graph and the behavioral graph disagree, and the behavioral one is what's actually running.

## What the playbooks say to do

12 playbooks keyed by `(dimension, failure_mode)`:

- `(centralization, too_flat_for_critical_task)` → "Add a supervisor layer. Introduce an explicit `incident-commander` role with full `decision_authority`. The other agents set `reports_to=[incident-commander]`. Commander has a hard 5-minute kill criterion per thread. Not sophisticated, but the highest-leverage structural change." Anchored in Galbraith 1995 + Mintzberg 1983.
- `(hierarchy, bottleneck_on_creative)` → "Flatten the hierarchy for brainstorm-class tasks specifically. Strip the orchestrator; let workers operate as peers. Keep the orchestrator for other task classes the same crew handles."
- `(specialization, generalists_on_specialist_workload)` → "Split roles by function (db / cache / queue). Tag each agent with one capability; route by tag. Generalist-everywhere is right for exploration and wrong for specialization-dependent tasks."
- `(departmentalization, function_grouped_for_product_work)` → "Regroup by product. Function-grouping creates cross-team coordination cost that product-grouping eliminates for product-class workloads." Anchored in Lawrence & Lorsch 1967.

## How it composes with adjacent patterns

Org-Structure Matrix is the *structural* layer of the organizational diagnostic stack. From the composition manifest:

- Pairs with: `vstack_schein_culture` (Pattern #31) and `vstack_robbins_culture` (Pattern #32) — Schein for culture coherence, Robbins/Judge for culture shape, Org-Structure for structural fit. A crew can be coherent (Schein), well-shaped (Robbins/Judge), and still fail because the structure is wrong for the task.
- Downstream when `biggest_gap=span_of_control`: `vstack_span_of_control` (Pattern #34) is the deepening pass — Org-Structure flags the dimension at the crew level; Span-of-Control localizes which supervisor is over- or under-loaded.
- Downstream when `archetype=flat-peer` on a critical task: `vstack_lencioni` (team dysfunction layer) often co-fires.

See [composition runbook chain S1](../COMPOSITION-RUNBOOK.md#chain-s1--crew-slows-down-under-load-structural-layer).

## Comparison to adjacent tools

- **vstack_schein_culture / vstack_robbins_culture** measure culture (the bottom and the shape of the iceberg). Org-Structure measures the org chart. The three compose into the full Module 3 surface.
- **vstack_span_of_control** (Pattern #34) zooms into one specific dimension — how many subordinates per supervisor. Org-Structure measures all six dimensions jointly; Span-of-Control is the localization pass.
- **CrewAI / LangGraph / AutoGen** let you build crew structures. Org-Structure audits whether the structure you built matches the task class you're running.
- **Multi-agent eval suites** (AppWorld, SWE-Bench-Multi) measure outcomes. Org-Structure measures the structural cause when outcomes are bad.

## Paper outline

1. **Background** — Galbraith 1995/2014, Mintzberg 1983, Burns & Stalker 1961, Lawrence & Lorsch 1967.
2. **Translation** — agent crews as organizations with measurable structural dimensions; task-class-relative archetype targets.
3. **Method** — six-dimension scoring + archetype classification + reporting-graph audit + decision-bottleneck audit + intervention ranker.
4. **Evaluation** — synthetic crew corpus across all six archetypes + eight task classes; measure precision/recall on archetype classification and biggest-gap identification.
5. **Limitations** — the `reports_to` and `decision_authority` inputs depend on accurate self-reporting from the crew operator; mismatches between declared and behavioral graphs are caught by the forensic audit but not the quick mode.
6. **Related work** — multi-agent topology research, hierarchical RL, mixture-of-experts routing.
7. **Future work** — automatic structure suggestion from task-class input; cross-archetype routing layers that adapt structure per-task.

## Citations

- Galbraith, J. R. (1995, 2014). *Designing Organizations: An Executive Briefing on Strategy, Structure, and Process*.
- Mintzberg, H. (1983). *Structure in Fives: Designing Effective Organizations*.
- Burns, T., & Stalker, G. M. (1961). *The Management of Innovation*.
- Lawrence, P. R., & Lorsch, J. W. (1967). *Organization and Environment*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-org-structure analyze --trace examples/incident_crew.json --mode forensic
```

If `archetype=flat-peer` on a critical task, the fix is `add_supervisor_layer` — and run `vstack_span_of_control` next to make sure the new commander's reporting graph stays inside the 5-9 sweet spot.
