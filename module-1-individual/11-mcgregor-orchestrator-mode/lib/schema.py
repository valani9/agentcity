"""Schema for the McGregor Theory X/Y Orchestrator Mode diagnostic.

Anchored in:
  - McGregor, D. (1960) *The Human Side of Enterprise* -- the
    canonical Theory X / Theory Y statement.
  - McGregor, D. (1966) *Leadership and Motivation* -- the mature
    development of the framework.
  - Schein, E. H. (1990) *Organizational Culture and Leadership* --
    cultural-layer Theory-X/Y framing.
  - Pfeffer, J., & Salancik, G. R. (1978) *The External Control of
    Organizations* -- task-property contingency framing.
  - Argyris, C. (1957) *Personality and Organization* -- the
    pathology of pure Theory-X organizations.
  - Eisenhardt, K. M. (1989) ``Agency Theory: An Assessment and
    Review.'' Academy of Management Review 14, 57-74 -- principal-
    agent contingency model.
  - Modern LLM analogues: Wang et al. (2023) ``Cooperative LLM
    Agents''; LangGraph + CrewAI orchestration patterns; Anthropic
    Computer Use 2024 (sub-agent authorization).

Two contrasting management styles:

  - THEORY X assumes workers need control; tight oversight; every
    action approved; trust low.
  - THEORY Y assumes workers want to do good work; loose oversight;
    broad goals; trust high.

For AI agent systems, an orchestrator running sub-agents has the same
choice. Misuse on either side is expensive:
  - Theory-X on simple/reversible tasks wastes cycles.
  - Theory-Y on risky/irreversible tasks invites incidents.

The optimal mode is a **function of task properties**: risk level,
complexity, reversibility, regulatory exposure, sub-agent capability.

Three pipeline modes (consistent with patterns #01-#10):

  - ``quick`` -- 1 LLM call: observed mode + optimal mode + top
    intervention.
  - ``standard`` -- 2 LLM calls: mode indicators + ranked
    interventions.
  - ``forensic`` -- 4 LLM calls: mode indicators + per-step audit +
    optimality justification + ranked interventions with composition
    targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

MODES: tuple[str, ...] = ("theory_x", "theory_y", "hybrid")

OrchestratorMode = Literal["theory_x", "theory_y", "hybrid"]

McGregorMode = Literal["quick", "standard", "forensic"]
MCGREGOR_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# 7-point severity scale.
Severity = Literal[
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_mismatch(mismatch: float, mode_quality: str = "well-matched") -> Severity:
    """Map [0,1] mode_mismatch + mode_quality to 7-point severity.

    Severe-mismatch caps severity at >= 'high' regardless of raw score.
    """
    m = max(0.0, min(1.0, float(mismatch)))
    if m < 0.10:
        base: Severity = "none"
    elif m < 0.25:
        base = "trace"
    elif m < 0.40:
        base = "low"
    elif m < 0.55:
        base = "moderate"
    elif m < 0.70:
        base = "medium"
    elif m < 0.85:
        base = "high"
    else:
        base = "critical"

    if mode_quality == "severe-mismatch" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index(
        "high"
    ):
        return "high"
    return base


# 12 profile patterns named by the deterministic classifier.
McGregorProfilePattern = Literal[
    "well_matched_theory_x",
    "well_matched_theory_y",
    "well_matched_hybrid",
    "theory_x_on_low_risk",  # over-supervision waste
    "theory_y_on_high_risk",  # under-supervision incident risk
    "theory_x_on_proven_agent",  # capable agent kept on leash
    "theory_y_on_unproven_agent",  # untrusted agent left alone
    "hybrid_misapplied",  # wrong axis triggers
    "regulated_workflow_under_supervision",
    "creative_task_over_supervised",
    "irreversible_action_under_supervision",
    "indeterminate",
]
MCGREGOR_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_matched_theory_x",
    "well_matched_theory_y",
    "well_matched_hybrid",
    "theory_x_on_low_risk",
    "theory_y_on_high_risk",
    "theory_x_on_proven_agent",
    "theory_y_on_unproven_agent",
    "hybrid_misapplied",
    "regulated_workflow_under_supervision",
    "creative_task_over_supervised",
    "irreversible_action_under_supervision",
    "indeterminate",
)


# Intervention typology -- original 10 + 8 new = 18.
InterventionType = Literal[
    # Original 10.
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
    # New v0.2.0.
    "tier_oversight_by_action_type",
    "add_authorization_scope",
    "rotate_to_hybrid",
    "add_step_classifier",
    "elevate_to_human_on_irreversible",
    "add_agent_capability_probe",
    "compose_pattern",
    "add_orchestrator_eval",
]
INTERVENTION_TYPES: tuple[str, ...] = (
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
    "tier_oversight_by_action_type",
    "add_authorization_scope",
    "rotate_to_hybrid",
    "add_step_classifier",
    "elevate_to_human_on_irreversible",
    "add_agent_capability_probe",
    "compose_pattern",
    "add_orchestrator_eval",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- orchestrator + agent trace
# ---------------------------------------------------------------------------


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
    success: bool = False

    # New in v0.2.0.
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- indicators + audits + intervention + handoff
# ---------------------------------------------------------------------------


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
        description="Rate at which the orchestrator intervened.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class StepAudit(BaseModel):
    """One audited step in the orchestrator trace. Forensic mode only."""

    step_index: int = Field(ge=0)
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
    mode_signal: OrchestratorMode = "hybrid"
    was_appropriate: bool = True
    suggested_alternative: str = ""
    explanation: str = ""


class OptimalityJustification(BaseModel):
    """Why the optimal mode is optimal given the task properties.

    Forensic mode only. Eisenhardt (1989) agency-theory contingency.
    """

    optimal_mode: OrchestratorMode
    task_risk: str = ""
    task_complexity: str = ""
    task_reversibility: str = ""
    agent_capability: str = ""
    regulatory: str = ""
    final_rationale: str = ""


class OrchestratorIntervention(BaseModel):
    """A concrete intervention to shift the orchestrator's mode."""

    target_mode: OrchestratorMode
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    # New in v0.2.0.
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    reversibility: Literal["one-way-door", "two-way-door"] = "two-way-door"
    composition_target_pattern: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    success_metric: str = ""


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the detection."""

    mode: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_observed_mode: str | None = None
    baseline_profile_pattern: str | None = None
    indicator_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of vstack."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class OrchestratorModeDetection(BaseModel):
    """The full Theory X/Y diagnostic output."""

    trace_id: str | None = None
    observed_mode: OrchestratorMode
    optimal_mode: OrchestratorMode
    mode_mismatch: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = matched, 1 = opposite.",
    )
    indicators: ModeIndicators
    mode_quality: Literal["well-matched", "mild-mismatch", "severe-mismatch"]
    rationale: str = Field(default="")
    interventions: list[OrchestratorIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: McGregorMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: McGregorProfilePattern = "indeterminate"
    step_audits: list[StepAudit] = Field(default_factory=list)
    optimality_justification: OptimalityJustification | None = None
    baseline: BaselineComparison | None = None
    composition_handoff: ComposedPatternHandoff | None = None
    attached_playbooks: list[AttachedPlaybook] = Field(default_factory=list)
    run_id: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    tokens_total: int = Field(default=0, ge=0)
    tokens_input: int = Field(default=0, ge=0)
    tokens_output: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    injection_detected: bool = False

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Orchestrator Mode Detection (McGregor Theory X/Y)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Mode quality: **{self.mode_quality.upper()}** (severity: {self.severity})_\n")
        out.append(f"_Observed mode: **{self.observed_mode}**_\n")
        out.append(f"_Optimal mode: **{self.optimal_mode}**_\n")
        out.append(f"_Mode mismatch: {self.mode_mismatch:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), "
                f"{self.tokens_total} tokens, ${self.cost_usd:.4f}, "
                f"{self.elapsed_ms:.0f}ms_\n"
            )
        if self.injection_detected:
            out.append(
                "_Prompt-injection patterns detected in inputs (sanitized for diagnosis)._\n"
            )

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

        if self.optimality_justification:
            oj = self.optimality_justification
            out.append("\n## Optimality Justification (Forensic)\n")
            out.append(f"- **Optimal mode:** {oj.optimal_mode}\n")
            if oj.task_risk:
                out.append(f"- **Risk:** {oj.task_risk}\n")
            if oj.task_complexity:
                out.append(f"- **Complexity:** {oj.task_complexity}\n")
            if oj.task_reversibility:
                out.append(f"- **Reversibility:** {oj.task_reversibility}\n")
            if oj.agent_capability:
                out.append(f"- **Agent capability:** {oj.agent_capability}\n")
            if oj.regulatory:
                out.append(f"- **Regulatory:** {oj.regulatory}\n")
            if oj.final_rationale:
                out.append(f"- **Final rationale:** {oj.final_rationale}\n")

        if self.step_audits:
            out.append("\n## Step-by-Step Audit (Forensic)\n")
            for sa in self.step_audits:
                ok = "OK" if sa.was_appropriate else "MISMATCH"
                out.append(
                    f"- step {sa.step_index} ({sa.step_type}, signals {sa.mode_signal}): {ok}\n"
                )
                if sa.suggested_alternative:
                    out.append(f"  - suggested: {sa.suggested_alternative}\n")

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
            out.append(f"- **Effort:** {iv.effort_estimate}\n")
            out.append(f"- **Risk:** {iv.risk}\n")
            out.append(f"- **Reversibility:** {iv.reversibility}\n")
            if iv.preconditions:
                out.append(f"- **Preconditions:** {'; '.join(iv.preconditions)}\n")
            if iv.success_metric:
                out.append(f"- **Success metric:** {iv.success_metric}\n")
            if iv.composition_target_pattern:
                out.append(f"- **Composes with:** `{iv.composition_target_pattern}`\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title}  _(mode={pb.mode}, failure_mode={pb.failure_mode})_\n"
                )
                for j, step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {step}\n")
                if pb.anchor_citation:
                    out.append(f"\n_Anchor: {pb.anchor_citation}_\n")

        if self.composition_handoff and (
            self.composition_handoff.downstream_patterns
            or self.composition_handoff.upstream_patterns
        ):
            out.append("\n## Composition Handoff\n")
            ch = self.composition_handoff
            if ch.upstream_patterns:
                out.append(f"- **Upstream:** {', '.join(f'`{p}`' for p in ch.upstream_patterns)}\n")
            if ch.downstream_patterns:
                out.append(
                    f"- **Recommended downstream:** "
                    f"{', '.join(f'`{p}`' for p in ch.downstream_patterns)}\n"
                )
            if ch.rationale:
                out.append(f"- **Rationale:** {ch.rationale}\n")

        if self.baseline:
            out.append("\n## Baseline Comparison\n")
            b = self.baseline
            out.append(f"- **Baseline id:** {b.historical_baseline_id or '(unset)'}\n")
            if b.historical_generated_at:
                out.append(
                    f"- **Baseline generated at:** {b.historical_generated_at.isoformat()}\n"
                )
            out.append(f"- **Baseline observed mode:** {b.baseline_observed_mode or '(unset)'}\n")
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.indicator_deltas:
                out.append("- **Indicator deltas:**\n")
                for k, v in b.indicator_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
