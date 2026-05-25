# Recipe: spot a structural bottleneck

Crew works on one request; falls over under load. Chain: **Span-of-Control (deterministic) → Org-Structure (qualitative fit) → Social Loafing + Superflocks (behavioral)**.

```python
from vstack.aar import AnthropicClient
from vstack.span_of_control import SpanLoadCalculator, CrewLoadTrace, AgentNode

llm = AnthropicClient()

trace = CrewLoadTrace(
    crew_id="customer-support",
    task="Handle 100 req/min on a multi-agent crew.",
    agents=[
        AgentNode(agent_id="orchestrator", decision_authority="full"),
        *[
            AgentNode(
                agent_id=f"worker-{i}",
                reports_to=["orchestrator"],
                decision_authority="advisory",
            )
            for i in range(12)
        ],
    ],
    incoming_request_rate=100.0,
    outcome="Throughput collapsed.",
    success=False,
)

# Span-of-Control: deterministic math. Run with the canonical
# hub-and-spoke baseline so you get drift vs. textbook failure mode.
span = SpanLoadCalculator(llm, mode="standard").run(
    trace,
    baseline_path="_baselines/canonical/span_of_control_hub_and_spoke.json",
)
print(span.profile_pattern, span.severity)
print(span.metrics)               # max_span / mean_span / centralization_index / ...
```

## Four-quadrant decision

|                       | Math broken                 | Math fine                  |
|-----------------------|-----------------------------|-----------------------------|
| **Structure wrong**   | Fundamental redesign        | Restructure (split / merge) |
| **Structure right**   | Tune (load-balance)         | Look at behavior            |

If math is fine but throughput tanks → run the behavioral pair:

```python
from vstack.social_loafing import SocialLoafingAnalyzer, MultiAgentTaskTrace
from vstack.superflocks import SuperflocksAnalyzer, RoutingTrace

loafing = SocialLoafingAnalyzer(llm).run(MultiAgentTaskTrace(...))
flock = SuperflocksAnalyzer(llm).run(RoutingTrace(...))
```

## Skill-based shortcut

```
/vstack-bottleneck
> We added 8 more agents and throughput dropped 40% ...
```
