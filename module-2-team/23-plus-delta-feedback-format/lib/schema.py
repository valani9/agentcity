"""Schema for the Plus/Delta Inter-Agent Feedback Format generator.

From the facilitator canon (Joiner Associates 1990s; Brown "Dare to Lead"
2018; retrospective-meeting literature). Plus/delta is forward-looking,
behavioral, specific.

This is a GENERATIVE pattern (alongside #13 GRPI, #24 SMART, #25 Group
Decision Models): it produces a Plus/Delta Feedback artifact rather
than scoring an existing artifact.

v0.2.0 adds three pipeline modes, a 7-point severity scale (mapped to
feedback_quality), eight deterministic profile patterns, forensic-mode
audits (Specificity, Behavioral-vs-Generic), calibration baselines,
composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PlusDeltaMode = Literal["quick", "standard", "forensic"]
PLUS_DELTA_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_quality(quality_score: float) -> Severity:
    """Map quality score (0=poor, 1=excellent) to inverse-severity bucket.

    Higher quality score => lower severity (quality is good).
    """
    s = max(0.0, min(1.0, float(quality_score)))
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


PlusDeltaProfilePattern = Literal[
    "balanced_specific",
    "plus_heavy_morale",
    "delta_heavy_rework",
    "generic_noise",
    "no_evidence_cited",
    "no_alternatives_named",
    "critical_findings",
    "indeterminate",
]
PLUS_DELTA_PROFILE_PATTERNS: tuple[str, ...] = (
    "balanced_specific",
    "plus_heavy_morale",
    "delta_heavy_rework",
    "generic_noise",
    "no_evidence_cited",
    "no_alternatives_named",
    "critical_findings",
    "indeterminate",
)


InterventionType = Literal[
    "tighten_specificity",
    "require_evidence",
    "require_alternative",
    "balance_style",
    "escalate_severity",
    "deescalate_severity",
    "add_commitment",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "tighten_specificity",
    "require_evidence",
    "require_alternative",
    "balance_style",
    "escalate_severity",
    "deescalate_severity",
    "add_commitment",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackRequest(BaseModel):
    feedback_id: str | None = None
    reviewer_agent: str
    subject_agent: str
    framework: str | None = None
    task_context: str
    contribution_summary: str
    contribution_artifact: str
    success_criteria: list[str] = Field(default_factory=list)
    style: Literal["balanced", "delta-leaning", "plus-leaning"] = "balanced"
    max_items_per_category: int = Field(default=4, ge=1, le=10)
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reviewer_agent", "subject_agent", "task_context", "contribution_artifact")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class PlusItem(BaseModel):
    statement: str
    evidence: str
    impact: str
    keep_doing: str = ""


class DeltaItem(BaseModel):
    statement: str
    evidence: str
    impact: str
    alternative: str
    severity: Literal["nit", "moderate", "critical"] = "moderate"


class Commitment(BaseModel):
    by_agent: str
    commitment: str


class SpecificityAudit(BaseModel):
    """Forensic-mode: do items meet behavioral-specificity bar?"""

    specific_plus_count: int = Field(default=0, ge=0)
    generic_plus_count: int = Field(default=0, ge=0)
    specific_delta_count: int = Field(default=0, ge=0)
    generic_delta_count: int = Field(default=0, ge=0)
    specificity_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class BehavioralVsGenericAudit(BaseModel):
    """Forensic-mode: per-item behavioral classification."""

    behavioral_count: int = Field(default=0, ge=0)
    generic_count: int = Field(default=0, ge=0)
    behavioral_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    generic_phrases_detected: list[str] = Field(default_factory=list)
    explanation: str = ""


class PlusDeltaIntervention(BaseModel):
    target_dimension: Literal["plus", "delta", "overall", "specificity"]
    intervention_type: InterventionType
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
    score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class PlusDeltaFeedback(BaseModel):
    feedback_id: str | None = None
    reviewer_agent: str
    subject_agent: str
    task_context: str
    contribution_summary: str

    plus_items: list[PlusItem] = Field(default_factory=list)
    delta_items: list[DeltaItem] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)

    overall_assessment: Literal["keep-going", "iterate", "rework"]
    feedback_quality_score: float = Field(ge=0.0, le=1.0)

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None

    # v0.2.0
    mode: PlusDeltaMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: PlusDeltaProfilePattern = "indeterminate"
    specificity_audit: SpecificityAudit | None = None
    behavioral_audit: BehavioralVsGenericAudit | None = None
    interventions: list[PlusDeltaIntervention] = Field(default_factory=list)
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
        out.append("# Plus/Delta Feedback\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        out.append(f"_Reviewer: **{self.reviewer_agent}** -> Subject: **{self.subject_agent}**_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Overall: **{self.overall_assessment.upper()}**_\n")
        out.append(
            f"_Feedback quality: {self.feedback_quality_score:.2f} (severity: {self.severity})_\n"
        )
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append(f"\n## Task context\n\n{self.task_context}\n")
        out.append(f"\n## Contribution under review\n\n{self.contribution_summary}\n")

        out.append("\n## Plus (keep doing)\n")
        if not self.plus_items:
            out.append("(No plus items.)\n")
        for i, plus in enumerate(self.plus_items, 1):
            out.append(f"\n### + {i}: {plus.statement}\n")
            out.append(f"- **Evidence:** {plus.evidence}\n")
            out.append(f"- **Impact:** {plus.impact}\n")
            if plus.keep_doing:
                out.append(f"- **Keep doing:** {plus.keep_doing}\n")

        out.append("\n## Delta (change for next time)\n")
        if not self.delta_items:
            out.append("(No delta items.)\n")
        for i, delta in enumerate(self.delta_items, 1):
            out.append(f"\n### D {i}: {delta.statement} ({delta.severity})\n")
            out.append(f"- **Evidence:** {delta.evidence}\n")
            out.append(f"- **Impact:** {delta.impact}\n")
            out.append(f"- **Alternative:** {delta.alternative}\n")

        if self.commitments:
            out.append("\n## Commitments\n")
            for c in self.commitments:
                out.append(f"- **{c.by_agent}:** {c.commitment}\n")

        if self.specificity_audit:
            sa = self.specificity_audit
            out.append("\n## Specificity Audit (Forensic)\n")
            out.append(
                f"- specific_plus_count: {sa.specific_plus_count}\n"
                f"- generic_plus_count: {sa.generic_plus_count}\n"
                f"- specific_delta_count: {sa.specific_delta_count}\n"
                f"- generic_delta_count: {sa.generic_delta_count}\n"
                f"- specificity_estimate: {sa.specificity_estimate:.2f}\n"
            )
            if sa.explanation:
                out.append(f"- {sa.explanation}\n")

        if self.behavioral_audit:
            ba = self.behavioral_audit
            out.append("\n## Behavioral-vs-Generic Audit (Forensic)\n")
            out.append(
                f"- behavioral_count: {ba.behavioral_count}\n"
                f"- generic_count: {ba.generic_count}\n"
                f"- behavioral_estimate: {ba.behavioral_estimate:.2f}\n"
            )
            if ba.generic_phrases_detected:
                out.append(
                    f"- generic_phrases_detected: {', '.join(ba.generic_phrases_detected)}\n"
                )
            if ba.explanation:
                out.append(f"- {ba.explanation}\n")

        if self.interventions:
            out.append("\n## Quality Interventions\n")
            for i, iv in enumerate(self.interventions, 1):
                out.append(
                    f"\n### Intervention {i}: targets `{iv.target_dimension}` via "
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
                    f"\n### {pb.title} _(dimension={pb.dimension}, "
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

    def to_inline_feedback(self) -> str:
        """Render a one-shot inline feedback block (for chat-style returns)."""
        lines = [f"FEEDBACK from {self.reviewer_agent} -> {self.subject_agent}:"]
        lines.append(f"Overall: {self.overall_assessment}")
        if self.plus_items:
            lines.append("\nPlus:")
            for plus in self.plus_items:
                lines.append(f"  + {plus.statement}")
        if self.delta_items:
            lines.append("\nDelta:")
            for delta in self.delta_items:
                lines.append(f"  D ({delta.severity}) {delta.statement} -> {delta.alternative}")
        return "\n".join(lines)
