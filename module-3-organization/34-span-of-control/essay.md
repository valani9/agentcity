# Your orchestrator has 12 workers and full commit authority. The math says you have effective parallelism of 1.

*A twenty-ninth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A customer-support crew is provisioned: one orchestrator, twelve worker agents. The orchestrator routes incoming requests. The workers process. Easy. The architect's diagram has a hub-and-spoke shape. The dashboard shows twelve workers, which feels like twelve units of throughput.

Then traffic hits 100 requests per minute. Queue depth starts climbing. p99 latency exceeds SLO. The team adds two more workers. Queue still grows. They add four more. Same problem. They swap to a faster model. Marginal improvement. Eventually someone runs the actual numbers and discovers that *the workers don't have commit authority*. Every response must be approved by the orchestrator before it ships. Effective parallelism isn't 12. It's 1.

The diagram looked right. The math was wrong.

This is the failure mode the org-design canon — Jay Galbraith's *Designing Organizations* (1995), Henry Mintzberg's *Structure in Fives* (1983), and the modern Stanford / Stuart Hall consolidation — has been measuring for forty years. Organizations don't fail because their structures look wrong on a diagram. They fail because the *numbers* underneath the diagram don't work: span of control too wide for one supervisor, hierarchy too deep for time-critical decisions, centralization too high for the load, span distribution too uneven for steady-state operation.

The framework is six metrics, all measurable, all deterministic. For AI agent crews:

- **max_span** — the widest supervisor's subordinate count. Healthy <7, problematic >10. The hub-and-spoke crew has max_span = 12, which is severe.

- **mean_span** — average span across supervisors. >5 starts becoming a coordination load. The hub-and-spoke has mean_span = 12 (only one supervisor); a properly tiered version would have mean_span ≈ 4.

- **centralization_index** — fraction of decision authority concentrated in the top supervisor(s). Computed as `(authority_weight × subordinate_count)` summed over the top-K supervisors, normalized to the crew total. Above 0.6 starts producing single-point-of-failure dynamics. The hub-and-spoke is roughly 0.85.

- **hierarchy_depth** — longest reports_to chain. Each layer adds approval latency. >3 levels makes time-critical decisions sluggish. The hub-and-spoke is 2 layers (orchestrator + workers) — this metric isn't the problem here.

- **span_gini** — inequality across the span distribution. 0 = every supervisor has the same subordinate count. 1 = one supervisor holds all subordinates. The hub-and-spoke crew has gini ≈ 0.9 (one supervisor with 12, twelve agents with 0). This is the imbalance signal.

- **decision_bottleneck** — the composite of span × full-authority × incoming-load. This is the metric that catches the opening scenario most cleanly. The orchestrator has span=12, full decision authority, and 100 requests/minute incoming. Score ≈ 0.95. The orchestrator IS the bottleneck.

The diagnostic value of computing all six is that **each metric points at a different intervention**. You don't have to guess which fix matters.

For the opening crew, the worst metric is `decision_bottleneck` (0.95). The intervention is `delegate_decision_authority`: upgrade workers from "advisory" to "partial" decision authority for low-risk request classes (FAQ, status checks, shipping inquiries). The orchestrator keeps full authority only for high-risk classes (refunds, escalations). Effective parallelism goes from 1 to 6 immediately. Throughput multiplies by 6×. No model swap, no new workers, no rebuild — just a single decision-authority delegation.

The second-worst metric is `max_span` (1.0). The intervention is `split_supervisor_load`: insert two sub-supervisors so the orchestrator's span drops from 12 to 2, and each sub-supervisor manages 6 workers. This combines with the first intervention to give 4-way effective parallelism at the supervisor layer with healthy spans throughout.

Neither intervention is novel. Both are textbook org design. What's novel is having the *numbers* tell you which intervention applies *first*, so the team doesn't apply `consolidate_supervisors` (which would make the problem worse) when the actual issue is centralization.

## The hard thing about this pattern

Most diagnostic patterns in AgentCity rely on an LLM to do the diagnostic work. This one doesn't. The math is intentionally deterministic — six pure-Python functions that operate on the agent roster and reports_to graph. The LLM is involved only in *generating interventions* on top of the locked metric values. The math should not depend on model whim.

