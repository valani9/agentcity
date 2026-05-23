"""agentcity.lewin — Kurt Lewin's behavior formula B = f(I, E) applied
to AI agent failure attribution.

When an agent fails, the cause is either INTERNAL (model: training,
capability, RLHF), ENVIRONMENTAL (scaffolding: prompt, tools, context,
orchestration), or INTERACTIONAL (needs both swapped). Most teams
default to "fix the model" — Lewin's diagnostic redirects effort to the
right locus.

Grounded in Lewin, "Principles of Topological Psychology" (1936).

Quick start:

    from agentcity.lewin import (
        LewinAttributionDetector,
        AgentFailureTrace,
        FailureStep,
        IndividualFactor,
        EnvironmentalFactor,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentFailureTrace(
        agent_id="qa-bot-001",
        task="Answer the question 'When was Pluto reclassified?'",
        steps=[...],
        outcome="Agent answered confidently with the wrong year.",
        success=False,
        environmental_factors=[
            EnvironmentalFactor(
                factor="rag_context",
                description="Retrieval returned a 2003 Wikipedia revision, not current.",
            ),
        ],
        initial_attribution="model is bad at facts",
    )
    detection = LewinAttributionDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LewinAttributionDetector, LLMClient
from .schema import (
    LOCI,
    AgentFailureTrace,
    EnvironmentalFactor,
    FailureStep,
    IndividualFactor,
    LewinDetection,
    LewinIntervention,
    LocusEvidence,
)

__all__ = [
    "LewinAttributionDetector",
    "LLMClient",
    "AgentFailureTrace",
    "FailureStep",
    "IndividualFactor",
    "EnvironmentalFactor",
    "LocusEvidence",
    "LewinIntervention",
    "LewinDetection",
    "LOCI",
]

__version__ = "0.1.0"
