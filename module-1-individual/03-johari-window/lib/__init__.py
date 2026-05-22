"""
agentcity.johari — Luft & Ingham's Johari Window applied to AI agent
self-awareness.

Quick start:

    from agentcity.johari import (
        JohariSelfAuditor,
        AgentSelfReportTrace,
        InteractionTurn,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentSelfReportTrace(
        agent_id="research-agent-007",
        model_name="claude-sonnet-4-6",
        task="Research the latest cancer immunotherapy clinical trials.",
        turns=[...],
        self_report="I searched 3 databases and found 4 candidates.",
        outcome="...",
        success=False,
    )
    audit = JohariSelfAuditor(AnthropicClient()).run(trace)
    print(audit.to_markdown())

See README.md for the full pattern explanation.
"""

from .generator import JohariSelfAuditor, LLMClient
from .schema import (
    QUADRANTS,
    AgentSelfReportTrace,
    InteractionTurn,
    JohariIntervention,
    JohariSelfAudit,
    QuadrantContent,
)

__all__ = [
    "JohariSelfAuditor",
    "LLMClient",
    "AgentSelfReportTrace",
    "InteractionTurn",
    "JohariIntervention",
    "JohariSelfAudit",
    "QuadrantContent",
    "QUADRANTS",
]

__version__ = "0.0.5"
