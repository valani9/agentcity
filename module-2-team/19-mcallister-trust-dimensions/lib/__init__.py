"""agentcity.mcallister_trust — McAllister's cognitive vs affective trust
dimensions applied to user-agent conversations.

From McAllister (1995), "Affect- and Cognition-Based Trust as Foundations
for Interpersonal Cooperation in Organizations" (Academy of Management
Journal, 38(1)). Trust has two foundations:

  - COGNITIVE trust  - "I trust your competence."
  - AFFECTIVE trust  - "I trust your care."

Most AI agents over-index on cognitive and under-build affective. The
detector reads a user-agent conversation and reports the balance.

Quick start:

    from agentcity.mcallister_trust import (
        TrustBalanceDetector,
        TrustConversationTrace,
        ConversationTurn,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = TrustConversationTrace(
        agent_id="support-agent-001",
        task="Help the user through a billing dispute.",
        turns=[...],
        outcome="Agent resolved the dispute correctly but user felt unheard.",
        success=True,
    )
    detection = TrustBalanceDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LLMClient, TrustBalanceDetector
from .schema import (
    TRUST_DIMENSIONS,
    ConversationTurn,
    TrustBalanceDetection,
    TrustConversationTrace,
    TrustDimensionEvidence,
    TrustIntervention,
)

__all__ = [
    "TrustBalanceDetector",
    "LLMClient",
    "TrustConversationTrace",
    "ConversationTurn",
    "TrustDimensionEvidence",
    "TrustIntervention",
    "TrustBalanceDetection",
    "TRUST_DIMENSIONS",
]

__version__ = "0.0.7"
