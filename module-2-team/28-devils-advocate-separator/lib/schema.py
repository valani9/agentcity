"""Schema for the Critical Evaluator / Devil's Advocate Role Separator.

Janis 1972 + Schwenk 1990 structured-dissent literature: the same
person/team should not both PROPOSE and JUDGE the same plan.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Approval Rate, Critic Voice),
calibration baselines, composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PHASES: tuple[str, ...] = ("plan", "execute", "self_evaluate", "external_critique")

DevilsAdvocateMode = Literal["quick", "standard", "forensic"]
DEVILS_ADVOCATE_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_separation(score: float) -> Severity:
    """Map separation score (0=fully conflated, 1=well separated) to inverse-severity."""
    s = max(0.0, min(1.0, float(score)))
    deficit = 1.0 - s
    if deficit < 0.10:
        return "none"
    if deficit < 0.25:
        return "trace"
    if deficit < 0.40:
        return "low"
    if deficit < 0.55:
        return "moderate"
    if deficit < 0.70:
        return "medium"
    if deficit < 0.85:
        return "high"
    return "critical"


DevilsAdvocateProfilePattern = Literal[
    "well_separated_critique",
    "self_review_only",
    "rubber_stamping",
    "missing_critic_phase",
    "fully_conflated_roles",
    "external_critic_present_weak",
    "no_pre_mortem",
    "no_alternative_hypothesis",
    "indeterminate",
]
DEVILS_ADVOCATE_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_separated_critique",
    "self_review_only",
    "rubber_stamping",
    "missing_critic_phase",
    "fully_conflated_roles",
    "external_critic_present_weak",
    "no_pre_mortem",
    "no_alternative_hypothesis",
    "indeterminate",
)


InterventionType = Literal[
    "add_critic_agent",
    "structured_self_critique",
    "red_team_loop",
    "devils_advocate_prompt",
    "external_review_gate",
    "pre_mortem_step",
    "alternative_hypothesis_step",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_critic_agent",
    "structured_self_critique",
    "red_team_loop",
    "devils_advocate_prompt",
    "external_review_gate",
    "pre_mortem_step",
    "alternative_hypothesis_step",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RoleStep(BaseModel):
    type: Literal[
        "plan",
        "execute",
        "self_evaluate",
        "external_critique",
        "decision",
        "observation",
        "tool_call",
        "thought",
    ]
    content: str
    actor: str = "primary"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SingleAgentTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    steps: list[RoleStep]
    outcome: str
    success: bool
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class PhaseEvidence(BaseModel):
    phase: Literal["plan", "execute", "self_evaluate", "external_critique"]
    present: bool
    actor: str = "primary"
    substantive_score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ApprovalRateAudit(BaseModel):
    """Forensic-mode: how often did the agent approve its own work?"""

    self_evaluations_observed: int = Field(default=0, ge=0)
    approvals: int = Field(default=0, ge=0)
    revisions: int = Field(default=0, ge=0)
    self_approval_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    rubber_stamping_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class CriticVoiceAudit(BaseModel):
    """Forensic-mode: how loud was the external critic voice?"""

    external_critique_turn_count: int = Field(default=0, ge=0)
    substantive_critic_objections: int = Field(default=0, ge=0)
    critic_actor_count: int = Field(default=0, ge=0)
    critic_voice_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class RoleSeparationIntervention(BaseModel):
    target_phase: Literal["plan", "execute", "self_evaluate", "external_critique"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    phase: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class RoleSeparationDetection(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    role_separation_quality: Literal["well-separated", "partially-conflated", "fully-conflated"]
    role_separation_score: float = Field(ge=0.0, le=1.0)
    locus_of_judgment: Literal["self-reviewed", "externally-reviewed", "mixed", "unreviewed"]
    phase_evidence: list[PhaseEvidence]
    self_approval_rate: float = Field(ge=0.0, le=1.0)
    interventions: list[RoleSeparationIntervention]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: DevilsAdvocateMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: DevilsAdvocateProfilePattern = "indeterminate"
    approval_rate_audit: ApprovalRateAudit | None = None
    critic_voice_audit: CriticVoiceAudit | None = None
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
        out.append("# Role-Separation Detection (Critical Evaluator / Devil's Advocate)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Role-separation quality: **{self.role_separation_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Locus of judgment: **{self.locus_of_judgment}**_\n")
        out.append(f"_Separation score: {self.role_separation_score:.2f}_\n")
        out.append(f"_Self-approval rate: {self.self_approval_rate:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Phase Evidence\n")
        out.append("Was each phase present, who performed it, and how substantive was it?\n\n")
        for ev in self.phase_evidence:
            mark = "+" if ev.present else "-"
            out.append(
                f"### {mark} {ev.phase} -- actor: `{ev.actor}`, "
                f"substantive {ev.substantive_score:.2f}\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")
            out.append("\n")

        if self.approval_rate_audit:
            ar = self.approval_rate_audit
            out.append("\n## Approval Rate Audit (Forensic)\n")
            out.append(
                f"- self_evaluations_observed: {ar.self_evaluations_observed}\n"
                f"- approvals: {ar.approvals}\n"
                f"- revisions: {ar.revisions}\n"
                f"- self_approval_rate: {ar.self_approval_rate:.2f}\n"
                f"- rubber_stamping_estimate: {ar.rubber_stamping_estimate:.2f}\n"
            )
            if ar.explanation:
                out.append(f"- {ar.explanation}\n")

        if self.critic_voice_audit:
            cv = self.critic_voice_audit
            out.append("\n## Critic Voice Audit (Forensic)\n")
            out.append(
                f"- external_critique_turn_count: {cv.external_critique_turn_count}\n"
                f"- substantive_critic_objections: {cv.substantive_critic_objections}\n"
                f"- critic_actor_count: {cv.critic_actor_count}\n"
                f"- critic_voice_estimate: {cv.critic_voice_estimate:.2f}\n"
            )
            if cv.explanation:
                out.append(f"- {cv.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_phase}` via "
                f"`{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(phase={pb.phase}, failure_mode={pb.failure_mode})_\n"
                )
                for j, step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {step}\n")

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
