"""Schema for the SMART Goal Generator.

George T. Doran (1981) "There's a S.M.A.R.T. Way to Write Management's
Goals and Objectives." Goals should be Specific, Measurable, Achievable,
Relevant, Time-bound.

This is a GENERATIVE pattern (alongside #13 GRPI, #23 Plus/Delta).

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
deterministic profile patterns, forensic-mode audits (Criteria
Completeness, Measurement Rigor), calibration baselines, composition
handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SMART_CRITERIA: tuple[str, ...] = (
    "specific",
    "measurable",
    "achievable",
    "relevant",
    "time_bound",
)

SmartGoalMode = Literal["quick", "standard", "forensic"]
SMART_GOAL_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_smart_score(score: float) -> Severity:
    """Map SMART score (0=poor, 1=excellent) to inverse-severity."""
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


SmartGoalProfilePattern = Literal[
    "strong_smart_goal",
    "vague_unspecific",
    "unmeasurable",
    "unachievable_stretch",
    "irrelevant_to_context",
    "no_deadline",
    "missing_kill_criteria",
    "indeterminate",
]
SMART_GOAL_PROFILE_PATTERNS: tuple[str, ...] = (
    "strong_smart_goal",
    "vague_unspecific",
    "unmeasurable",
    "unachievable_stretch",
    "irrelevant_to_context",
    "no_deadline",
    "missing_kill_criteria",
    "indeterminate",
)


InterventionType = Literal[
    "tighten_specificity",
    "add_measurement",
    "calibrate_achievability",
    "ground_relevance",
    "add_deadline",
    "add_kill_criteria",
    "add_completion_criteria",
    "decompose_goal",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "tighten_specificity",
    "add_measurement",
    "calibrate_achievability",
    "ground_relevance",
    "add_deadline",
    "add_kill_criteria",
    "add_completion_criteria",
    "decompose_goal",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GoalRequest(BaseModel):
    goal_id: str | None = None
    vague_goal: str
    context: str = ""
    available_resources: list[str] = Field(default_factory=list)
    known_constraints: list[str] = Field(default_factory=list)
    deadline_hint: str | None = None
    framework: str | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("vague_goal")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class SMARTCriterion(BaseModel):
    criterion: Literal["specific", "measurable", "achievable", "relevant", "time_bound"]
    statement: str
    quality_score: float = Field(ge=0.0, le=1.0)


class SuccessMetric(BaseModel):
    name: str
    target: str
    measurement_method: str


class KillCriterion(BaseModel):
    name: str
    condition: str
    action_on_trigger: str = "escalate_to_human"


class CriteriaCompletenessAudit(BaseModel):
    """Forensic-mode: are all 5 SMART criteria addressed substantively?"""

    addressed_criteria_count: int = Field(default=0, ge=0, le=5)
    weak_criteria: list[str] = Field(default_factory=list)
    missing_criteria: list[str] = Field(default_factory=list)
    completeness_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class MeasurementRigorAudit(BaseModel):
    """Forensic-mode: are success metrics + kill criteria operationalizable?"""

    operationalizable_metric_count: int = Field(default=0, ge=0)
    qualitative_metric_count: int = Field(default=0, ge=0)
    operationalizable_kill_count: int = Field(default=0, ge=0)
    rigor_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class SmartGoalIntervention(BaseModel):
    target_criterion: Literal[
        "specific", "measurable", "achievable", "relevant", "time_bound", "overall"
    ]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    criterion: str
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


class SMARTGoal(BaseModel):
    goal_id: str | None = None
    original_goal: str
    smart_statement: str
    criteria: list[SMARTCriterion]
    completion_criteria: list[str]
    success_metrics: list[SuccessMetric]
    kill_criteria: list[KillCriterion]
    deadline: str
    open_questions: list[str] = Field(default_factory=list)

    overall_smart_score: float = Field(ge=0.0, le=1.0)
    smart_quality: Literal["strong", "acceptable", "weak"]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    framework: str | None = None

    # v0.2.0
    mode: SmartGoalMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: SmartGoalProfilePattern = "indeterminate"
    criteria_audit: CriteriaCompletenessAudit | None = None
    rigor_audit: MeasurementRigorAudit | None = None
    interventions: list[SmartGoalIntervention] = Field(default_factory=list)
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
        out.append("# SMART Goal (Doran 1981)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        if self.framework:
            out.append(f"_Framework: {self.framework}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(
            f"_SMART quality: **{self.smart_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Overall SMART score: {self.overall_smart_score:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append(f"\n## Original Goal\n\n{self.original_goal}\n")
        out.append(f"\n## SMART Restatement\n\n{self.smart_statement}\n")

        out.append("\n## SMART Criteria\n")
        for c in self.criteria:
            out.append(f"\n### {c.criterion} (quality {c.quality_score:.2f})\n")
            out.append(f"{c.statement}\n")

        out.append("\n## Completion Criteria\n")
        for cc in self.completion_criteria:
            out.append(f"- {cc}\n")

        out.append("\n## Success Metrics\n")
        for m in self.success_metrics:
            out.append(f"\n### {m.name}\n")
            out.append(f"- **Target:** {m.target}\n")
            out.append(f"- **Measurement:** {m.measurement_method}\n")

        out.append("\n## Kill Criteria\n")
        for k in self.kill_criteria:
            out.append(f"\n### {k.name}\n")
            out.append(f"- **Condition:** {k.condition}\n")
            out.append(f"- **Action on trigger:** {k.action_on_trigger}\n")

        out.append(f"\n## Deadline\n\n{self.deadline}\n")

        if self.open_questions:
            out.append("\n## Open Questions to Resolve Before Starting\n")
            for q in self.open_questions:
                out.append(f"- {q}\n")

        if self.criteria_audit:
            ca = self.criteria_audit
            out.append("\n## Criteria Completeness Audit (Forensic)\n")
            out.append(
                f"- addressed_criteria_count: {ca.addressed_criteria_count}/5\n"
                f"- weak_criteria: {', '.join(ca.weak_criteria) or '(none)'}\n"
                f"- missing_criteria: {', '.join(ca.missing_criteria) or '(none)'}\n"
                f"- completeness_estimate: {ca.completeness_estimate:.2f}\n"
            )
            if ca.explanation:
                out.append(f"- {ca.explanation}\n")

        if self.rigor_audit:
            ra = self.rigor_audit
            out.append("\n## Measurement Rigor Audit (Forensic)\n")
            out.append(
                f"- operationalizable_metric_count: {ra.operationalizable_metric_count}\n"
                f"- qualitative_metric_count: {ra.qualitative_metric_count}\n"
                f"- operationalizable_kill_count: {ra.operationalizable_kill_count}\n"
                f"- rigor_estimate: {ra.rigor_estimate:.2f}\n"
            )
            if ra.explanation:
                out.append(f"- {ra.explanation}\n")

        if self.interventions:
            out.append("\n## Quality Interventions\n")
            for i, iv in enumerate(self.interventions, 1):
                out.append(
                    f"\n### Intervention {i}: targets `{iv.target_criterion}` via "
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
                    f"\n### {pb.title} _(criterion={pb.criterion}, "
                    f"failure_mode={pb.failure_mode})_\n"
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

    def to_agent_preamble(self) -> str:
        lines = [
            "SMART GOAL:",
            self.smart_statement,
            "",
            f"Deadline: {self.deadline}",
            "",
            "Completion criteria:",
        ]
        for cc in self.completion_criteria:
            lines.append(f"- {cc}")
        lines.extend(["", "Success metrics:"])
        for m in self.success_metrics:
            lines.append(f"- {m.name}: {m.target} (measured: {m.measurement_method})")
        lines.extend(["", "Kill criteria (abandon goal if any fires):"])
        for k in self.kill_criteria:
            lines.append(f"- {k.condition} -> {k.action_on_trigger}")
        return "\n".join(lines)
