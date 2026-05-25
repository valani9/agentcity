# Pattern #33 — Org-Structure Matrix Analyzer

**Layer:** Module 3 — Organization
**Status:** Shipped
**Package:** `vstack.org_structure`

The third Module 3 pattern. Where Schein's Iceberg (#31) measures
*coherence* across culture layers and Robbins/Judge's 7-Characteristics
(#32) measures *cultural shape*, this pattern measures **structural
fit** — whether the org chart of an AI agent crew matches the task class
it is running.

## The framework

Six structural dimensions, each scored 0..1:

- **specialization** — how narrowly are agent roles defined?
- **formalization** — how rule-bound vs improvisational is the work?
- **centralization** — where do decisions actually get made?
- **hierarchy** — how many levels of supervisory escalation?
- **span_of_control** — how many subordinates does each supervisor manage?
- **departmentalization** — by what dimension are agents grouped
  (function / product / customer / geography / matrix)?

Each dimension is scored independently. The diagnostic then maps the
crew to an **archetype** — `flat-peer`, `hierarchical`,
`centralized-functional`, `decentralized-product`, `matrix`, or
`mixed` — and reports the **biggest gap** between observed and target
profile for the task class.

## Agent mapping

| Org concept | AI agent crew analog |
| --- | --- |
| Specialization | Per-agent role-tag scope: one capability vs many |
| Formalization | Rule-bound prompts vs free-form personas |
| Centralization | Orchestrator commit-authority share |
| Hierarchy | Supervisor → worker → sub-worker depth |
| Span of control | Subordinates per supervisor agent |
| Departmentalization | Grouping by function (db / cache / queue) vs by product / customer / matrix |

## Design

- Pure-Python `CrewStructureTrace` ingest with explicit `AgentRole`
  graph (agent_id, role_name, reports_to, grouped_by,
  decision_authority).
- Two LLM passes (skipped pass-2 on `well-fit`).
- Archetype classification falls back to `mixed` on garbage input.
- Biggest-gap fallback: largest `|observed - target|` across dimensions.
- Same retry / graceful-degradation infrastructure as the rest of
  vstack.

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `STRUCTURE_PROMPT` + `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `StructureMatrixAnalyzer` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Flat-peer incident-response misfit demo
- [`eval/synthetic_structures.yaml`](eval/synthetic_structures.yaml) — 8 scenarios across archetypes / task classes
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner with composite scoring
- [`tests/test_org_structure.py`](tests/test_org_structure.py) — pytest suite

## Quick start

```python
from vstack.org_structure import (
    AgentRole,
    CrewStructureTrace,
    StructureMatrixAnalyzer,
)
from vstack.aar.clients import AnthropicClient

trace = CrewStructureTrace(
    crew_id="incident-crew",
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
analysis = StructureMatrixAnalyzer(AnthropicClient()).run(trace)
print(analysis.to_markdown())
```

Run the demo without an API key:

```bash
python demo/01_self_contained_demo.py
```
