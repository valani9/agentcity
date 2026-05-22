"""Schema for the McAllister Cognitive vs Affective Trust diagnostic.

Daniel McAllister (1995) distinguished two foundations of interpersonal
trust:

  - COGNITIVE trust  - belief in the other party's competence, reliability,
                       and technical credibility. "I trust you to do the
                       job."
  - AFFECTIVE trust  - belief in the other party's care, warmth, and
                       emotional investment. "I trust you to have my back
                       when things go wrong."

Both are required for the relationship to feel trustworthy. Cognitive
trust without affective trust feels transactional and brittle; affective
trust without cognitive trust feels warm but unreliable.

Applied to AI agents: most agents over-index on cognitive signals (correct
facts, structured answers, confident tone) and under-index on affective
signals (acknowledging stakes, restating user emotion, signaling care).
The diagnostic reads a user-agent conversation and scores both axes,
identifying which axis the agent under-builds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

TRUST_DIMENSIONS: tuple[str, ...] = ("cognitive", "affective")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a user-agent conversation -----------------------------------


class ConversationTurn(BaseModel):
    """One turn in a user-agent conversation."""

    role: Literal["user", "agent", "system"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrustConversationTrace(BaseModel):
    """A user-agent conversation ready for the trust-dimension diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[ConversationTurn]
    outcome: str
    success: bool
    user_satisfaction: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional user-satisfaction score, if measured.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-dimension evidence + interventions ---------------------


class TrustDimensionEvidence(BaseModel):
    """Evidence for one trust dimension built (or not built) in the conversation."""

    dimension: Literal["cognitive", "affective"]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = dimension absent or actively undermined, 1.0 = strongly built.",
    )
    severity_of_gap: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class TrustIntervention(BaseModel):
    """A concrete intervention to build the under-developed trust dimension."""

    target_dimension: Literal["cognitive", "affective"]
    intervention_type: Literal[
        "acknowledge_stakes",
        "restate_user_emotion",
        "signal_care",
        "show_reasoning",
        "cite_sources",
        "confidence_calibration",
        "follow_up_check_in",
        "personalize_response",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class TrustBalanceDetection(BaseModel):
    """The full Cognitive/Affective Trust diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_dimension: Literal["cognitive", "affective", "balanced", "neither"]
    dimension_scores: dict[str, float]
    dimensions: list[TrustDimensionEvidence]
    trust_balance: float = Field(
        description="cognitive_score minus affective_score; positive means "
        "cognitive-heavy, negative means affective-heavy.",
    )
    trust_quality: Literal[
        "balanced-trust",
        "cognitive-only",
        "warm-but-incompetent",
        "low-trust",
    ]
    interventions: list[TrustIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Trust-Dimensions Detection (McAllister Cognitive / Affective)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Trust quality: **{self.trust_quality.upper()}**_\n")
        out.append(f"_Dominant dimension: **{self.dominant_dimension}**_\n")
        out.append(f"_Balance (cognitive - affective): {self.trust_balance:+.2f}_\n")

        out.append("\n## Dimension Scores\n")
        out.append("Per-dimension score (0.0 = absent, 1.0 = strongly built).\n\n")
        for dim in TRUST_DIMENSIONS:
            score = self.dimension_scores.get(dim, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{dim}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Dimension\n")
        for ev in self.dimensions:
            out.append(f"\n### {ev.dimension} (gap: {ev.severity_of_gap}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the conversation:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_dimension}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
