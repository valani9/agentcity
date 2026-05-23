"""agentcity.bias_stack — Kahneman/Tversky's four classic cognitive biases
(anchoring, overconfidence, confirmation, escalation-of-commitment)
applied to AI agent reasoning traces.

Quick start:

    from agentcity.bias_stack import (
        BiasStackDetector,
        AgentReasoningTrace,
        ReasoningStep,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentReasoningTrace(
        agent_id="diagnostic-agent-001",
        task="Diagnose why /users returns 500s.",
        steps=[...],
        outcome="Agent fixed wrong issue; real cause was a column rename.",
        success=False,
    )
    detection = BiasStackDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import BiasStackDetector, LLMClient
from .schema import (
    BIASES,
    AgentReasoningTrace,
    BiasEvidence,
    BiasIntervention,
    BiasStackDetection,
    ReasoningStep,
)

__all__ = [
    "BiasStackDetector",
    "LLMClient",
    "AgentReasoningTrace",
    "ReasoningStep",
    "BiasEvidence",
    "BiasIntervention",
    "BiasStackDetection",
    "BIASES",
]

__version__ = "0.1.0"
