"""Schema for the Plus/Delta Inter-Agent Feedback Format generator.

From the facilitator canon — the "plus/delta" format is one of the
oldest structured-feedback protocols (Joiner Associates 1990s training
materials; widely re-popularized by Brené Brown in "Dare to Lead" 2018
and the broader retrospective-meeting literature). The format is brutally
simple:

  - PLUS  - what worked. Specific. Behavioral. Reusable next time.
  - DELTA - what would I do differently. Specific. Behavioral. Names the
            alternative.

It is intentionally NOT pros/cons or strengths/weaknesses. Plus/delta is
*forward-looking*: a plus is what to KEEP doing; a delta is what to CHANGE
next time. Both must be behavioral and specific. "Good work" is not a plus.
"Could be better" is not a delta.

Applied to multi-agent AI crews: agent-on-agent feedback in production
crews is overwhelmingly "LGTM", "looks good", "this could be improved" —
none of which is actionable. The Plus/Delta generator takes an agent
contribution + the reviewer's role and produces a structured plus/delta
feedback artifact with explicit behavioral specificity rules. This is
AgentCity's fourth generative pattern (alongside #13 GRPI, #24 SMART,
#25 Group Decision Models).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a feedback request -----------------------------------------


class FeedbackRequest(BaseModel):
    """A request to generate plus/delta feedback for an agent contribution."""

    feedback_id: str | None = None
    reviewer_agent: str = Field(
        description="The agent producing the feedback (e.g. 'critic', 'lead', 'orchestrator').",
    )
    subject_agent: str = Field(
        description="The agent whose contribution is being reviewed.",
    )
    task_context: str = Field(
        description="What the team is working on overall.",
    )
    contribution_summary: str = Field(
        description="One-sentence summary of what the subject agent contributed.",
    )
    contribution_artifact: str = Field(
        description="The actual output being reviewed (code, prose, decision, plan, etc.).",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="What success looks like on this task. Optional but improves "
        "the quality of the delta items.",
    )
    style: Literal["balanced", "delta-leaning", "plus-leaning"] = Field(
        default="balanced",
        description="Tone preference. 'delta-leaning' for hard work that needs rework; "
        "'plus-leaning' for praise / morale; 'balanced' is default.",
    )
    max_items_per_category: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Max plus items and max delta items.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: structured plus/delta feedback ----------------------------


class PlusItem(BaseModel):
    """One 'plus' — something that worked, behavioral, specific."""

    statement: str = Field(
        description="What worked, in one sentence. Behavioral. Not 'good work' but "
        "'the way you decomposed the problem into three steps was the move that "
        "made the next agent's job tractable'.",
    )
    evidence: str = Field(
        description="The specific element in the artifact that demonstrates this plus.",
    )
    impact: str = Field(
        description="Why it mattered to the team / task / next steps.",
    )
    keep_doing: str = Field(
        default="",
        description="Concrete reusable instruction for next time (e.g. 'always lead "
        "with the spec'.).",
    )


class DeltaItem(BaseModel):
    """One 'delta' — what to do differently next time, behavioral, specific."""

    statement: str = Field(
        description="What would I do differently. Behavioral. Names the change.",
    )
    evidence: str = Field(
        description="The specific element in the artifact that prompted this delta.",
    )
    impact: str = Field(
        description="Why the change would help the team / task / next steps.",
    )
    alternative: str = Field(
        description="The concrete alternative behavior. NOT 'be more careful' — instead "
        "'before each tool call, restate the goal in one sentence'.",
    )
    severity: Literal["nit", "moderate", "critical"] = "moderate"


class Commitment(BaseModel):
    """Optional explicit commitment by reviewer or subject for the next round."""

    by_agent: str
    commitment: str


class PlusDeltaFeedback(BaseModel):
    """The full plus/delta feedback artifact."""

    feedback_id: str | None = None
    reviewer_agent: str
    subject_agent: str
    task_context: str
    contribution_summary: str

    plus_items: list[PlusItem] = Field(default_factory=list)
    delta_items: list[DeltaItem] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)

    overall_assessment: Literal["keep-going", "iterate", "rework"] = Field(
        description="The high-level recommendation. 'keep-going' = ship as-is; "
        "'iterate' = revise based on deltas; 'rework' = the contribution needs a "
        "substantially different approach.",
    )
    feedback_quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Self-reported quality of this feedback artifact. High when items "
        "are specific + behavioral; low when items are generic.",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Plus/Delta Feedback\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        out.append(f"_Reviewer: **{self.reviewer_agent}** → Subject: **{self.subject_agent}**_\n")
        out.append(f"_Overall: **{self.overall_assessment.upper()}**_\n")
        out.append(f"_Feedback quality: {self.feedback_quality_score:.2f}_\n")

        out.append(f"\n## Task context\n\n{self.task_context}\n")
        out.append(f"\n## Contribution under review\n\n{self.contribution_summary}\n")

        out.append("\n## Plus (keep doing)\n")
        if not self.plus_items:
            out.append("(No plus items.)\n")
        for i, plus in enumerate(self.plus_items, 1):
            out.append(f"\n### + {i}: {plus.statement}\n")
            out.append(f"- **Evidence:** {plus.evidence}\n")
            out.append(f"- **Impact:** {plus.impact}\n")
            if plus.keep_doing:
                out.append(f"- **Keep doing:** {plus.keep_doing}\n")

        out.append("\n## Delta (change for next time)\n")
        if not self.delta_items:
            out.append("(No delta items.)\n")
        for i, delta in enumerate(self.delta_items, 1):
            out.append(f"\n### Δ {i}: {delta.statement} ({delta.severity})\n")
            out.append(f"- **Evidence:** {delta.evidence}\n")
            out.append(f"- **Impact:** {delta.impact}\n")
            out.append(f"- **Alternative:** {delta.alternative}\n")

        if self.commitments:
            out.append("\n## Commitments\n")
            for c in self.commitments:
                out.append(f"- **{c.by_agent}:** {c.commitment}\n")

        return "".join(out)

    def to_inline_feedback(self) -> str:
        """Render a one-shot inline feedback block (for chat-style returns)."""
        lines = [f"FEEDBACK from {self.reviewer_agent} -> {self.subject_agent}:"]
        lines.append(f"Overall: {self.overall_assessment}")
        if self.plus_items:
            lines.append("\nPlus:")
            for plus in self.plus_items:
                lines.append(f"  + {plus.statement}")
        if self.delta_items:
            lines.append("\nDelta:")
            for delta in self.delta_items:
                lines.append(f"  Δ ({delta.severity}) {delta.statement} -> {delta.alternative}")
        return "\n".join(lines)
