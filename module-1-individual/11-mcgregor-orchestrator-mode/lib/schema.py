"""Schema for the McGregor Theory X/Y Orchestrator Mode diagnostic.

Douglas McGregor (1960), "The Human Side of Enterprise" (McGraw-Hill).
Two contrasting management styles:

  - THEORY X  - assumes workers need to be controlled and directed; tight
                oversight; every action approved; trust is low.
  - THEORY Y  - assumes workers want to do good work; loose oversight; broad
                goals; trust is high.

Neither is universally correct. The right mode depends on TASK PROPERTIES:
risk level, task complexity, agent capability, reversibility of mistakes,
regulatory exposure.

Applied to AI agent systems: an orchestrator running sub-agents has the
same choice. Theory-X orchestrator approves every step; Theory-Y
orchestrator gives goals + budget and lets agents work autonomously. A
hybrid orchestrator picks per-step based on risk. Misuse on either side
is expensive: Theory-X on simple tasks wastes cycles; Theory-Y on risky
tasks invites incidents.

The diagnostic reads the orchestrator-agent trace + the task properties
and reports the observed mode, the optimal mode, the mode-mismatch
score, and concrete interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

MODES: tuple[str, ...] = ("theory_x", "theory_y", "hybrid")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: orchestrator + agent trace -----------------------------------


class OrchestratorStep(BaseModel):
    """One step in an orchestrator-agent interaction."""

    step_type: Literal[
        "delegate",
        "check_in",
        "approve",
        "reject",
        "intervene",
        "broaden",
        "narrow",
        "abort",
        "observation",
    ]
    actor: Literal["orchestrator", "agent"]
    content: str
    sub_agent: str | None = Field(
        default=None,
        description="Which sub-agent the step targets (None for orchestrator-only steps).",
    )
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskProperties(BaseModel):
    """The properties of the task that determine the optimal orchestrator mode."""

    risk_level: Literal["low", "medium", "high"]
    complexity: Literal["routine", "moderate", "novel"]
    reversibility: Literal["reversible", "partial", "irreversible"] = "reversible"
    regulatory_exposure: bool = False
    agent_capability: Literal["unproven", "moderate", "proven"] = "moderate"


class OrchestratorTrace(BaseModel):
    """An orchestrator-agent trace ready for the Theory X/Y diagnostic."""

    trace_id: str | None = None
    task: str
    sub_agents: list[str]
    task_properties: TaskProperties
    steps: list[OrchestratorStep]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-dimension evidence + interventions ----------------------


class ModeIndicators(BaseModel):
    """Quantitative indicators of the observed orchestrator mode."""

    check_in_frequency: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of agent steps that triggered an orchestrator check-in.",
    )
    autonomy_granted: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of decisions made by sub-agents without orchestrator intervention.",
    )
    pre_approval_required: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of agent actions that required orchestrator pre-approval.",
    )
    intervention_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Rate at which the orchestrator intervened (corrected, redirected, aborted).",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class OrchestratorIntervention(BaseModel):
    """A concrete intervention to shift the orchestrator's mode toward the optimal."""

    target_mode: Literal["theory_x", "theory_y", "hybrid"]
    intervention_type: Literal[
        "tighten_oversight",
        "loosen_oversight",
        "add_pre_approval_gates",
        "remove_pre_approval_gates",
        "add_risk_classifier",
        "increase_check_in_cadence",
        "decrease_check_in_cadence",
        "redefine_agent_boundaries",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class OrchestratorModeDetection(BaseModel):
    """The full Theory X/Y diagnostic output."""

    trace_id: str | None = None
    observed_mode: Literal["theory_x", "theory_y", "hybrid"]
    optimal_mode: Literal["theory_x", "theory_y", "hybrid"]
    mode_mismatch: float = Field(
        ge=0.0,
        le=1.0,
        description="How far the observed mode is from the optimal mode (0 = matched, 1 = opposite).",
    )
    indicators: ModeIndicators
    mode_quality: Literal["well-matched", "mild-mismatch", "severe-mismatch"]
    rationale: str = Field(
        default="",
        description="Why this mode is/isn't right for the task properties.",
    )
    interventions: list[OrchestratorIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Orchestrator Mode Detection (McGregor Theory X/Y)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Mode quality: **{self.mode_quality.upper()}**_\n")
        out.append(f"_Observed mode: **{self.observed_mode}**_\n")
        out.append(f"_Optimal mode: **{self.optimal_mode}**_\n")
        out.append(f"_Mode mismatch: {self.mode_mismatch:.2f}_\n")

        out.append("\n## Mode Indicators\n")
        out.append(f"- **Check-in frequency:** {self.indicators.check_in_frequency:.2f}\n")
        out.append(f"- **Autonomy granted:** {self.indicators.autonomy_granted:.2f}\n")
        out.append(f"- **Pre-approval required:** {self.indicators.pre_approval_required:.2f}\n")
        out.append(f"- **Intervention rate:** {self.indicators.intervention_rate:.2f}\n")
        out.append(f"\n{self.indicators.explanation}\n")
        if self.indicators.evidence_quotes:
            out.append("\nEvidence:\n")
            for quote in self.indicators.evidence_quotes:
                out.append(f"> {quote}\n")

        if self.rationale:
            out.append("\n## Why This Mismatch Matters\n")
            out.append(f"{self.rationale}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_mode}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
