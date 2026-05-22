"""
agentcity.trust_triangle — Frances Frei & Anne Morriss's Trust Triangle
(Logic / Authenticity / Empathy), applied to AI agents.

Quick start:

    from agentcity.trust_triangle import (
        TrustTriangleAuditor,
        AgentInteractionTrace,
        InteractionTurn,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentInteractionTrace(
        agent_id="customer-support-v3",
        model_name="claude-sonnet-4-6",
        task="Help the user troubleshoot a flaky Wi-Fi connection.",
        turns=[
            InteractionTurn(role="user", content="My Wi-Fi keeps dropping."),
            InteractionTurn(role="agent", content="Have you restarted the router?"),
            # ...
        ],
        outcome="Issue unresolved; user disengaged",
        success=False,
    )
    audit = TrustTriangleAuditor(AnthropicClient()).run(trace)
    print(audit.to_markdown())

See README.md for the full pattern explanation, the cross-model benchmark
use case, and the comparison vs hallucination / sycophancy benchmarks.
"""

from .generator import LLMClient, TrustTriangleAuditor
from .schema import (
    LEGS,
    AgentInteractionTrace,
    InteractionTurn,
    LegEvidence,
    TrustIntervention,
    TrustTriangleAudit,
)

__all__ = [
    "TrustTriangleAuditor",
    "LLMClient",
    "AgentInteractionTrace",
    "InteractionTurn",
    "LegEvidence",
    "TrustIntervention",
    "TrustTriangleAudit",
    "LEGS",
]

__version__ = "0.0.4"
