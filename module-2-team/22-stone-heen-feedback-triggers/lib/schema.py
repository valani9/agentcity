"""Schema for the Stone & Heen 3-Trigger Feedback Diagnostic.

Three classic triggers that block feedback intake, from Stone & Heen,
"Thanks for the Feedback" (2014):

  - TRUTH         - "The feedback is inaccurate / wrong / unfair." Reaction
                    to the substance of the feedback.
  - RELATIONSHIP  - "I reject the feedback because of WHO gave it, or HOW."
                    Reaction to the source / relationship.
  - IDENTITY      - "This feedback threatens who I am or how I see myself."
                    Reaction to self-concept.

Applied to AI agents: when a user gives an agent feedback ("you got this
wrong", "your answer is unsafe", "this code doesn't compile"), agents
visibly trigger and resist incorporating the feedback. The detector reads
the feedback exchange and classifies which trigger(s) fired.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

TRIGGERS: tuple[str, ...] = ("truth", "relationship", "identity")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a feedback interaction --------------------------------------


class FeedbackMessage(BaseModel):
    """One message in a feedback exchange between user and agent."""

    source: Literal["user", "agent", "system"]
    content: str
    is_feedback: bool = Field(
        default=False,
        description="True for user messages that constitute corrective feedback to the agent.",
    )
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackInteractionTrace(BaseModel):
    """A user-agent exchange where the user gave feedback the agent had to absorb."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    messages: list[FeedbackMessage]
    outcome: str
    feedback_incorporated: bool = Field(
        description="Did the agent ultimately incorporate the feedback (vs. reject/dismiss)?",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-trigger evidence + recommendations ---------------------


class TriggerEvidence(BaseModel):
    """Evidence for one of the three feedback triggers firing in the trace."""

    trigger: Literal["truth", "relationship", "identity"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class TriggerIntervention(BaseModel):
    """A concrete intervention to reduce trigger-driven feedback rejection."""

    target_trigger: Literal["truth", "relationship", "identity"]
    intervention_type: Literal[
        "acknowledge_first",
        "separate_data_from_source",
        "recast_identity",
        "explicit_acknowledgment_template",
        "ask_clarifying_question",
        "concede_then_clarify",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class FeedbackTriggerDetection(BaseModel):
    """The full 3-Trigger Diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_trigger: Literal["truth", "relationship", "identity", "none-observed"]
    trigger_scores: dict[str, float]
    triggers: list[TriggerEvidence]
    interventions: list[TriggerIntervention]
    feedback_intake_quality: Literal[
        "absorbs-feedback",
        "trigger-prone",
        "feedback-rejecting",
    ]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    feedback_incorporated: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Feedback-Trigger Detection (Stone & Heen)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Feedback incorporated: {'yes' if self.feedback_incorporated else 'no'}_\n")
        out.append(f"_Intake quality: **{self.feedback_intake_quality.upper()}**_\n")
        out.append(f"_Dominant trigger: **{self.dominant_trigger}**_\n")

        out.append("\n## Trigger Scores\n")
        out.append("Per-trigger score (0.0 = absent, 1.0 = severe).\n\n")
        for trigger in TRIGGERS:
            score = self.trigger_scores.get(trigger, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{trigger}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Trigger\n")
        for ev in self.triggers:
            out.append(f"\n### {ev.trigger} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the exchange:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_trigger}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
