"""agentcity.social_loafing — Latané, Williams & Harkins's social loafing
phenomenon (1979) applied to multi-agent AI systems.

When N agents are assigned to a task, substantive contribution often
pools to 1-2 agents while others rubber-stamp, paraphrase, or produce
cosmetic work. The detector reads a multi-agent execution trace and
identifies loafing agents with concrete role-redesign interventions.

Quick start:

    from agentcity.social_loafing import (
        SocialLoafingDetector,
        MultiAgentTaskTrace,
        AgentMessage,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = MultiAgentTaskTrace(
        team_id="research-crew-001",
        task="Compile a market-research report on prompt-injection defenses.",
        agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
        messages=[...],
        outcome="Lead and researcher did all substantive work; others rubber-stamped.",
        success=True,
    )
    detection = SocialLoafingDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LLMClient, SocialLoafingDetector
from .schema import (
    AgentContribution,
    AgentMessage,
    LoafingIntervention,
    MultiAgentTaskTrace,
    SocialLoafingDetection,
)

__all__ = [
    "SocialLoafingDetector",
    "LLMClient",
    "MultiAgentTaskTrace",
    "AgentMessage",
    "AgentContribution",
    "LoafingIntervention",
    "SocialLoafingDetection",
]

__version__ = "0.1.0"
