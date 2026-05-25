"""Schema for the GRPI Working Agreement Generator.

Anchored in:
  - Beckhard, R. (1972) ``Optimizing Team-Building Effort.'' Journal of
    Contemporary Business 1, 23-32 -- canonical four-dimensional GRPI.
  - Rubin, I. M., Plovnick, M. S., & Fry, R. E. (1977) *Task-Oriented
    Team Development* -- the formal GRPI operationalization.
  - Raue, S., et al. (2013) ``A Review of Team Effectiveness Models.''
  - Hackman, J. R. (2002) *Leading Teams: Setting the Stage for Great
    Performances* -- the team-effectiveness anchor.
  - Salas, E., et al. (2018) ``The Science of Team Performance.''
    Annual Review of Org Psych 5, 593-620 -- the modern review.
  - Lencioni, P. (2002) *Five Dysfunctions of a Team* -- inverse
    (which dysfunctions a strong GRPI prevents).
  - Modern LLM analogue: Wang et al. (2023) Cooperative LLM Agents;
    Anthropic Computer Use (2024) sub-agent authorization.

GRPI = Goals + Roles + Processes + Interactions.

Unlike most vstack patterns (DIAGNOSTIC, consume traces), GRPI is
GENERATIVE: it consumes a team-setup request and produces a structured
Working Agreement document.

Three pipeline modes:
  - ``quick`` -- 1 LLM call: skeleton GRPI agreement (fast/cheap).
  - ``standard`` -- 2 LLM calls: agreement + per-section refinement.
  - ``forensic`` -- 4 LLM calls: agreement + role-fit audit +
    dysfunction-prevention audit + composition recommendations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DIMENSIONS: tuple[str, ...] = ("goals", "roles", "processes", "interactions")

GRPIMode = Literal["quick", "standard", "forensic"]
GRPI_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

GRPIDimension = Literal["goals", "roles", "processes", "interactions"]

# 7-point severity scale.
Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = ("none", "trace", "low", "moderate", "medium", "high", "critical")


def severity_from_completeness(score: float) -> Severity:
    """Map [0,1] completeness score to severity (inverse polarity)."""
    s = max(0.0, min(1.0, float(score)))
    distance = 1.0 - s
    if distance < 0.10:
        return "none"
    if distance < 0.25:
        return "trace"
    if distance < 0.40:
        return "low"
    if distance < 0.55:
        return "moderate"
    if distance < 0.70:
        return "medium"
    if distance < 0.85:
        return "high"
    return "critical"


# Profile patterns for the deterministic classifier.
GRPIProfilePattern = Literal[
    "complete_balanced",
    "weak_goals",
    "weak_roles",
    "weak_processes",
    "weak_interactions",
    "missing_kill_criteria",
    "missing_escalation_path",
    "ambiguous_decision_rights",
    "single_agent_team",
    "framework_misfit",
    "indeterminate",
]
GRPI_PROFILE_PATTERNS: tuple[str, ...] = (
    "complete_balanced",
    "weak_goals",
    "weak_roles",
    "weak_processes",
    "weak_interactions",
    "missing_kill_criteria",
    "missing_escalation_path",
    "ambiguous_decision_rights",
    "single_agent_team",
    "framework_misfit",
    "indeterminate",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: team setup request ------------------------------------------


class AgentRole(BaseModel):
    """A named agent on the team with optional pre-filled detail."""

    name: str
    description: str = ""
    decision_rights: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)


class TeamSetupRequest(BaseModel):
    """A request to generate a GRPI Working Agreement for a new team."""

    team_id: str | None = None
    task: str
    agents: list[AgentRole]
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    framework: str | None = None
    # New in v0.2.0.
    baseline_path: str | None = None
    risk_level: Literal["low", "medium", "high"] = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be non-empty")
        return v


# --- Output: GRPI sections --------------------------------------------


class GoalsSection(BaseModel):
    primary_goal: str
    measurable_success_criteria: list[str]
    scope_boundaries: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)


class RoleAssignment(BaseModel):
    agent_name: str
    role_title: str
    responsibilities: list[str]
    decision_rights: list[str]
    accountability_owner_for: list[str] = Field(default_factory=list)


class RolesSection(BaseModel):
    role_assignments: list[RoleAssignment]
    raci_summary: str = ""


class ProcessesSection(BaseModel):
    decision_protocol: str
    escalation_path: list[str]
    abandonment_criteria: list[str]
    communication_cadence: str
    review_cadence: str = ""
    artifact_storage: str = ""


class InteractionsSection(BaseModel):
    disagreement_norms: list[str]
    feedback_format: str
    conflict_resolution: str
    voice_and_turn_taking: list[str] = Field(default_factory=list)
    psychological_safety_commitments: list[str] = Field(default_factory=list)


# --- Forensic-mode audits ---------------------------------------------


class RoleFitAudit(BaseModel):
    """Per-role fit audit. Forensic mode only."""

    agent_name: str
    fit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    ambiguous_decision_rights: list[str] = Field(default_factory=list)
    overlapping_responsibilities: list[str] = Field(default_factory=list)
    notes: str = ""


class DysfunctionPreventionAudit(BaseModel):
    """Lencioni dysfunction-prevention audit. Forensic mode only."""

    prevents_absence_of_trust: bool = False
    prevents_fear_of_conflict: bool = False
    prevents_lack_of_commitment: bool = False
    prevents_avoidance_of_accountability: bool = False
    prevents_inattention_to_results: bool = False
    notes: str = ""


class GRPIIntervention(BaseModel):
    """A concrete intervention to improve an existing working agreement."""

    target_dimension: GRPIDimension
    intervention_type: Literal[
        "tighten_goals",
        "clarify_roles",
        "tighten_processes",
        "strengthen_interactions",
        "add_kill_criteria",
        "add_escalation_path",
        "disambiguate_decision_rights",
        "scope_to_framework",
        "new_eval",
        "human_review",
        "compose_pattern",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    dimension: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    completeness_delta: float = 0.0
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class WorkingAgreement(BaseModel):
    """The full GRPI Working Agreement output."""

    team_id: str | None = None
    task: str
    goals: GoalsSection
    roles: RolesSection
    processes: ProcessesSection
    interactions: InteractionsSection

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    framework: str | None = None

    # New in v0.2.0.
    mode: GRPIMode = "standard"
    severity: Severity = "moderate"
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    profile_pattern: GRPIProfilePattern = "indeterminate"
    role_fit_audits: list[RoleFitAudit] = Field(default_factory=list)
    dysfunction_prevention: DysfunctionPreventionAudit | None = None
    interventions: list[GRPIIntervention] = Field(default_factory=list)
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
        out.append("# Working Agreement (GRPI)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.team_id:
            out.append(f"_Team: {self.team_id}_\n")
        if self.framework:
            out.append(f"_Framework: {self.framework}_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(
            f"_Completeness: {self.completeness_score:.2f} "
            f"(severity: {self.severity}, profile: {self.profile_pattern})_\n"
        )
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), "
                f"{self.tokens_total} tokens, ${self.cost_usd:.4f}, "
                f"{self.elapsed_ms:.0f}ms_\n"
            )
        if self.injection_detected:
            out.append(
                "_Prompt-injection patterns detected in inputs (sanitized for generation)._\n"
            )

        out.append(f"\n## Task\n\n{self.task}\n")

        out.append("\n## G — Goals\n\n")
        out.append(f"**Primary goal:** {self.goals.primary_goal}\n\n")
        out.append("**Measurable success criteria:**\n")
        for c in self.goals.measurable_success_criteria:
            out.append(f"- {c}\n")
        if self.goals.deliverables:
            out.append("\n**Deliverables:**\n")
            for d in self.goals.deliverables:
                out.append(f"- {d}\n")
        if self.goals.scope_boundaries:
            out.append("\n**Scope boundaries:**\n")
            for b in self.goals.scope_boundaries:
                out.append(f"- {b}\n")
        if self.goals.kill_criteria:
            out.append("\n**Kill criteria:**\n")
            for k in self.goals.kill_criteria:
                out.append(f"- {k}\n")

        out.append("\n## R — Roles\n")
        for ra in self.roles.role_assignments:
            out.append(f"\n### {ra.agent_name} — {ra.role_title}\n")
            out.append("**Responsibilities:**\n")
            for r in ra.responsibilities:
                out.append(f"- {r}\n")
            out.append("\n**Decision rights:**\n")
            for d in ra.decision_rights:
                out.append(f"- {d}\n")
            if ra.accountability_owner_for:
                out.append("\n**Owns end-to-end:**\n")
                for o in ra.accountability_owner_for:
                    out.append(f"- {o}\n")
        if self.roles.raci_summary:
            out.append(f"\n**RACI summary:** {self.roles.raci_summary}\n")

        out.append("\n## P — Processes\n\n")
        out.append(f"**Decision protocol:** {self.processes.decision_protocol}\n\n")
        out.append("**Escalation path:**\n")
        for step in self.processes.escalation_path:
            out.append(f"- {step}\n")
        out.append("\n**Abandonment criteria:**\n")
        for c in self.processes.abandonment_criteria:
            out.append(f"- {c}\n")
        out.append(f"\n**Communication cadence:** {self.processes.communication_cadence}\n")
        if self.processes.review_cadence:
            out.append(f"\n**Review cadence:** {self.processes.review_cadence}\n")
        if self.processes.artifact_storage:
            out.append(f"\n**Artifact storage:** {self.processes.artifact_storage}\n")

        out.append("\n## I — Interactions\n\n")
        out.append("**Disagreement norms:**\n")
        for n in self.interactions.disagreement_norms:
            out.append(f"- {n}\n")
        out.append(f"\n**Feedback format:** {self.interactions.feedback_format}\n")
        out.append(f"\n**Conflict resolution:** {self.interactions.conflict_resolution}\n")
        if self.interactions.voice_and_turn_taking:
            out.append("\n**Voice & turn-taking:**\n")
            for v in self.interactions.voice_and_turn_taking:
                out.append(f"- {v}\n")
        if self.interactions.psychological_safety_commitments:
            out.append("\n**Psychological-safety commitments:**\n")
            for ps in self.interactions.psychological_safety_commitments:
                out.append(f"- {ps}\n")

        if self.role_fit_audits:
            out.append("\n## Role-Fit Audits (Forensic)\n")
            for rfa in self.role_fit_audits:
                out.append(f"- **{rfa.agent_name}**: fit {rfa.fit_score:.2f}\n")
                if rfa.ambiguous_decision_rights:
                    out.append(f"  - ambiguous decision rights: {rfa.ambiguous_decision_rights}\n")
                if rfa.overlapping_responsibilities:
                    out.append(
                        f"  - overlapping responsibilities: {rfa.overlapping_responsibilities}\n"
                    )

        if self.dysfunction_prevention:
            dp = self.dysfunction_prevention
            out.append("\n## Dysfunction Prevention (Forensic; Lencioni)\n")
            out.append(
                f"- absence_of_trust: {dp.prevents_absence_of_trust}\n"
                f"- fear_of_conflict: {dp.prevents_fear_of_conflict}\n"
                f"- lack_of_commitment: {dp.prevents_lack_of_commitment}\n"
                f"- avoidance_of_accountability: {dp.prevents_avoidance_of_accountability}\n"
                f"- inattention_to_results: {dp.prevents_inattention_to_results}\n"
            )
            if dp.notes:
                out.append(f"- _notes:_ {dp.notes}\n")

        if self.interventions:
            out.append("\n## Recommended Interventions\n")
            for i, iv in enumerate(self.interventions, 1):
                out.append(
                    f"\n### Intervention {i}: {iv.target_dimension} via `{iv.intervention_type}`\n"
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
                    f"\n### {pb.title}  _(dimension={pb.dimension}, "
                    f"failure_mode={pb.failure_mode})_\n"
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

    def to_orchestrator_preamble(self) -> str:
        lines = [
            "TEAM WORKING AGREEMENT (GRPI):",
            f"Task: {self.task}",
            "",
            "Goals:",
            f"- Primary: {self.goals.primary_goal}",
            f"- Success criteria: {'; '.join(self.goals.measurable_success_criteria)}",
            "",
            "Roles:",
        ]
        for ra in self.roles.role_assignments:
            lines.append(f"- {ra.agent_name}: {ra.role_title}")
        lines.extend(
            [
                "",
                f"Decision protocol: {self.processes.decision_protocol}",
                f"Escalation path: {' -> '.join(self.processes.escalation_path)}",
                f"Communication: {self.processes.communication_cadence}",
                "",
                f"Disagreement norms: {'; '.join(self.interactions.disagreement_norms)}",
                f"Feedback format: {self.interactions.feedback_format}",
            ]
        )
        return "\n".join(lines)
