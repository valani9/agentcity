"""agentcity.sdt_reward — Deci & Ryan's Self-Determination Theory
intrinsic reward shaping diagnostic for AI agents.

The three basic psychological needs: AUTONOMY (choice / self-direction),
COMPETENCE (effectiveness / mastery growth), RELATEDNESS (connection to
others / purpose). When all three are met, intrinsic motivation is high.
When any is undermined, motivation degrades.

KEY INSIGHT: external reward signals (rating threats, leaderboards,
cost caps as primary drivers) can UNDERMINE intrinsic motivation by
reducing the autonomy signal — the "overjustification effect."

Quick start:

    from agentcity.sdt_reward import (
        SDTRewardDetector,
        AgentSDTTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentSDTTrace(
        agent_id="research-agent",
        task="Explore design space for new feature.",
        task_class="research_exploration",
        system_prompt="You MUST follow the rules. You will be RATED on accuracy.",
        extrinsic_signals=[
            "Threat: low ratings will be flagged.",
            "Cost cap: must complete in <5 tool calls.",
        ],
        observed_behaviors=[
            "Agent restated established patterns rather than exploring.",
            "Agent refused to deviate from the prompt structure.",
        ],
        outcome="Output is rigid; no novel directions surfaced.",
        success=False,
    )
    detection = SDTRewardDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # most_undermined_need: autonomy; intervention: remove_external_reward_threat
"""

from .generator import LLMClient, SDTRewardDetector
from .schema import (
    SDT_NEEDS,
    AgentSDTTrace,
    NeedScore,
    SDTDetection,
    SDTIntervention,
)

__all__ = [
    "SDTRewardDetector",
    "LLMClient",
    "AgentSDTTrace",
    "NeedScore",
    "SDTDetection",
    "SDTIntervention",
    "SDT_NEEDS",
]

__version__ = "0.1.0"
