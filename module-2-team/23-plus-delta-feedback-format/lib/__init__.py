"""agentcity.plus_delta — structured plus/delta inter-agent feedback
format generator. From the facilitator canon (Joiner Associates; Brené
Brown, "Dare to Lead", 2018; retrospective-meeting literature).

Fourth generative pattern in AgentCity (alongside #13 GRPI, #24 SMART,
#25 Group Decision Models).

Replaces unstructured "LGTM" / "looks good" / "could be better" feedback
with explicit:
  - PLUS  - what worked. Behavioral. Specific. Reusable.
  - DELTA - what to do differently. Behavioral. Names the alternative.

Quick start:

    from agentcity.plus_delta import (
        PlusDeltaFeedbackGenerator,
        FeedbackRequest,
    )
    from agentcity.aar.clients import AnthropicClient

    request = FeedbackRequest(
        reviewer_agent="senior-eng",
        subject_agent="junior-eng",
        task_context="Refactor the auth middleware for clarity.",
        contribution_summary="Rewrote auth middleware in 3 modules.",
        contribution_artifact="<the actual code diff>",
        success_criteria=[
            "Code is readable by a new engineer in <10 minutes",
            "No new dependencies",
            "Tests still pass",
        ],
        style="balanced",
    )
    feedback = PlusDeltaFeedbackGenerator(AnthropicClient()).run(request)
    print(feedback.to_markdown())
    # to_inline_feedback() also available for chat-style returns.
"""

from .generator import LLMClient, PlusDeltaFeedbackGenerator
from .schema import (
    Commitment,
    DeltaItem,
    FeedbackRequest,
    PlusDeltaFeedback,
    PlusItem,
)

__all__ = [
    "PlusDeltaFeedbackGenerator",
    "LLMClient",
    "FeedbackRequest",
    "PlusItem",
    "DeltaItem",
    "Commitment",
    "PlusDeltaFeedback",
]

__version__ = "0.1.0"
