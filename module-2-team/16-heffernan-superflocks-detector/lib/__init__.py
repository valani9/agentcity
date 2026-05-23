"""agentcity.superflocks — Margaret Heffernan's superflocks fragility
pattern applied to multi-agent orchestrator routing.

When an orchestrator always routes to the "best" single agent, the
system becomes brittle — the other agents' complementary capabilities
go unused, redundancy collapses, and the system has no fallback when
the top agent fails. The detector measures five quantitative fragility
metrics and recommends concrete robustness interventions.

Quick start:

    from agentcity.superflocks import (
        SuperflocksDetector,
        RoutingTrace,
        RoutingDecision,
        AgentCapability,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = RoutingTrace(
        trace_id="prod-routing-2026-W21",
        window_description="Last 1000 production task routes.",
        agents=["claude", "gpt", "haiku", "ollama"],
        capabilities=[...],
        routing_decisions=[...],
        outcome="Single-agent dominance; one outage cascaded.",
        success=False,
    )
    detection = SuperflocksDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # fragility_quality: superflocks
    # interventions: introduce_routing_jitter, redundant_routing, swap_top_agent_offline_drill
"""

from .generator import LLMClient, SuperflocksDetector
from .schema import (
    AgentCapability,
    FragilityIntervention,
    RoutingDecision,
    RoutingTrace,
    SuperflocksDetection,
    SuperflocksMetric,
)

__all__ = [
    "SuperflocksDetector",
    "LLMClient",
    "RoutingTrace",
    "RoutingDecision",
    "AgentCapability",
    "SuperflocksMetric",
    "FragilityIntervention",
    "SuperflocksDetection",
]

__version__ = "0.0.11"
