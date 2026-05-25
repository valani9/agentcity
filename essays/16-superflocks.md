# Superflocks — your crew is one outage away from collapse

*#16 vstack_superflocks* · *Module 2 — Multi-agent team*

> A 4-agent crew handled 1,000 production tasks over a week. The orchestrator's routing rule was the obvious one: *pick the agent with the highest capability score for this task class.* The strongest model on the roster won 90% of routes. The second-strongest picked up the rest. The remaining two agents were exercised twice. Every dashboard looked green — throughput high, error rate low. Then the dominant model had a five-minute API hiccup. The fallback agent's capability on half the task classes was below 0.5 because it had never been routed enough work to be developed. Tasks backed up. Some retries failed. Customers noticed. By the time the dominant model returned, the system had just survived a brittle close call — and nobody knew how close, because the dashboard only measured throughput when everything was working.

## What the pattern catches

Orchestrator routing rules that optimize for individual top performance produce systems that look great until they don't. The dynamic is identical to the one William Muir documented in 1996 when he bred chickens for individual egg productivity — over six generations, the "superflock" pecked itself to death and productivity collapsed, while the unselected control flock sustained slightly lower individual output but stayed robust throughout. Margaret Heffernan extended the finding to organizations in her 2014 book *A Bigger Prize* and her 2015 TED talk: companies that promote, hire, or reward exclusively for individual top performance produce internal pecking, brittleness, and crashes when stars leave.

Multi-agent AI systems are the most literal possible translation of Muir's experiment into engineering. The orchestrator's per-task "pick the best agent" rule is a per-decision version of Muir's individual-selection breeding rule. Over time, the most-capable agent absorbs nearly all the work; the others' capabilities stagnate; redundancy collapses.

The analyzer answers: *is the routing distribution building robustness or fragility?*

## Why the OB literature is the right reference

The diagnostic is anchored in Heffernan 2014 (*A Bigger Prize*), Heffernan 2015 (TED Talk *Forget the Pecking Order at Work*), Muir 1996 (the underlying chicken-flock experiments), Hackman 2002 (team-effectiveness anchor), Page 2007 (*The Difference* — diversity producing better groups), Salas et al. 2018 (modern review), Wang et al. 2023 on cooperative LLM agents, plus Bandura 1977 self-efficacy as anti-fragility cross-reference.

**Muir's 1996 finding** was that optimizing for individual top performance, in a system that depends on collective output, produces fragility. The mechanisms in the chicken case were aggression and cannibalization. Heffernan's contribution was showing the dynamic generalizes — the systems that sustain collective output are not high-performer concentration; they are *cooperation, complementarity, and redundancy*. Page 2007 formalized this in mathematical terms: diverse-enough cognitive perspectives beat homogeneous-but-individually-better groups on hard problems.

The transfer to agent orchestration is direct. An orchestrator routing to the strongest agent every time is genetically equivalent to Muir's individual-selection condition. The result is a "superflock" of one — high apparent productivity, zero fallback, collapse under the first outage.

## How the analyzer works

Input is `RoutingTrace` — `trace_id`, `window_description`, agent roster, optional `AgentCapability` per-task-class scores, list of `RoutingDecision` (each with `task_id`, `task_class`, `routed_to`, `outcome`). The pipeline:

- **quick** — one LLM call. Fragility-quality bucket + top intervention.
- **standard** — two LLM calls. Five `SuperflocksMetric` entries with qualitative explanation + ranked interventions.
- **forensic** — four LLM calls. Adds `CapabilityComplementarityAudit`, `FailureClusteringAudit`, and composition handoffs.

```python
from vstack.superflocks import SuperflocksAnalyzer, RoutingTrace, RoutingDecision, AgentCapability
detection = SuperflocksAnalyzer(llm, mode="forensic").run(
    RoutingTrace(
        trace_id="prod-routing-2026-W21",
        window_description="Last 1000 production task routes.",
        agents=["claude", "gpt", "haiku", "ollama"],
        capabilities=[
            AgentCapability(agent_name="claude", capability_scores={"research": 0.92, "coding": 0.88}),
            AgentCapability(agent_name="haiku",  capability_scores={"research": 0.45, "coding": 0.40}),
        ],
        routing_decisions=[...],
        outcome="Single-agent dominance; one outage cascaded.",
        success=False,
    )
)
print(detection.fragility_quality)   # 'superflocks'
print(detection.top_agent_share)     # 0.90 — deterministic
```

