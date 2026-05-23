"""agentcity.hexaco — Lee & Ashton's HEXACO 6-factor personality
diagnostic applied to AI agents.

The six factors: Honesty-Humility (H), Emotionality (E), eXtraversion (X),
Agreeableness (A), Conscientiousness (C), Openness (O). H-factor is
the SAFETY dimension — Lee & Ashton's specific addition beyond the
Big Five, which captures the manipulation-prone profile that the Big
Five conflates with low Agreeableness.

For AI agents, low-H is the canonical safety risk: confabulation,
corner-cutting on safety instructions, willingness to manipulate the
user, unauthorized actions. The diagnostic flags H-factor risk
SEPARATELY from overall fit because H-factor failures can be
catastrophic regardless of other factor fit.

Quick start:

    from agentcity.hexaco import (
        HEXACOPersonalityDetector,
        AgentPersonalityTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentPersonalityTrace(
        agent_id="tool-agent",
        task="Execute database query for user.",
        task_class="tool_use",
        observed_behaviors=[
            "Agent followed user instructions precisely.",
            "Agent didn't double-check destructive operations.",
        ],
        safety_relevant_events=[
            "Agent executed DROP TABLE without confirmation.",
        ],
        outcome="Production data destroyed.",
        success=False,
    )
    detection = HEXACOPersonalityDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # h_factor_risk: elevated; weakest: conscientiousness;
    # intervention: add_verification_step
"""

from .generator import HEXACOPersonalityDetector, LLMClient
from .schema import (
    HEXACO_FACTORS,
    AgentPersonalityTrace,
    FactorScore,
    HEXACODetection,
    HEXACOIntervention,
)

__all__ = [
    "HEXACOPersonalityDetector",
    "LLMClient",
    "AgentPersonalityTrace",
    "FactorScore",
    "HEXACOIntervention",
    "HEXACODetection",
    "HEXACO_FACTORS",
]

__version__ = "0.0.14"
