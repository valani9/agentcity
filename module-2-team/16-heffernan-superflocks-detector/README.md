# Superflocks Detector — Heffernan/Muir, applied to multi-agent orchestrator routing

> *"For more than 50 years, William Muir bred chickens for individual egg productivity. The result wasn't a superflock — it was a small group of survivors. The 'high-productivity' chickens had pecked each other to death. Productivity collapsed. The flock had bred itself into fragility. Organizations that select for individual stars over team output produce the same dynamic."*
> — Margaret Heffernan, *Forget the Pecking Order at Work* (TED Talk, 2015) and *A Bigger Prize* (Simon & Schuster, 2014)

**Status:** 🟢 shipped
**Module:** 2 (Team) — multi-agent orchestrator routing
**Anchor framework:** Margaret Heffernan, *A Bigger Prize* (Simon & Schuster, 2014) and her 2015 TED Talk *Forget the Pecking Order at Work*. Drawing on Purdue biologist William Muir's chicken-flock experiments (1996-2010s).

---

## The OB framework

In 1996, Purdue biologist William Muir designed a multi-generation chicken-flock experiment. One condition selected for INDIVIDUAL egg productivity — each generation, only the most productive chickens bred. The other condition kept the *whole flock* intact regardless of individual output. Over six generations, the individual-selection condition produced a "superflock" of the most-productive chickens. The expected result was massive productivity gains.

The actual result: only **three of the original nine "superchickens" survived**. The most-productive chickens had pecked each other to death. Productivity collapsed. The control flock, where no individual selection happened, sustained slightly-less-productive but robust laying behavior throughout. Muir's finding became one of the foundational results in the cooperation-vs-competition literature in biology and organizational behavior.

Heffernan's 2014 book and 2015 TED talk extended the finding to human organizations. The pattern is the same. **Optimizing for individual top performance destroys collective productivity.** The systems that sustain group output are *cooperation, complementarity, and redundancy*, not raw individual talent. Organizations that breed (or hire, or promote) only for individual high-performance markers tend to produce fragile cultures, internal pecking, and crashes when the top performers leave.

The pattern has specific operational signatures in human teams:
- Routing all interesting work to the top performer
- Lack of fallback when the top performer is unavailable
- Collapse of complementary capabilities that were never developed
- Failures concentrating on the top performer's domain

## How this maps to AI agents

Multi-agent AI systems with an orchestrator + N agents exhibit the same dynamic with disturbing fidelity. The orchestrator's default routing rule — *"pick the agent with the highest capability score for this task class"* — produces the superflocks pattern in production.

