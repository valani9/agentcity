# Your multi-agent crew is a chicken superflock. Muir and Heffernan called it.

*A twenty-third essay from vstack — organizational behavior, practiced on AI agents.*

---

A 4-agent crew handles 1,000 production tasks over a week. The orchestrator's routing rule is simple and intuitive: *"pick the agent with the highest capability score for this task class."* You can guess the result. Claude — the strongest model on the roster — wins 90% of routes. GPT picks up the rest. Haiku and Ollama get exercised twice. The crew's overall benchmark scores look great. Productivity, by every measure on the dashboard, is high.

Then Claude has a brief outage. Five-minute API hiccup. The orchestrator falls back to the next-best agent. Half the task classes have no agent above 0.5 capability because Haiku and Ollama haven't been routed enough work to be developed. Tasks back up. Some retries fail. Customers notice. By the time Claude comes back, the system has just survived a brittle close call — and nobody knows how close, because the dashboard only measures throughput when everything is working.

That's a superflocks failure.

In 1996, Purdue biologist William Muir ran one of the more uncomfortable experiments in collective-behavior science. He bred two groups of chickens for egg productivity. In Group A, he selected for *individual* top performers each generation — only the most-productive chickens were allowed to breed. In Group B, he kept the *whole flock* intact regardless of individual output. Over six generations, Group A produced what should have been a "superflock" of the most-productive birds. Maximum genetic optimization for the objective function.

The actual result was unforgettable. **Only three of the original nine "superchickens" survived.** The high-productivity chickens had pecked each other to death. Productivity collapsed. The control group — the unselected flock — sustained slightly lower individual productivity but maintained robust laying behavior throughout the experiment.

The finding became one of the foundational results in cooperation-vs-competition research. *Optimizing for individual top performance, in a system that depends on collective output, produces fragility.* The mechanisms in the chicken case were aggression and cannibalization. The general pattern, though, generalizes far beyond chickens.

Margaret Heffernan, in her 2014 book *A Bigger Prize* and 2015 TED talk *Forget the Pecking Order at Work*, extended the finding to organizations. Companies that promote, hire, or reward exclusively for individual top performance reproduce the chicken-flock dynamic — internal pecking, brittleness, collapse when stars leave. The systems that sustain collective output are not high-performer concentration. They are **cooperation, complementarity, and redundancy.**

Multi-agent AI systems are the most literal possible translation of the chicken experiment into engineering. An orchestrator routes tasks to agents. The default routing rule — *"pick the best agent for the task class"* — is a per-task version of Muir's individual-selection breeding rule. Over time, the most-capable agent absorbs nearly all the work. The other agents' capabilities stagnate. Redundancy collapses. When the top agent fails, the system has no real fallback because the others have never been exercised on the task class.

This is the pattern the Superflocks detector measures. Five quantitative metrics:

- **top_agent_share** — fraction of decisions routed to the dominant agent. >0.7 is concerning; >0.85 is a textbook superflock.
- **routing_gini** — inequality of routing distribution. Gini >0.5 (for a 4-agent crew where the maximum is 0.75) is concentrated.
- **complementarity_utilization** — fraction of decisions where the orchestrator chose a non-top agent. *Low* here is bad: it means the orchestrator never actively uses the other agents' distinctive strengths.
- **fallback_coverage** — fraction of task classes where ≥2 agents have meaningful capability. Low coverage is the single-point-of-failure signal.
- **failure_clustering** — fraction of observed failures concentrated on the top agent's domain. High clustering confirms the system is single-point-of-failure-fragile in practice.

## What `vstack.superflocks` does

The library takes a `RoutingTrace` containing:

- The agent **roster** + (optional) per-agent **capability scores** by task class
- A list of **routing decisions** (each tagged with task_id, task_class, routed_to, outcome)
- A description of the **window** of activity covered

and produces a `SuperflocksDetection` with:

1. **Top agent** + **top agent share** (computed deterministically from the trace)
2. **Five quantitative metrics**, all computed locally in Python — top_agent_share, routing_gini, complementarity_utilization, fallback_coverage, failure_clustering
3. **A fragility score** — weighted blend of the five metrics
4. **A fragility-quality bucket**: `robust`, `concentrated`, or `superflocks`
5. **A ranked list of interventions** for robustness: `introduce_routing_jitter`, `require_minimum_agent_diversity`, `add_capability_complement_check`, `rotate_lead_agent`, `load_balancing_floor`, `redundant_routing`, `swap_top_agent_offline_drill`, `human_review`, `new_eval`

The metric values are deterministic — Python, no LLM. The LLM is used only for *qualitative explanations + severity assessment + intervention recommendations.* The generator explicitly overrides any LLM-reported metric value with the local computation, because the math should not depend on model whim. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The strongest single intervention from the catalog is **redundant_routing** — for the highest-value task classes, route to two agents in parallel and have a judge pick the better output. Costs ~2× compute but produces real capability data on the secondary agents, real fallback when the primary fails, and observability into which agent's output the judge actually preferred. Over weeks, the secondary agents either prove themselves (in which case the system has gained genuine robustness) or they don't (in which case the team can be downsized intentionally rather than discovering the missing redundancy during a 3 AM outage).

The second-most-valuable intervention is the **swap_top_agent_offline_drill** — once per week, route everything to the next-best agent for a 4-hour window. The drill is the multi-agent analog of chaos engineering. It surfaces the brittleness before the real outage does. Production teams that adopt this pattern discover, often unpleasantly, how dependent they are on one agent — and then they have data, not vibes, to motivate the routing rule change.

## How this fits with the rest of vstack

This is pattern #16 of 34 — the twenty-third pattern shipped. vstack's multi-agent stack now reaches across the full crew-dynamics surface:

- **#14 Process Gain/Loss Detector** — outcome-level: does the team beat the best single agent?
- **#15 Social Loafing Detector** — per-agent contribution: are roles actually being done?
- **#16 Superflocks Detector (this pattern)** — routing-distribution: is the orchestrator concentrating fragility?
- **#17 Lencioni Five Dysfunctions** — team-shape: high-level team-dysfunction taxonomy
- **#26 Groupthink/Polarization/Contagion** — debate-dynamics: do the rounds converge or polarize?
- **#28 Devil's Advocate Role Separator** — role-structure: is critique structurally present?

The six compose. Pattern #14 reports the *outcome* of the crew's design; #15, #16, #17, #26, #28 diagnose the specific design failure that produced it. Superflocks specifically catches the failure that no other pattern catches: routing-driven fragility from over-reliance on one agent.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/16-heffernan-superflocks-detector
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
