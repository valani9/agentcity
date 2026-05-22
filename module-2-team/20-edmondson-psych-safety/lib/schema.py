"""Schema for the Edmondson Psychological Safety Score for multi-agent systems."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

BEHAVIORS: tuple[str, ...] = (
    "voice",
    "help-seeking",
    "error-reporting",
    "boundary-spanning",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMessage(BaseModel):
    """A message in a multi-agent system trace."""

    timestamp: datetime | None = None
    from_agent: str
    to_agent: str | None = None
    content: str
    message_type: Literal[
        "task",
        "response",
        "challenge",
        "agreement",
        "question",
        "vote",
        "decision",
        "observation",
        "admission",
        "help_request",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentSafetyTrace(BaseModel):
    """Multi-agent trace ready for the psychological-safety diagnostic."""

    team_id: str | None = None
    framework: str | None = None
    goal: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class BehaviorEvidence(BaseModel):
    """Evidence for one Edmondson safety behavior."""

    behavior: Literal["voice", "help-seeking", "error-reporting", "boundary-spanning"]
    presence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = behavior absent, 1.0 = behavior strongly present.",
    )
    severity_of_absence: Literal["none", "low", "medium", "high"] = "none"
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class SafetyIntervention(BaseModel):
    target_behavior: Literal["voice", "help-seeking", "error-reporting", "boundary-spanning"]
    intervention_type: Literal[
        "prompt_patch",
        "scaffold_change",
        "role_assignment",
        "new_eval",
        "human_review",
        "norms_in_working_agreement",
        "dissent_round",
        "uncertainty_surfacing",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class PsychologicalSafetyDetection(BaseModel):
    team_id: str | None = None
    safety_score: float = Field(ge=0.0, le=1.0)
    team_climate: Literal["safe", "cautious", "silenced"]
    behavior_scores: dict[str, float]
    behaviors: list[BehaviorEvidence]
    blocking_behaviors: list[str] = Field(
        default_factory=list,
        description="Concrete behaviors observed in the trace that suppress psychological safety.",
    )
    interventions: list[SafetyIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Psychological Safety Score (Edmondson)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Safety score: **{self.safety_score:.2f}**_\n")
        out.append(f"_Team climate: **{self.team_climate.upper()}**_\n")

        out.append("\n## Behavior Presence Scores\n")
        out.append("Per-behavior presence (0.0 = absent, 1.0 = strongly present).\n\n")
        for b in BEHAVIORS:
            score = self.behavior_scores.get(b, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{b}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Behavior\n")
        for ev in self.behaviors:
            out.append(
                f"\n### {ev.behavior} ({ev.severity_of_absence} absence, presence {ev.presence_score:.2f})\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for q in ev.evidence_quotes:
                    out.append(f"> {q}\n")

        if self.blocking_behaviors:
            out.append("\n## Blocking Behaviors (suppressing safety)\n")
            for b in self.blocking_behaviors:
                out.append(f"- {b}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: grows `{iv.target_behavior}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")
        return "".join(out)
