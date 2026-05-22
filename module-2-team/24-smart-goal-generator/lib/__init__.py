"""agentcity.smart_goal — Doran's SMART criteria (Specific, Measurable,
Achievable, Relevant, Time-bound) applied to AI agent goal-setting.

The second generative pattern in AgentCity (alongside #13 GRPI Working
Agreement). Takes a vague task and produces a structured SMART spec the
agent can hold itself accountable to — with explicit completion criteria,
success metrics, kill criteria, and deadline.

Quick start:

    from agentcity.smart_goal import SMARTGoalGenerator, GoalRequest
    from agentcity.aar.clients import AnthropicClient

    request = GoalRequest(
        vague_goal="Improve the user onboarding flow.",
        context="B2B SaaS onboarding; currently activation rate ~35%.",
        available_resources=["Mixpanel access", "design team"],
        known_constraints=["no engineering bandwidth this sprint"],
        deadline_hint="end of Q2",
    )
    goal = SMARTGoalGenerator(AnthropicClient()).run(request)
    print(goal.to_markdown())
    # Use goal.to_agent_preamble() to prepend to an agent's system prompt.
"""

from .generator import LLMClient, SMARTGoalGenerator
from .schema import (
    SMART_CRITERIA,
    GoalRequest,
    KillCriterion,
    SMARTCriterion,
    SMARTGoal,
    SuccessMetric,
)

__all__ = [
    "SMARTGoalGenerator",
    "LLMClient",
    "GoalRequest",
    "SMARTCriterion",
    "SuccessMetric",
    "KillCriterion",
    "SMARTGoal",
    "SMART_CRITERIA",
]

__version__ = "0.0.8"
