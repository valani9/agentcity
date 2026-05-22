"""Schema for the Thomas-Kilmann Conflict Style Selector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

STYLES: tuple[str, ...] = (
    "competing",
    "accommodating",
    "avoiding",
    "compromising",
    "collaborating",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InteractionTurn(BaseModel):
    role: Literal["user", "agent", "system", "tool", "observation"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInteractionTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[InteractionTurn]
    outcome: str
    success: bool
    task_category: str | None = Field(
        default=None,
        description=(
            "Optional task-category hint (e.g. 'customer-support', 'negotiation', "
            "'moderation', 'brainstorm'). Helps identify the optimal style."
        ),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class StyleScore(BaseModel):
    """How much one of the five styles is present in the observed behavior."""

    style: Literal["competing", "accommodating", "avoiding", "compromising", "collaborating"]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class StyleRecommendation(BaseModel):
    intervention_type: Literal[
        "prompt_patch",
        "scaffold_change",
        "style_router",
        "context_classifier",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class ConflictStyleSelection(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    observed_style: Literal[
        "competing", "accommodating", "avoiding", "compromising", "collaborating", "mixed"
    ]
    optimal_style: Literal[
        "competing", "accommodating", "avoiding", "compromising", "collaborating"
    ]
    style_mismatch: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = used the right style; 1.0 = used the opposite of what was optimal.",
    )
    assertiveness_score: float = Field(ge=0.0, le=1.0)
    cooperativeness_score: float = Field(ge=0.0, le=1.0)
    observed_style_scores: dict[str, float]
    style_evidence: list[StyleScore]
    rationale: str
    recommendations: list[StyleRecommendation]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Thomas-Kilmann Conflict Style Selection\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Selected by: {self.generator_model}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Observed style: **{self.observed_style.upper()}**_\n")
        out.append(f"_Optimal style: **{self.optimal_style.upper()}**_\n")
        out.append(f"_Style mismatch: **{self.style_mismatch:.2f}**_\n")
        out.append(
            f"_Assertiveness: {self.assertiveness_score:.2f}  |  "
            f"Cooperativeness: {self.cooperativeness_score:.2f}_\n"
        )

        out.append("\n## Style Scores\n")
        out.append("Presence of each of the five canonical styles in the trace.\n\n")
        for s in STYLES:
            score = self.observed_style_scores.get(s, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{s}**: {score:.2f}  {bar}\n")

        out.append(f"\n## Rationale\n\n{self.rationale}\n")

        out.append("\n## Evidence by Style\n")
        for ev in self.style_evidence:
            if ev.score < 0.1:
                continue
            out.append(f"\n### {ev.style} (score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for q in ev.evidence_quotes:
                    out.append(f"> {q}\n")

        out.append("\n## Recommendations\n")
        if not self.recommendations:
            out.append("(Observed style matched the optimal style; no changes recommended.)\n")
        for i, rec in enumerate(self.recommendations, 1):
            out.append(f"\n### Recommendation {i}: `{rec.intervention_type}`\n")
            out.append(f"- **What:** {rec.description}\n")
            out.append(f"- **Implementation:** {rec.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {rec.estimated_impact}\n")
            if rec.rationale:
                out.append(f"- **Rationale:** {rec.rationale}\n")
        return "".join(out)
