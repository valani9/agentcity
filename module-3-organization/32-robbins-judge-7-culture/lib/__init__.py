"""agentcity.robbins_culture — Robbins & Judge's 7-dimension culture
profile applied to AI agents. Second Module 3 (organizational) pattern.

The seven dimensions: innovation, attention_to_detail, outcome, people,
team, aggressiveness, stability. Each task class implies a different
target profile; the diagnostic identifies where the agent's observed
profile fails to match.

Where Schein's Iceberg (#31) measures *coherence across layers*, this
pattern measures *fit to task class*.

Quick start:

    from agentcity.robbins_culture import (
        CultureProfileDetector,
        AgentCultureTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentCultureTrace(
        agent_id="research-agent-001",
        task="Explore design space for a new feature.",
        task_class="research_exploration",
        system_prompt="Be thorough; double-check every claim with citations.",
        observed_behaviors=["Agent over-cites; never proposes novel directions."],
        outcome="Output is comprehensive but stale.",
        success=False,
    )
    detection = CultureProfileDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # biggest_gap: innovation; intervention: rewrite_system_prompt + adjust_temperature
"""

from .generator import CultureProfileDetector, LLMClient
from .schema import (
    CULTURE_CHARACTERISTICS,
    AgentCultureTrace,
    CharacteristicScore,
    CultureIntervention,
    CultureProfileDetection,
)

__all__ = [
    "CultureProfileDetector",
    "LLMClient",
    "AgentCultureTrace",
    "CharacteristicScore",
    "CultureIntervention",
    "CultureProfileDetection",
    "CULTURE_CHARACTERISTICS",
]

__version__ = "0.1.0"
