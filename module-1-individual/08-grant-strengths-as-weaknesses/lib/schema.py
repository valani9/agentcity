"""Schema for the Adam Grant "Strengths as Weaknesses" diagnostic.

Adam Grant's contribution (drawn from his organizational-psychology work
at Wharton; popularized in WorkLife and TED talks): a person's strongest
trait, *overused*, becomes their primary failure mode. The conscientious
employee misses deadlines because they polish forever. The empathetic
manager avoids hard conversations. The decisive leader cuts off useful
debate.

Applied to AI agents, the canonical strength-overuse failures are:

  - HELPFULNESS overuse     - executes destructive requests because the user
                               asked nicely (DROP TABLE; rm -rf; transfer funds)
  - AGREEABLENESS overuse   - never pushes back on bad ideas; sycophancy
  - THOROUGHNESS overuse    - over-analyzes when speed matters; analysis paralysis
  - CAUTION overuse         - refuses safe requests; reflexive refusal
  - CONFIDENCE overuse      - asserts uncertain claims as facts; under-hedges
  - BREVITY overuse         - omits critical context; over-compresses
  - PRECISION overuse       - quibbles about definitions when the gist is the answer

The detector identifies WHICH strength was over-used in a given trace and
proposes interventions targeted at the specific overuse pattern (not at
the underlying strength, which is usually desirable in moderation).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

STRENGTHS: tuple[str, ...] = (
    "helpfulness",
    "agreeableness",
    "thoroughness",
    "caution",
    "confidence",
    "brevity",
    "precision",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: an agent behavior trace -------------------------------------


class AgentBehaviorStep(BaseModel):
    """One step in an agent's trace."""

    type: Literal[
        "input",
        "thought",
        "tool_call",
        "observation",
        "decision",
        "output",
        "refusal",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentBehaviorTrace(BaseModel):
    """An agent behavior trace ready for the Strengths-Overuse diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[AgentBehaviorStep]
    outcome: str
    success: bool
    harm_visible: bool = Field(
        default=False,
        description="Did the trace produce observable harm (broken state, lost data, "
        "wrong-information shipped, etc.)?",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-strength overuse evidence + interventions --------------


class StrengthOveruseEvidence(BaseModel):
    """Evidence for one strength being over-used in this trace."""

    strength: Literal[
        "helpfulness",
        "agreeableness",
        "thoroughness",
        "caution",
        "confidence",
        "brevity",
        "precision",
    ]
    overuse_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = strength operating in healthy range; 1 = severe overuse.",
    )
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class StrengthIntervention(BaseModel):
    """A concrete intervention to bound a strength's overuse without removing it."""

    target_strength: Literal[
        "helpfulness",
        "agreeableness",
        "thoroughness",
        "caution",
        "confidence",
        "brevity",
        "precision",
    ]
    intervention_type: Literal[
        "add_destructive_action_gate",
        "require_pushback_on_premise_check",
        "time_box_analysis",
        "require_hedged_confidence",
        "add_minimum_context_check",
        "explicit_anti_overuse_prompt",
        "human_review",
        "new_eval",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class StrengthOveruseDetection(BaseModel):
    """The full Strengths-Overuse diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_overuse: Literal[
        "helpfulness",
        "agreeableness",
        "thoroughness",
        "caution",
        "confidence",
        "brevity",
        "precision",
        "none-observed",
    ]
    strength_scores: dict[str, float]
    strengths: list[StrengthOveruseEvidence]
    harm_caused: Literal["none", "low", "medium", "high"]
    overuse_quality: Literal["healthy", "borderline", "overused"]
    interventions: list[StrengthIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Strengths-as-Weaknesses Detection (Adam Grant)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Overuse quality: **{self.overuse_quality.upper()}**_\n")
        out.append(f"_Dominant overuse: **{self.dominant_overuse}**_\n")
        out.append(f"_Harm caused: **{self.harm_caused}**_\n")

        out.append("\n## Strength Overuse Scores\n")
        out.append("Per-strength overuse score (0.0 = healthy range, 1.0 = severe overuse).\n\n")
        for strength in STRENGTHS:
            score = self.strength_scores.get(strength, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{strength}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Strength\n")
        for ev in self.strengths:
            out.append(f"\n### {ev.strength} ({ev.severity}, overuse {ev.overuse_score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_strength}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