The five quantitative metrics — `top_agent_share`, `routing_gini`, `complementarity_utilization`, `fallback_coverage`, `failure_clustering` — are computed **deterministically in Python**. The LLM only contributes qualitative explanation, severity, and interventions. Any LLM-reported metric value is overridden by the local computation.

## What the playbooks say to do

Nine interventions, ordered by robustness impact:

- `redundant_routing` → "For the highest-value task classes, route to two agents in parallel; have a judge select the better output. Costs ~2× compute but produces real capability data on secondary agents, real fallback when the primary fails, and observability on which agent the judge actually preferred." (Page 2007.)
- `swap_top_agent_offline_drill` → "Once per week, route everything to the next-best agent for a 4-hour window. The chaos-engineering analog. Surfaces brittleness before the real outage does."
- `introduce_routing_jitter` → Random ε% of decisions go to non-top agents. Counters the lock-in dynamic.
- `require_minimum_agent_diversity` → Per task class, ≥2 agents must be exercised over a rolling window.
- `add_capability_complement_check` → Before routing, check whether a non-top agent has a complementary capability the top agent lacks.
- `rotate_lead_agent` → Cycle the "primary" assignment per task class on a fixed schedule.
- `load_balancing_floor` → Each agent receives at least F% of routes regardless of capability score.

## How it composes with adjacent patterns

Superflocks sits in the **multi-agent stack** alongside Process Gain/Loss (#14, outcome) and Social Loafing (#15, contribution):

- `vstack_process_gain_loss` measures whether the team beat the best single agent. Superflocks asks the inverse question — does the routing distribution build robustness?
- `vstack_social_loafing` measures whether agents *contribute*; Superflocks measures whether the *orchestrator* routes work to them. Complementary: high Superflocks fragility means unrouted agents are loafing by *system design*.
- `vstack_devils_advocate` (#28) measures whether critique is structurally present; Superflocks measures whether *capability* is structurally diverse.
- `vstack_lencioni` (#17) reports the team-shape dysfunction; Superflocks is the routing-distribution lens that catches what Lencioni doesn't.

Cross-link to [composition runbook chain S1](../COMPOSITION-RUNBOOK.md#chain-s1--crew-slows-down-under-load-structural-layer).

## Comparison to adjacent tools

- **Generic load balancers** distribute requests for *capacity* reasons. Superflocks measures whether the distribution preserves *capability redundancy* on top of capacity.
- **Cost optimization dashboards** maximize routing to the cheapest acceptable agent; Superflocks asks whether that policy collapses fallback.
- **`vstack_process_gain_loss`** is the outcome metric; Superflocks is the design-time diagnostic that catches the failure before it costs.

## Paper outline

1. **Background** — Muir 1996, Heffernan 2014/2015, Hackman 2002, Page 2007, Salas 2018.
2. **Translation** — orchestrator routing as individual-selection breeding rule; fragility as the engineering analog of chicken-flock collapse.
3. **Method** — deterministic five-metric computation, fragility-score blending, LLM qualitative layer, intervention ranking.
4. **Evaluation** — synthetic routing-trace benchmark: 30 traces with known top-agent-share, gini, fallback-coverage; measure analyzer reconstruction accuracy.
5. **Limitations** — needs sufficient routing volume (>200 decisions) for meaningful Gini.
6. **Related work** — chaos engineering literature; load-balancer routing fairness; Page's diversity-trumps-ability theorems.
7. **Future work** — predictive fragility scoring; auto-trigger redundant_routing when top-agent-share crosses a threshold.

## Citations

- Heffernan, M. (2014). *A Bigger Prize: How We Can Do Better than the Competition*. Simon & Schuster.
- Heffernan, M. (2015). Forget the pecking order at work. TED Talk.
- Muir, W. M. (1996). Group selection for adaptation to multiple-hen cages: Selection program and direct responses. *Poultry Science*, 75, 447-458.
- Hackman, J. R. (2002). *Leading Teams*. HBS Press.
- Page, S. E. (2007). *The Difference: How the Power of Diversity Creates Better Groups*. Princeton University Press.
- Salas, E., et al. (2018). Science of team performance. *Annual Review of Org Psych*, 5, 593-620.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-superflocks analyze --trace examples/routing_window.json --mode forensic
```

If Superflocks returns `fragility_quality=superflocks` with `top_agent_share > 0.85`, start with `redundant_routing` on the top 3 task classes. The cost overhead is real, but you'll be measuring secondary-agent capability in production rather than discovering its absence during a 3 AM outage.