This is the same architectural decision made by Pattern #16 (Heffernan Superflocks Detector), where the routing-distribution metrics are computed deterministically and the LLM only contributes intervention narratives. The reason is operational: numbers that change run-to-run because the LLM had a different mood aren't usable as a regression metric. You can't track *"is the crew's centralization_index trending up or down across deploys"* if the number itself is non-deterministic.

The cost of this design is that the pattern can't surface things the math doesn't see. A crew with perfect math but bad culture (Pattern #31 Schein) or bad structural fit (Pattern #33 Org-Structure Matrix) will pass #34's check while still being broken. That's *intentional*. Each pattern has its job. #34's job is the numbers.

## What `agentcity.span_of_control` does

The library takes a `CrewLoadTrace` containing:

- **agents** — list of `AgentNode` (agent_id, role_name, reports_to, decision_authority)
- **incoming_request_rate** — requests/minute hitting the crew, used to amplify bottleneck scoring under load
- **task** + **outcome** + **success**

and produces a `SpanLoadAnalysis` with:

1. **All six quantitative metrics**, each with raw value + normalized score (0..1)
2. **structural_load_score** — composite, weighted toward bottleneck (0.30) and gini (0.20)
3. **structural_load_quality bucket**: `well-balanced` (<0.3), `under-stress` (0.3-0.6), `overloaded` (≥0.6)
4. **bottleneck_agent_ids** — agents flagged by the deterministic computation
5. **A ranked list of interventions** targeting the worst metric: add_supervisor_layer, flatten_hierarchy, split_supervisor_load, delegate_decision_authority, consolidate_supervisors, redistribute_subordinates, add_redundant_path, remove_bottleneck_agent, new_eval, human_review

ONE LLM pass under the hood (interventions only), skipped when load quality is `well-balanced`. Same retry / graceful-degradation infrastructure as the rest of AgentCity. Math is deterministic by design.

## Why this matters operationally

The single highest-leverage use of this pattern is **catching the hub-and-spoke fragility before it ships**. Teams building multi-agent crews routinely default to "orchestrator + N workers" because it's the obvious shape. The shape isn't wrong by itself — what matters is whether the workers have commit authority. Without it, effective parallelism is 1 regardless of N. The `decision_bottleneck` metric catches this in static analysis, before traffic ever hits the system.

The second-highest-leverage use is **post-incident root-cause attribution**. When a multi-agent crew misses its SLO, the team's first instinct is usually *"add more workers"* or *"swap to a faster model."* Both are expensive and frequently don't help. Running #34 on the crew's actual structure produces a metric breakdown that points at the *structural* root cause: high centralization, imbalanced gini, deep hierarchy. The fix is often a one-line change to decision_authority assignments, not a model upgrade.

The third use is **comparative analysis across crews**. Because the metrics are deterministic, you can compute them across multiple crews and compare. A team running 5 different agent crews can see which ones have the highest bottleneck risk and prioritize structural refactoring. This is the kind of analysis that's impossible with LLM-driven diagnostics because the numbers change run-to-run.

## How this fits with the rest of AgentCity

This is pattern #34 of 34 — the thirtieth pattern shipped, and the **fourth Module 3 (Organizational) pattern.** Module 3 now covers the full organizational diagnostic surface:

- **#31 Schein Iceberg Culture Audit** — layer-coherence diagnostic
- **#32 Robbins & Judge 7-Characteristics** — multi-dim culture-shape diagnostic
- **#33 Org-Structure Matrix** — six-dimension qualitative structural-fit diagnostic
- **#34 Span-of-Control / Centralization (this pattern)** — six-metric deterministic structural-load diagnostic

The four compose. Schein for culture coherence, Robbins/Judge for culture shape, #33 for structural fit-to-task, #34 for whether the structure's *math* works under load. A crew can pass culture audits (Schein + Robbins) and pass structural-fit audit (#33) and still fail #34 because the orchestrator's span is too wide for the incoming traffic. The four diagnostics together cover culture, structure-fit, and structure-load.

#34 also pairs with **#16 Heffernan Superflocks Detector** (Module 2). Both are deterministic-metrics patterns; both diagnose multi-agent fragility. Superflocks looks at routing distribution (which agents get the work); span-of-control looks at the org graph (who reports to whom, who can commit). A crew can have balanced routing (passes #16) and still have an orchestrator bottleneck (fails #34) because the metric being measured is fundamentally different.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-3-organization/34-span-of-control
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
