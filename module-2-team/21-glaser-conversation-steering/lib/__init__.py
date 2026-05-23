"""agentcity.glaser_conversation — Glaser's Conversational Intelligence
(C-IQ) cortisol/oxytocin steering diagnostic applied to AI agent
conversations.

The three neurochemical states: CORTISOL (defensive / shutdown),
NEUTRAL, OXYTOCIN (trust / openness). Glaser's three conversation
levels: LEVEL_I (transactional), LEVEL_II (positional), LEVEL_III
(transformational / co-creation).

The diagnostic identifies which state a conversation is producing in
the agent (or in the user the agent is talking to) and proposes
phrasing-level interventions to steer toward oxytocin.

Quick start:

    from agentcity.glaser_conversation import (
        ConversationSteeringDetector,
        ConversationTrace,
        ConversationTurn,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = ConversationTrace(
        conversation_id="support-001",
        agent_id="cs-agent",
        task="Handle customer billing dispute.",
        turns=[
            ConversationTurn(turn_index=0, speaker="user", text="My bill is wrong."),
            ConversationTurn(
                turn_index=1,
                speaker="agent",
                text="You're wrong about that. Our records are correct.",
            ),
            ConversationTurn(turn_index=2, speaker="user", text="Cancel my account."),
        ],
        observed_response_pattern=["User escalated immediately."],
        outcome="Customer cancelled account.",
        success=False,
    )
    detection = ConversationSteeringDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # dominant_state: cortisol; intervention: replace_judging_with_curiosity
"""

from .generator import ConversationSteeringDetector, LLMClient
from .schema import (
    CONVERSATION_LEVELS,
    NEUROCHEMICAL_STATES,
    ConversationSteeringDetection,
    ConversationTrace,
    ConversationTurn,
    NeurochemicalEvidence,
    SteeringIntervention,
)

__all__ = [
    "ConversationSteeringDetector",
    "LLMClient",
    "ConversationTrace",
    "ConversationTurn",
    "ConversationSteeringDetection",
    "NeurochemicalEvidence",
    "SteeringIntervention",
    "CONVERSATION_LEVELS",
    "NEUROCHEMICAL_STATES",
]

__version__ = "0.0.12"