A typical 4-agent crew (Claude + GPT + Haiku + Ollama) on a real-world workload often routes >90% of tasks to one agent. The other three rarely run. Their capability scores never improve (they're not getting practice). When the top agent has an outage, the crew has no real fallback because the others have never developed working knowledge of the task patterns. The system inherits the chicken-flock fragility: high productivity until the top performer is unavailable, then catastrophic collapse.

Five quantitative metrics expose the pattern:

| Metric | What it measures | High = bad |
|---|---|---|
| `top_agent_share` | Fraction of routing decisions going to one agent | 1 agent absorbs all work |
| `routing_gini` | Inequality of routing across the roster | concentration on few |
| `complementarity_utilization` | Fraction of decisions where the orchestrator actively chose a non-top agent | LOW = orchestrator never uses complementarity |
| `fallback_coverage` | Fraction of task classes with ≥2 capable agents | LOW = no fallback when top fails |
| `failure_clustering` | Fraction of failures concentrated on the top agent's domain | single-point-of-failure pattern |

## What this pattern does

The `vstack.superflocks` library takes a `RoutingTrace` with:

- The agent **roster**
- Optional per-agent **capability scores** by task class
- A list of **routing decisions** (each tagged with task_id, task_class, routed_to, outcome)
- A description of the **window** of activity covered

and produces a `SuperflocksDetection` with:

1. **Top agent** + **top agent share** (deterministic from the trace)
2. **Routing Gini coefficient** (deterministic)
3. **Five per-metric scores** (deterministic from the trace; LLM contributes qualitative explanation + severity)
4. **A fragility score** (weighted blend of the five metrics)
5. **A fragility-quality bucket**: `robust`, `concentrated`, or `superflocks`
6. **Concrete interventions** for robustness: `introduce_routing_jitter`, `require_minimum_agent_diversity`, `add_capability_complement_check`, `rotate_lead_agent`, `load_balancing_floor`, `redundant_routing`, `swap_top_agent_offline_drill`, `human_review`, `new_eval`

The five metrics are computed *locally* in Python — deterministic, no LLM. The single LLM pass produces the qualitative explanations + severity assessments + intervention recommendations. The LLM does not control the metric values (the generator overrides any LLM-reported metric value with the deterministic local computation).

## How this differs from existing tools

- **Pattern #15 Social Loafing Detector** measures whether agents loaf within a team they're assigned to. The Superflocks Detector measures whether the orchestrator's *routing* concentrates on one agent in the first place. They're complements: if Superflocks reports high `top_agent_share`, agents not getting routed are loafing by *system design*, not by their own behavior.
- **Pattern #14 Process Gain/Loss Detector** measures outcome (did the team beat the best single agent?). Superflocks asks the *routing-design* question (does the team's routing distribution build robustness or fragility?). Both flag over-reliance on one agent but from different angles.
- **Pattern #28 Devil's Advocate Role Separator** measures whether critique is structurally present. Superflocks measures whether *capability* is structurally diverse.
- **Generic load balancers** distribute requests across servers for capacity reasons. Superflocks measures whether the distribution preserves *robustness* (capability redundancy) on top of capacity.

## Design

```python
from vstack.superflocks import (
    SuperflocksDetector,
    RoutingTrace,
    RoutingDecision,
    AgentCapability,
)
from vstack.aar.clients import AnthropicClient

trace = RoutingTrace(
    trace_id="prod-routing-2026-W21",
    window_description="Last 1000 production task routes.",
    agents=["claude", "gpt", "haiku", "ollama"],
    capabilities=[
        AgentCapability(agent_name="claude",
                        capability_scores={"research": 0.92, "coding": 0.88}),
        AgentCapability(agent_name="gpt",
                        capability_scores={"research": 0.75, "coding": 0.78}),
        AgentCapability(agent_name="haiku",
                        capability_scores={"research": 0.45, "coding": 0.40}),
        AgentCapability(agent_name="ollama",
                        capability_scores={"research": 0.35, "coding": 0.42}),
    ],
    routing_decisions=[
        RoutingDecision(task_id="t01", task_class="research", routed_to="claude", outcome="success"),
        # ... 900 more
    ],
    outcome="Single-agent dominance; one outage cascaded.",
    success=False,
)

detector = SuperflocksDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
# top_agent: claude (share 0.90)
# fragility_quality: superflocks
# Intervention #1: redundant_routing (route in parallel to build fallback)
```

## Files

- `lib/schema.py` — `RoutingTrace`, `RoutingDecision`, `AgentCapability`, `SuperflocksMetric`, `SuperflocksDetection`
- `lib/prompts.py` — `METRICS_PROMPT`, `SUPERFLOCKS_SYSTEM_PROMPT`
- `lib/generator.py` — `SuperflocksDetector` (deterministic local metrics + 1 LLM pass for qualitative + interventions)
- `demo/01_self_contained_demo.py` — claude-dominated routing on a 4-agent crew
- `eval/synthetic_routing_traces.yaml` — 8 hand-crafted scenarios across robust / concentrated / superflocks
- `eval/run_benchmark.py` — scoring runner
- `tests/test_superflocks.py` — pytest tests covering validation, local metrics (all 5), pipeline, threshold reconciliation
- `essay.md` — Substack-ready essay
