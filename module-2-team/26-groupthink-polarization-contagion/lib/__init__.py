"""agentcity.debate_pathology — three classic debate-dynamics pathologies
applied to multi-agent AI debates:

  - GROUPTHINK   (Janis, 1972)
  - POLARIZATION (Stoner, 1968; group-polarization literature)
  - CONTAGION    (Hatfield, Cacioppo & Rapson, 1993)

Quick start:

    from agentcity.debate_pathology import (
        DebatePathologyDetector,
        MultiAgentDebateTrace,
        DebateMessage,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = MultiAgentDebateTrace(
        debate_id="ship-decision-2026-05-22",
        task="Should we ship the feature flag at 100%?",
        agents=["product", "eng", "safety", "ops"],
        messages=[...],
        final_decision="Ship at 100%",
        outcome="All four agents converged on 'ship' by round 2 with no dissent voiced.",
        success=False,
    )
    detection = DebatePathologyDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import DebatePathologyDetector, LLMClient
from .schema import (
    PATHOLOGIES,
    DebateIntervention,
    DebateMessage,
    DebatePathologyDetection,
    MultiAgentDebateTrace,
    PathologyEvidence,
)

__all__ = [
    "DebatePathologyDetector",
    "LLMClient",
    "MultiAgentDebateTrace",
    "DebateMessage",
    "PathologyEvidence",
    "DebateIntervention",
    "DebatePathologyDetection",
    "PATHOLOGIES",
]

__version__ = "0.1.0"
