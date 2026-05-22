"""
Schema for the Johari Window Self-Audit applied to AI agents.

Luft & Ingham 1955 four-quadrant model of self-awareness:

                Known to others    Not known to others
              ┌──────────────────┬─────────────────────┐
  Known       │      OPEN        │       HIDDEN        │
  to self     │                  │                     │
              ├──────────────────┼─────────────────────┤
  Not known   │      BLIND       │       UNKNOWN       │
  to self     │                  │                     │
              └──────────────────┴─────────────────────┘

For an AI agent:
  - OPEN     - the agent's self-report matches observed behavior
  - BLIND    - observed behavior the agent did not acknowledge (confabulation,
                hallucinated tool calls, behavior diverging from self-report)
  - HIDDEN   - private reasoning / uncertainty / scratchpad content the agent
                computed but did not surface to the user
  - UNKNOWN  - latent capabilities or behaviors neither agent nor observer
                noticed; surfaced only in edge cases
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

QUADRANTS: tuple[str, ...] = ("open", "blind", "hidden", "unknown")


def _utcnow() -> datetime:
    """Timezone-aware UTC now; replaces the deprecated `datetime.utcnow`."""
    return datetime.now(timezone.utc)


# --- Input: a structured agent trace + self-report ----------------------


class InteractionTurn(BaseModel):
    """One turn in the agent's interaction trace.

    Covers user messages, agent messages, tool calls, tool results, and
    internal-reasoning ("thought") traces if the agent exposes them.
    """

    role: Literal[
        "user",
        "agent",
        "system",
        "tool",
        "tool_result",
        "thought",
        "observation",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSelfReportTrace(BaseModel):
    """An agent run plus its self-report.

    The audit compares the self-report against the actual trace to
    identify divergences (BLIND content) and assess the quality of the
    agent's self-knowledge.
    """

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[InteractionTurn]
    self_report: str = Field(
        description=(
            "The agent's own summary of what it did, in its own words. "
            "Compared against turns to identify confabulation."
        )
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: the Johari audit -------------------------------------------


class QuadrantContent(BaseModel):
    """Content observed in one Johari quadrant."""

    quadrant: Literal["open", "blind", "hidden", "unknown"]
    weight: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Relative weight of content in this quadrant in [0.0, 1.0]. "
            "Sum across all four quadrants should be close to 1.0."
        ),
    )
    explanation: str
    evidence_quotes: list[str] = Field(
        default_factory=list,
        description="Specific turn excerpts or self-report excerpts illustrating this quadrant.",
    )


class JohariIntervention(BaseModel):
    """A concrete intervention to grow the OPEN quadrant."""

    target_quadrant: Literal["blind", "hidden", "unknown"]
    intervention_type: Literal[
        "disclosure_prompt",
        "feedback_loop",
        "self_consistency_check",
        "uncertainty_surfacing",
        "capability_probe",
        "trace_self_review",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class JohariSelfAudit(BaseModel):
    """The full Johari Window Self-Audit output for one agent trace."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_quadrant: Literal["open", "blind", "hidden", "unknown"]
    quadrant_weights: dict[str, float] = Field(
        description="Weight per Johari quadrant. Sum across the four ≈ 1.0."
    )
    quadrants: list[QuadrantContent]
    self_awareness_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "0.0 = severely unaware (large BLIND); 1.0 = fully self-aware "
            "(content sits mostly in OPEN with deliberate HIDDEN)."
        ),
    )
    blind_spot_register: list[str] = Field(
        default_factory=list,
        description="Concrete blind-spot items: observed behaviors the agent did not acknowledge.",
    )
    hidden_content_register: list[str] = Field(
        default_factory=list,
        description="Content the agent reasoned about but did not surface.",
    )
    interventions: list[JohariIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        """Render the audit as a markdown report."""
        out: list[str] = []
        out.append("# Johari Window Self-Audit\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Audited by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Dominant quadrant: **{self.dominant_quadrant.upper()}**_\n")
        out.append(f"_Self-awareness score: **{self.self_awareness_score:.2f}**_\n")

        out.append("\n## Quadrant Weights\n")
        out.append("Relative weight of agent content per Johari quadrant.\n\n")
        for q in QUADRANTS:
            score = self.quadrant_weights.get(q, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{q}**: {score:.2f}  {bar}\n")

        out.append("\n## Per-Quadrant Findings\n")
        for qc in self.quadrants:
            out.append(f"\n### {qc.quadrant.upper()} (weight {qc.weight:.2f})\n")
            out.append(f"{qc.explanation}\n")
            if qc.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in qc.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.blind_spot_register:
            out.append("\n## Blind Spots (behaviors the agent did not acknowledge)\n")
            for item in self.blind_spot_register:
                out.append(f"- {item}\n")

        if self.hidden_content_register:
            out.append("\n## Hidden Content (reasoned about, not surfaced)\n")
            for item in self.hidden_content_register:
                out.append(f"- {item}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: shrinks `{iv.target_quadrant}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
