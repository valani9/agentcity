"""Schema for the Process Gain/Loss Detector.

Anchored in:
  - Steiner, I. D. (1972) *Group Process and Productivity.* Academic Press.
  - Hill, G. W. (1982) ``Group versus Individual Performance: Are N + 1
    Heads Better than One?'' Psychological Bulletin 91, 517-539.
  - Hackman, J. R., & Vidmar, N. (1970) ``Effects of Size and Task Type
    on Group Performance and Member Reactions.'' Sociometry 33, 37-54.
  - Diehl, M., & Stroebe, W. (1987) ``Productivity Loss in Brainstorming
    Groups.'' JPSP 53, 497-509.
  - Salas, E., et al. (2018) Team performance review.
  - Robbins, S. P., & Judge, T. A. *Organizational Behavior* (textbook).
  - Modern LLM analogue: Wang et al. (2023) Cooperative LLM Agents.

Compares team output vs the best individual baseline (Steiner 1972
process-gain/loss). Identifies which factor(s) caused process loss.

Three pipeline modes:
  - ``quick`` -- 1 LLM call: factor scoring + top intervention.
  - ``standard`` -- 2 LLM calls: factor scoring + ranked interventions.
  - ``forensic`` -- 4 LLM calls: factor scoring + interaction-log audit
    + counterfactual reasoning + ranked interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PROCESS_FACTORS: tuple[str, ...] = (
    "coordination_cost",
    "social_loafing",
    "groupthink",
    "handoff_loss",
    "context_dilution",
    "consensus_dilution",
)

ProcessFactor = Literal[
    "coordination_cost",
    "social_loafing",
    "groupthink",
    "handoff_loss",
    "context_dilution",
    "consensus_dilution",
]

ProcessFactorOrTeamDesign = Literal[
    "coordination_cost",
    "social_loafing",
    "groupthink",
    "handoff_loss",
    "context_dilution",
    "consensus_dilution",
    "team_design",
]

ProcessGainLossMode = Literal["quick", "standard", "forensic"]
PROCESS_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = ("none", "trace", "low", "moderate", "medium", "high", "critical")


def severity_from_loss(gain_loss_score: float) -> Severity:
    """Map gain/loss score [-1, 1] to severity. Negative = loss."""
    s = max(-1.0, min(1.0, float(gain_loss_score)))
    # Distance below zero, scaled.
    if s >= 0.10:
        return "none"
    if s >= 0.0:
        return "trace"
    distance = abs(s)
    if distance < 0.10:
        return "low"
    if distance < 0.25:
        return "moderate"
    if distance < 0.40:
        return "medium"
    if distance < 0.60:
        return "high"
    return "critical"


ProcessProfilePattern = Literal[
    "process_gain_balanced",
    "neutral_team",
    "coordination_dominant_loss",
    "social_loafing_dominant_loss",
    "groupthink_dominant_loss",
    "handoff_dominant_loss",
    "context_dilution_dominant_loss",
    "consensus_dilution_dominant_loss",
    "multi_factor_loss",
    "cost_overhead_with_loss",  # worst case
    "team_too_large",
    "indeterminate",
]
PROCESS_PROFILE_PATTERNS: tuple[str, ...] = (
    "process_gain_balanced",
    "neutral_team",
    "coordination_dominant_loss",
    "social_loafing_dominant_loss",
    "groupthink_dominant_loss",
    "handoff_dominant_loss",
    "context_dilution_dominant_loss",
    "consensus_dilution_dominant_loss",
    "multi_factor_loss",
    "cost_overhead_with_loss",
    "team_too_large",
    "indeterminate",
)


InterventionType = Literal[
    # Original 10.
    "smaller_team",
    "use_single_best_agent",
    "decompose_task",
    "nominal_group_aggregation",
    "explicit_critic",
    "structured_handoff",
    "context_summarization",
    "fixed_vote_aggregation",
    "new_eval",
    "human_review",
    # New v0.2.0.
    "add_individual_accountability",
    "add_dissent_round",
    "increase_role_specialization",
    "compose_pattern",
    "add_process_eval",
    "reduce_team_size",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "smaller_team",
    "use_single_best_agent",
    "decompose_task",
    "nominal_group_aggregation",
    "explicit_critic",
    "structured_handoff",
    "context_summarization",
    "fixed_vote_aggregation",
    "new_eval",
    "human_review",
    "add_individual_accountability",
    "add_dissent_round",
    "increase_role_specialization",
    "compose_pattern",
    "add_process_eval",
    "reduce_team_size",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input ----------------------------------------------------------------


class IndividualBaseline(BaseModel):
    agent_name: str
    output_summary: str
    quality_score: float = Field(ge=0.0, le=1.0)
    cost_units: float | None = Field(default=None, ge=0.0)
    notes: str = ""


class TeamResult(BaseModel):
    agents: list[str]
    output_summary: str
    quality_score: float = Field(ge=0.0, le=1.0)
    cost_units: float | None = Field(default=None, ge=0.0)
    notes: str = ""


class ProcessTrace(BaseModel):
    trace_id: str | None = None
    task: str
    individual_baselines: list[IndividualBaseline]
    team_result: TeamResult
    interaction_log: str = ""
    outcome: str
    success: bool = False
    # New in v0.2.0.
    framework: str | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# --- Output --------------------------------------------------------------


class ProcessFactorEvidence(BaseModel):
    factor: ProcessFactor
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class InteractionLogAudit(BaseModel):
    """Forensic-mode: audit the interaction log for specific loss signatures."""

    n_handoffs: int = Field(default=0, ge=0)
    n_silent_agents: int = Field(default=0, ge=0)
    n_premature_consensus: int = Field(default=0, ge=0)
    n_context_loss_events: int = Field(default=0, ge=0)
    dominant_factor: ProcessFactor = "coordination_cost"
    notes: str = ""


class CounterfactualAudit(BaseModel):
    """Forensic-mode: what would a NOMINAL group have produced?"""

    nominal_group_quality_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    nominal_minus_team: float = Field(default=0.0)
    would_recommend_individual: bool = False
    explanation: str = ""


class ProcessIntervention(BaseModel):
    target_factor: ProcessFactorOrTeamDesign
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
    factor: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    gain_loss_delta: float = 0.0
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class ProcessGainLossDetection(BaseModel):
    trace_id: str | None = None
    process_quality: Literal["process-gain", "neutral", "process-loss"]
    gain_loss_score: float
    individual_best_quality: float = Field(ge=0.0, le=1.0)
    individual_best_agent: str
    individual_mean_quality: float = Field(ge=0.0, le=1.0)
    team_quality: float = Field(ge=0.0, le=1.0)
    contributing_factors: list[ProcessFactorEvidence]
    interventions: list[ProcessIntervention]
    cost_overhead_ratio: float | None = None

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: ProcessGainLossMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: ProcessProfilePattern = "indeterminate"
    interaction_log_audit: InteractionLogAudit | None = None
    counterfactual_audit: CounterfactualAudit | None = None
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
        out.append("# Process Gain/Loss Detection (Steiner / Robbins & Judge)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Process quality: **{self.process_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Gain/loss score: {self.gain_loss_score:+.2f}_\n")
        out.append(
            f"_Individual best: {self.individual_best_agent} "
            f"(quality {self.individual_best_quality:.2f})_\n"
        )
        out.append(f"_Individual mean quality: {self.individual_mean_quality:.2f}_\n")
        out.append(f"_Team quality: {self.team_quality:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.cost_overhead_ratio is not None:
            out.append(f"_Cost overhead vs best single: {self.cost_overhead_ratio:.2f}x_\n")
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

        out.append("\n## Contributing Factors\n")
        if not self.contributing_factors:
            out.append("(No contributing factors identified.)\n")
        for ev in self.contributing_factors:
            out.append(f"\n### {ev.factor} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.interaction_log_audit:
            ila = self.interaction_log_audit
            out.append("\n## Interaction Log Audit (Forensic)\n")
            out.append(
                f"- handoffs: {ila.n_handoffs} | silent agents: {ila.n_silent_agents} "
                f"| premature consensus: {ila.n_premature_consensus} "
                f"| context loss events: {ila.n_context_loss_events}\n"
            )
            out.append(f"- dominant factor: `{ila.dominant_factor}`\n")
            if ila.notes:
                out.append(f"- _notes:_ {ila.notes}\n")

        if self.counterfactual_audit:
            cf = self.counterfactual_audit
            out.append("\n## Counterfactual Audit (Forensic)\n")
            out.append(
                f"- Nominal group quality estimate: {cf.nominal_group_quality_estimate:.2f}\n"
            )
            out.append(f"- Nominal - team: {cf.nominal_minus_team:+.2f}\n")
            out.append(f"- Recommend individual baseline? {cf.would_recommend_individual}\n")
            if cf.explanation:
                out.append(f"- {cf.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_factor}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            out.append(f"- **Effort:** {iv.effort_estimate}\n")
            out.append(f"- **Risk:** {iv.risk}\n")
            if iv.composition_target_pattern:
                out.append(f"- **Composes with:** `{iv.composition_target_pattern}`\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title}  _(factor={pb.factor}, failure_mode={pb.failure_mode})_\n"
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

        return "".join(out)
