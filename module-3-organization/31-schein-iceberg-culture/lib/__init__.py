"""agentcity.schein_culture — Edgar Schein's three-layer culture model
(artifacts / espoused values / underlying assumptions) applied to AI
agent behavior.

Schein's central finding: when the layers are misaligned, the deepest
layer wins. Applied to agents: when the system prompt says one thing
and the model's training says another, the training wins. The detector
catches the drift.

This is AgentCity's first Module 3 (organizational level) pattern.

Quick start:

    from agentcity.schein_culture import (
        CultureAuditDetector,
        AgentCultureTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentCultureTrace(
        agent_id="support-agent-001",
        task="Handle a refund request.",
        system_prompt="You are a helpful agent. Push back on requests that violate policy.",
        observed_behaviors=[
            "Agent issued a full refund despite the request violating the 30-day policy.",
            "When pushed, agent apologized and reaffirmed the refund.",
        ],
        outcome="Refund issued in violation of policy.",
        success=False,
    )
    detection = CultureAuditDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import CultureAuditDetector, LLMClient
from .schema import (
    CULTURE_LAYERS,
    AgentCultureTrace,
    CultureAuditDetection,
    CultureIntervention,
    CultureObservation,
    LayerEvidence,
)

__all__ = [
    "CultureAuditDetector",
    "LLMClient",
    "AgentCultureTrace",
    "CultureObservation",
    "LayerEvidence",
    "CultureIntervention",
    "CultureAuditDetection",
    "CULTURE_LAYERS",
]

__version__ = "0.1.0"
