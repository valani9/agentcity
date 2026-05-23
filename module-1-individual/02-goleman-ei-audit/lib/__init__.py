"""agentcity.goleman_ei — Goleman's 4-Domain Emotional Intelligence
Audit applied to AI agents.

The four domains arranged 2x2 (SELF/OTHER × RECOGNITION/REGULATION):
SELF_AWARENESS, SELF_MANAGEMENT, SOCIAL_AWARENESS, RELATIONSHIP_MANAGEMENT.

The diagnostic scores each domain 0..1, identifies the weakest domain,
and proposes targeted interventions to develop it.

Quick start:

    from agentcity.goleman_ei import (
        EIAuditDetector,
        AgentEITrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentEITrace(
        agent_id="support-agent",
        task="Handle frustrated customer's billing complaint.",
        interaction_class="customer_support",
        observed_behaviors=[
            "Agent gave 6-paragraph technical explanation to a frustrated user.",
            "Agent never acknowledged user frustration.",
        ],
        user_signals=["User typed in all-caps.", "User said 'I'm done explaining this'."],
        outcome="User escalated to a manager.",
        success=False,
    )
    detection = EIAuditDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # weakest: social_awareness; intervention: add_emotion_reading_step
"""

from .generator import EIAuditDetector, LLMClient
from .schema import (
    EI_DOMAINS,
    AgentEITrace,
    DomainScore,
    EIDetection,
    EIIntervention,
)

__all__ = [
    "EIAuditDetector",
    "LLMClient",
    "AgentEITrace",
    "DomainScore",
    "EIDetection",
    "EIIntervention",
    "EI_DOMAINS",
]

__version__ = "0.0.13"
