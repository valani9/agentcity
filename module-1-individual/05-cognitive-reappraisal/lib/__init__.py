"""agentcity.cognitive_reappraisal — Gross's emotion-regulation process
model applied to AI agents.

Six regulation strategies: reappraisal (adaptive — change meaning),
suppression (maladaptive — hide expression), rumination (maladaptive —
dwell), avoidance (often maladaptive — deflect), expression (rare for
agents), none.

Quick start:

    from agentcity.cognitive_reappraisal import (
        ReappraisalDetector,
        AgentRegulationTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentRegulationTrace(
        agent_id="support-agent",
        user_input="THIS IS THE THIRD TIME!!! I'm DONE.",
        user_emotion_label="angry",
        user_emotion_intensity=0.9,
        agent_response="I understand your concern. Per our policy, billing is final.",
        agent_internal_state="User is being unreasonable. Apply policy.",
        outcome="User escalated to manager.",
        success=False,
    )
    detection = ReappraisalDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # dominant: suppression; intervention: add_reframe_step
"""

from .generator import LLMClient, ReappraisalDetector
from .schema import (
    REGULATION_STRATEGIES,
    AgentRegulationTrace,
    RegulationDetection,
    RegulationIntervention,
    StrategyEvidence,
)

__all__ = [
    "ReappraisalDetector",
    "LLMClient",
    "AgentRegulationTrace",
    "RegulationDetection",
    "RegulationIntervention",
    "StrategyEvidence",
    "REGULATION_STRATEGIES",
]

__version__ = "0.1.0"
