"""
agentcity.lencioni — Patrick Lencioni's Five Dysfunctions of a Team,
applied to multi-agent AI systems.

Quick start:

    from agentcity.lencioni import (
        LencioniDiagnostic,
        MultiAgentTrace,
        AgentMessage,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = MultiAgentTrace(
        goal="Generate a marketing campaign",
        agents=["researcher", "strategist", "critic"],
        messages=[...],
        outcome="Campaign launched, performed 12% of target",
        success=False,
    )
    diagnosis = LencioniDiagnostic(AnthropicClient()).run(trace)
    print(diagnosis.to_markdown())

See README.md for the full pattern explanation and the comparison vs
existing multi-agent observability tools.
"""

from .generator import LencioniDiagnostic, LLMClient
from .schema import (
    DYSFUNCTIONS,
    AgentMessage,
    DysfunctionEvidence,
    Intervention,
    LencioniDiagnosis,
    MultiAgentTrace,
)

__all__ = [
    "LencioniDiagnostic",
    "LLMClient",
    "AgentMessage",
    "DysfunctionEvidence",
    "Intervention",
    "LencioniDiagnosis",
    "MultiAgentTrace",
    "DYSFUNCTIONS",
]

__version__ = "0.0.5"
