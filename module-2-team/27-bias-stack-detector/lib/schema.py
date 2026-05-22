"""Schema for the Bias-Stack Detector.

Four canonical Kahneman/Tversky biases applied to agent reasoning:
  - anchoring
  - overconfidence
  - confirmation
  - escalation-of-commitment

The four cluster — an anchored agent tends toward overconfidence, which
amplifies confirmation bias, which leads to escalation when the original
direction proves wrong. The detector measures all four together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

BIASES: tuple[str, ...] = (
    "anchoring",
    "overconfidence",
    "confirmation",
    "escalation-of-commitment",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a structured reasoning trace --------------------------------


class ReasoningStep(BaseModel):
    """One step in an agent's reasoning trace."""

    type: Literal[
        "hypothesis",
        "tool_call",
        "observation",
        "decision",
        "thought",
        "retry",
        "conclusion",
    ]
    content: str
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional self-reported confidence in [0.0, 1.0].",
    )
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentReasoningTrace(BaseModel):
    """A reasoning trace ready for the Bias-Stack diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[ReasoningStep]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-bias evidence + diagnostic -----------------------------


class BiasEvidence(BaseModel):
    """Evidence for one cognitive bias observed in the trace."""

    bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
    ]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class BiasIntervention(BaseModel):
    """A concrete intervention targeting one of the four biases."""

    target_bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
    ]
    intervention_type: Literal[
        "prompt_patch",
        "scaffold_change",
        "retry_cap",
        "uncertainty_calibration",
        "first_principles_reset",
        "devils_advocate_role",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class BiasStackDetection(BaseModel):
    """The full Bias-Stack diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
        "none-observed",
    ]
    bias_scores: dict[str, float]
    biases: list[BiasEvidence]
    interventions: list[BiasIntervention]
    overall_reasoning_quality: Literal["well-calibrated", "bias-prone", "severely-biased"]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Bias-Stack Detection\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Reasoning quality: **{self.overall_reasoning_quality.upper()}**_\n")
        out.append(f"_Dominant bias: **{self.dominant_bias}**_\n")

        out.append("\n## Bias Scores\n")
        out.append("Per-bias score (0.0 = absent, 1.0 = severe).\n\n")
        for bias in BIASES:
            score = self.bias_scores.get(bias, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{bias}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Bias\n")
        for ev in self.biases:
            out.append(f"\n### {ev.bias} ({ev.severity}, score {ev.score:.2f})\n")
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
                f"\n### Intervention {i}: targets `{iv.target_bias}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
