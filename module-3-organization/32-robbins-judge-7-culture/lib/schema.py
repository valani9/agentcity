"""Schema for the Robbins & Judge 7-Characteristics Culture Diagnostic.

Stephen P. Robbins & Timothy A. Judge, "Organizational Behavior" (17th
ed., Pearson, 2017). The Robbins/Judge model proposes that culture can
be profiled along seven dimensions, each scored independently:

  - INNOVATION         - how much risk-taking and novel approaches are
                          encouraged
  - ATTENTION_TO_DETAIL - precision, analysis, attention to specifics
  - OUTCOME            - emphasis on results vs. process
  - PEOPLE             - consideration for effects on team members /
                          stakeholders
  - TEAM               - work organized around teams vs. individuals
  - AGGRESSIVENESS     - competitiveness vs. easy-going-ness
  - STABILITY          - emphasis on maintaining status quo vs. growth

Where Schein's Iceberg (#31) asks ARE THE THREE LAYERS ALIGNED, the
Robbins/Judge 7-Characteristics asks WHAT IS THIS CULTURE'S PROFILE? The
two compose: Schein measures coherence; Robbins/Judge measures the
specific shape.

Applied to AI agents: the seven dimensions are an explicit decomposition
of "agent personality / behavioral style." Some agents need to be high-
innovation low-stability (research/exploration); others need high-
attention-to-detail high-stability (regulated workflows, financial
operations). When the agent's culture profile doesn't match the task
class, you get culture-task misalignment failures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

CULTURE_CHARACTERISTICS: tuple[str, ...] = (
    "innovation",
    "attention_to_detail",
    "outcome",
    "people",
    "team",
    "aggressiveness",
    "stability",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent culture trace + task class ---------------------------


class AgentCultureTrace(BaseModel):
    """A trace + task class ready for the 7-Characteristics culture diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: Literal[
        "research_exploration",
        "creative_generation",
        "regulated_workflow",
        "financial_operation",
        "customer_support",
        "code_review",
        "incident_response",
        "general_purpose",
    ] = Field(
        default="general_purpose",
        description="The task class drives the target culture profile.",
    )
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-characteristic profile + recommendations --------------


class CharacteristicScore(BaseModel):
    """One culture characteristic, scored against the trace."""

    characteristic: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
    ]
    observed_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = absent in this agent's behavior; 1 = strongly present.",
    )
    target_score: float = Field(
        ge=0.0,
        le=1.0,
        description="What the score should be for the given task class.",
    )
    fit_score: float = Field(
        ge=0.0,
        le=1.0,
        description="1 - abs(observed - target). 1 = perfect fit; 0 = inverted.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class CultureIntervention(BaseModel):
    """A concrete intervention to shift one characteristic toward the target."""

    target_characteristic: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
    ]
    direction: Literal["increase", "decrease"]
    intervention_type: Literal[
        "rewrite_system_prompt",
        "adjust_temperature",
        "add_guardrail",
        "swap_model",
        "add_team_scaffold",
        "remove_solo_path",
        "add_kill_criterion",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class CultureProfileDetection(BaseModel):
    """The full 7-Characteristics diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: Literal[
        "research_exploration",
        "creative_generation",
        "regulated_workflow",
        "financial_operation",
        "customer_support",
        "code_review",
        "incident_response",
        "general_purpose",
    ]
    characteristics: list[CharacteristicScore]
    overall_fit: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean fit score across the seven characteristics.",
    )
    fit_quality: Literal["well-fit", "partial-fit", "misfit"]
    biggest_gap: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
        "none",
    ]
    interventions: list[CultureIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# 7-Characteristics Culture Profile (Robbins & Judge)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Fit quality: **{self.fit_quality.upper()}**_\n")
        out.append(f"_Overall fit: {self.overall_fit:.2f}_\n")
        out.append(f"_Biggest gap: **{self.biggest_gap}**_\n")

        out.append("\n## Per-Characteristic Profile\n")
        out.append("Each row shows observed score vs target for this task class.\n\n")
        for c in self.characteristics:
            obs_bar = "█" * int(round(c.observed_score * 10))
            target_bar = "·" * int(round(c.target_score * 10))
            out.append(
                f"- **{c.characteristic}**: obs {c.observed_score:.2f} `{obs_bar:<10}` "
                f"target {c.target_score:.2f} `{target_bar:<10}` fit {c.fit_score:.2f}\n"
            )

        out.append("\n## Evidence\n")
        for c in self.characteristics:
            out.append(f"\n### {c.characteristic} (fit {c.fit_score:.2f})\n")
            out.append(f"{c.explanation}\n")
            if c.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in c.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_characteristic}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
