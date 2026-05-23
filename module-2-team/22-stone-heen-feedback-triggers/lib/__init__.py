"""agentcity.feedback_triggers — Stone & Heen's three feedback triggers
(truth, relationship, identity) applied to user-agent feedback exchanges.

From "Thanks for the Feedback: The Science and Art of Receiving Feedback
Well" (Stone & Heen, 2014). When an AI agent receives corrective feedback
from a user, three classic triggers can block intake:

  - TRUTH         - the agent reacts to the substance of the feedback
  - RELATIONSHIP  - the agent reacts to who is giving it
  - IDENTITY      - the agent reacts to what the feedback says about itself

The detector reads a feedback exchange and classifies which trigger(s)
fired, with concrete interventions for the dominant trigger.

Quick start:

    from agentcity.feedback_triggers import (
        FeedbackTriggerDetector,
        FeedbackInteractionTrace,
        FeedbackMessage,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = FeedbackInteractionTrace(
        agent_id="support-agent-001",
        task="Help the user fix their broken script.",
        messages=[...],
        outcome="Agent never incorporated the user's correction.",
        feedback_incorporated=False,
    )
    detection = FeedbackTriggerDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import FeedbackTriggerDetector, LLMClient
from .schema import (
    TRIGGERS,
    FeedbackInteractionTrace,
    FeedbackMessage,
    FeedbackTriggerDetection,
    TriggerEvidence,
    TriggerIntervention,
)

__all__ = [
    "FeedbackTriggerDetector",
    "LLMClient",
    "FeedbackInteractionTrace",
    "FeedbackMessage",
    "TriggerEvidence",
    "TriggerIntervention",
    "FeedbackTriggerDetection",
    "TRIGGERS",
]

__version__ = "0.1.0"
