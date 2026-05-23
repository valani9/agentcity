"""Schema for the Yerkes-Dodson Optimal Workload Diagnostic.

Robert M. Yerkes & John D. Dodson (1908), "The Relation of Strength of
Stimulus to Rapidity of Habit Formation" (Journal of Comparative Neurology
and Psychology, 18). The original Yerkes-Dodson experiments established
that performance on a task has an INVERTED-U relationship with arousal /
pressure:

  - Under no pressure         → performance wanders, attention drifts
  - Under moderate pressure   → performance peaks
  - Under high pressure       → performance collapses (corner-cutting,
                                 freezing, panic)

The optimum is task-dependent: complex tasks peak at lower pressure;
simple tasks peak at higher pressure (Yerkes-Dodson Law).

Applied to AI agents, the same curve appears: an agent given infinite
budget and no deadline wanders; an agent given tight budget + deadline
produces clean focused output; an agent given absurdly-tight budget
hallucinates, corner-cuts, or refuses. The detector reads an agent
trace + the pressure inputs (deadline, token budget, retry cap, error
rate) and identifies whether the agent is operating in the optimal
range or has fallen off either side of the curve.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: pressure + trace --------------------------------------------


class PressureInputs(BaseModel):
    """The pressure inputs applied to the agent for this task."""

    deadline_pressure: Literal["none", "moderate", "tight", "absurd"] = "moderate"
    budget_pressure: Literal["none", "moderate", "tight", "absurd"] = "moderate"
    retry_cap: int | None = Field(
        default=None,
        ge=0,
        description="Max retries allowed. None = unbounded.",
    )
    error_visibility: Literal["low", "medium", "high"] = "medium"
    task_complexity: Literal["simple", "moderate", "complex"] = "moderate"


class AgentPerformanceTrace(BaseModel):
    """An agent performance trace ready for the Yerkes-Dodson diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    pressure: PressureInputs
    observed_behaviors: list[str] = Field(
        description="Concrete observed behaviors (wandering, focused, corner-cutting, etc.).",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: workload diagnostic + interventions ------------------------


class WorkloadZoneEvidence(BaseModel):
    """Evidence the agent is operating in a given zone."""

    zone: Literal["under_pressure", "optimal", "over_pressure"]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="How strongly the trace evidences this zone (0=absent, 1=clear).",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class WorkloadIntervention(BaseModel):
    """A concrete intervention to push the agent toward the optimal zone."""

    target_zone: Literal["optimal"]
    intervention_type: Literal[
        "tighten_deadline",
        "add_budget_cap",
        "loosen_deadline",
        "loosen_budget",
        "add_kill_criterion",
        "raise_retry_cap",
        "lower_retry_cap",
        "explicit_focus_prompt",
        "human_review",
        "new_eval",
    ]
    direction: Literal["increase_pressure", "decrease_pressure"]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class WorkloadDetection(BaseModel):
    """The full Yerkes-Dodson Optimal Workload diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    observed_zone: Literal["under_pressure", "optimal", "over_pressure"]
    zone_evidence: list[WorkloadZoneEvidence]
    distance_from_optimal: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = on the curve's optimum; 1 = at the worst end of one tail.",
    )
    failure_mode: Literal[
        "wandering",
        "focused",
        "corner_cutting",
        "freezing",
        "hallucinating",
        "refusing",
        "unknown",
    ]
    interventions: list[WorkloadIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Yerkes-Dodson Optimal Workload Detection\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Observed zone: **{self.observed_zone.upper()}**_\n")
        out.append(f"_Failure mode: **{self.failure_mode}**_\n")
        out.append(f"_Distance from optimal: {self.distance_from_optimal:.2f}_\n")

        out.append("\n## Zone Evidence\n")
        for ev in self.zone_evidence:
            bar = "█" * int(round(ev.score * 20))
            out.append(f"\n### {ev.zone} (score {ev.score:.2f})  {bar}\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(Already in optimal zone — no interventions needed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(f"\n### Intervention {i}: {iv.direction} via `{iv.intervention_type}`\n")
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
