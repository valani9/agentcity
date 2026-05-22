"""Schema for the Groupthink / Polarization / Emotional Contagion Detector.

Three classic dysfunctional dynamics in group decision-making, applied to
multi-agent debate:

  - GROUPTHINK   - Janis (1972, "Victims of Groupthink"). The group converges
                   too quickly on a single position. Dissent gets suppressed.
                   Illusion of unanimity. Self-censorship.

  - POLARIZATION - Stoner (1968) on "risky shift" and the broader
                   group-polarization literature. Each round of debate pushes
                   the group's position further toward an extreme rather than
                   the deliberative average of starting positions.

  - CONTAGION    - Hatfield, Cacioppo & Rapson (1993, "Emotional Contagion").
                   The emotional tone of one agent spreads to others. Heated
                   tone propagates across turns; calm tone propagates across
                   turns. Tone dominates content.

The detector reads a multi-agent debate trace and scores all three
dynamics, identifying the dominant pathology and recommending debate-
structure interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

PATHOLOGIES: tuple[str, ...] = ("groupthink", "polarization", "contagion")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a multi-agent debate trace -----------------------------------


class DebateMessage(BaseModel):
    """One message in a multi-agent debate."""

    round: int = Field(ge=1, description="Debate round number, starting at 1.")
    from_agent: str
    position: str = Field(
        default="",
        description="Optional short summary of the agent's stance this round "
        "(e.g. 'pro-ship', 'opposed', 'neutral / abstain').",
    )
    emotional_tone: Literal[
        "calm", "neutral", "heated", "anxious", "enthusiastic", "dismissive", "unknown"
    ] = "unknown"
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentDebateTrace(BaseModel):
    """A multi-agent debate ready for the Groupthink/Polarization/Contagion diagnostic."""

    debate_id: str | None = None
    task: str
    agents: list[str]
    messages: list[DebateMessage]
    final_decision: str
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-pathology evidence + interventions ----------------------


class PathologyEvidence(BaseModel):
    """Evidence for one of the three debate pathologies."""

    pathology: Literal["groupthink", "polarization", "contagion"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class DebateIntervention(BaseModel):
    """A concrete intervention targeting one of the three pathologies."""

    target_pathology: Literal["groupthink", "polarization", "contagion"]
    intervention_type: Literal[
        "assign_devils_advocate",
        "require_silent_vote",
        "round_robin_dissent",
        "diverse_seed_positions",
        "anchor_to_base_rates",
        "tone_normalization",
        "cool_down_pause",
        "external_arbiter",
        "smaller_panel",
        "secret_ballot",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class DebatePathologyDetection(BaseModel):
    """The full Groupthink/Polarization/Contagion diagnostic output."""

    debate_id: str | None = None
    dominant_pathology: Literal["groupthink", "polarization", "contagion", "none-observed"]
    pathology_scores: dict[str, float]
    pathologies: list[PathologyEvidence]
    debate_quality: Literal["healthy", "at-risk", "pathological"]
    convergence_round: int | None = Field(
        default=None,
        description="Round number when positions converged (None if no convergence).",
    )
    interventions: list[DebateIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Debate-Pathology Detection (Groupthink / Polarization / Contagion)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.debate_id:
            out.append(f"_Debate: {self.debate_id}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Debate quality: **{self.debate_quality.upper()}**_\n")
        out.append(f"_Dominant pathology: **{self.dominant_pathology}**_\n")
        if self.convergence_round is not None:
            out.append(f"_Convergence round: {self.convergence_round}_\n")

        out.append("\n## Pathology Scores\n")
        out.append("Per-pathology score (0.0 = absent, 1.0 = severe).\n\n")
        for p in PATHOLOGIES:
            score = self.pathology_scores.get(p, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{p}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Pathology\n")
        for ev in self.pathologies:
            out.append(f"\n### {ev.pathology} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the debate:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_pathology}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
