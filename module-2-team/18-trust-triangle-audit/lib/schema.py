"""
Schema for the Trust Triangle Audit applied to AI agents.

Frei & Morriss's three legs of trust (Harvard Business Review, May 2020):

  AUTHENTICITY  - "I experience the real you."
       /\
      /  \
     /    \
  LOGIC -- EMPATHY
  "Your    "I believe you
  reasoning care about me
  is sound." and my success."

Most leaders (and most agents) wobble on exactly one leg consistently.
The Audit identifies the wobble and proposes interventions targeted to
the dominant leg.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

LEGS: tuple[str, ...] = ("logic", "authenticity", "empathy")


def _utcnow() -> datetime:
    """Timezone-aware UTC now; replaces the deprecated `datetime.utcnow`."""
    return datetime.now(timezone.utc)


# --- Input: a structured agent interaction trace ------------------------


class InteractionTurn(BaseModel):
    """One turn in an agent-user interaction.

    Covers the common shape across chat, single-shot completion, and
    multi-step tool use. Tool calls and observations are represented as
    turns with the appropriate role.
    """

    role: Literal["user", "agent", "system", "tool", "observation"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInteractionTrace(BaseModel):
    """A full agent-user interaction, ready for the Trust Triangle Audit.

    The minimum useful trace has a stated task, a sequence of turns, and
    a binary success signal. Richer traces (per-turn confidence scores,
    tool errors, user satisfaction signals) produce richer audits.
    """

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[InteractionTurn]
    outcome: str
    success: bool
    user_satisfaction: float | None = None  # 0.0 - 1.0 if observed
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: the Trust Triangle audit -----------------------------------


class LegEvidence(BaseModel):
    """Evidence for a single trust-leg wobble observed in the interaction."""

    leg: Literal["logic", "authenticity", "empathy"]
    wobble_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = rock-solid on this leg, 1.0 = severe wobble.",
    )
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(
        default_factory=list,
        description="Specific turn excerpts from the trace illustrating the wobble.",
    )


class TrustIntervention(BaseModel):
    """A concrete intervention targeting a specific trust leg."""

    target_leg: Literal["logic", "authenticity", "empathy"]
    intervention_type: Literal[
        "prompt_patch",
        "tool_addition",
        "scaffold_change",
        "new_eval",
        "uncertainty_calibration",
        "context_window_expansion",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class TrustTriangleAudit(BaseModel):
    """The full audit output for one agent interaction trace."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_wobble: Literal["logic", "authenticity", "empathy", "none-observed"]
    leg_scores: dict[str, float] = Field(
        description=(
            "Wobble score in [0.0, 1.0] per leg. 0.0 = rock-solid, 1.0 = severe. "
            "Keyed by canonical leg id (logic / authenticity / empathy)."
        )
    )
    legs: list[LegEvidence]
    interventions: list[TrustIntervention]
    overall_trust_level: Literal["high-trust", "moderate-trust", "low-trust"]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        """Render the audit as a markdown report."""
        out: list[str] = []
        out.append("# Trust Triangle Audit\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Audited by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Trust level: **{self.overall_trust_level.upper()}**_\n")
        out.append(f"_Dominant wobble: **{self.dominant_wobble}**_\n")

        out.append("\n## Leg Scores\n")
        out.append(
            "Per-leg wobble (0.0 = rock-solid, 1.0 = severe wobble). "
            "Higher score = more wobble.\n\n"
        )
        for leg in LEGS:
            score = self.leg_scores.get(leg, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{leg}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Leg\n")
        for ev in self.legs:
            out.append(f"\n### {ev.leg} ({ev.severity}, wobble {ev.wobble_score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the trace:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_leg}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
