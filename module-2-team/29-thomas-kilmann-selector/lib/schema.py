"""Schema for the Thomas-Kilmann Conflict Style Selector.

Five styles plotted on assertiveness x cooperativeness axes (Thomas &
Kilmann 1974): competing, accommodating, avoiding, compromising,
collaborating.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Style Fit, Pattern Consistency),
calibration baselines, composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

STYLES: tuple[str, ...] = (
    "competing",
    "accommodating",
    "avoiding",
    "compromising",
    "collaborating",
)

ThomasKilmannMode = Literal["quick", "standard", "forensic"]
THOMAS_KILMANN_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_mismatch(mismatch: float) -> Severity:
    """Map style-mismatch score (0=match, 1=opposite) to severity."""
    s = max(0.0, min(1.0, float(mismatch)))
    if s < 0.10:
        return "none"
    if s < 0.25:
        return "trace"
    if s < 0.40:
        return "low"
    if s < 0.55:
        return "moderate"
    if s < 0.70:
        return "medium"
    if s < 0.85:
        return "high"
    return "critical"


ThomasKilmannProfilePattern = Literal[
    "well_matched",
    "competing_when_collaborating",
    "accommodating_when_competing",
    "avoiding_when_collaborating",
    "default_compromising",
    "rigid_single_style",
    "context_blind",
    "mixed_inconsistent",
    "indeterminate",
]
THOMAS_KILMANN_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_matched",
    "competing_when_collaborating",
    "accommodating_when_competing",
    "avoiding_when_collaborating",
    "default_compromising",
    "rigid_single_style",
    "context_blind",
    "mixed_inconsistent",
    "indeterminate",
)


InterventionType = Literal[
    "prompt_patch",
    "scaffold_change",
    "style_router",
    "context_classifier",
    "task_specific_persona",
    "calibrate_assertiveness",
    "calibrate_cooperativeness",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "prompt_patch",
    "scaffold_change",
    "style_router",
    "context_classifier",
    "task_specific_persona",
    "calibrate_assertiveness",
    "calibrate_cooperativeness",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InteractionTurn(BaseModel):
    role: Literal["user", "agent", "system", "tool", "observation"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInteractionTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    turns: list[InteractionTurn]
    outcome: str
    success: bool
    task_category: str | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class StyleScore(BaseModel):
    style: Literal["competing", "accommodating", "avoiding", "compromising", "collaborating"]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class StyleFitAudit(BaseModel):
    """Forensic-mode: does observed style fit the task category?"""

    task_category_inferred: str | None = None
    optimal_style_inferred: str | None = None
    fit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    cost_of_mismatch_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class PatternConsistencyAudit(BaseModel):
    """Forensic-mode: how consistent is the style across the trace?"""

    early_dominant_style: str | None = None
    late_dominant_style: str | None = None
    style_flips: int = Field(default=0, ge=0)
    consistency_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class StyleRecommendation(BaseModel):
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    style: str
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


class ConflictStyleSelection(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    observed_style: Literal[
        "competing",
        "accommodating",
        "avoiding",
        "compromising",
        "collaborating",
        "mixed",
    ]
    optimal_style: Literal[
        "competing", "accommodating", "avoiding", "compromising", "collaborating"
    ]
    style_mismatch: float = Field(ge=0.0, le=1.0)
    assertiveness_score: float = Field(ge=0.0, le=1.0)
    cooperativeness_score: float = Field(ge=0.0, le=1.0)
    observed_style_scores: dict[str, float]
    style_evidence: list[StyleScore]
    rationale: str
    recommendations: list[StyleRecommendation]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: ThomasKilmannMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: ThomasKilmannProfilePattern = "indeterminate"
    style_fit_audit: StyleFitAudit | None = None
    pattern_consistency_audit: PatternConsistencyAudit | None = None
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
        out.append("# Thomas-Kilmann Conflict Style Selection\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Selected by: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Observed style: **{self.observed_style.upper()}**_\n")
        out.append(f"_Optimal style: **{self.optimal_style.upper()}**_\n")
        out.append(f"_Style mismatch: **{self.style_mismatch:.2f}** (severity: {self.severity})_\n")
        out.append(
            f"_Assertiveness: {self.assertiveness_score:.2f}  |  "
            f"Cooperativeness: {self.cooperativeness_score:.2f}_\n"
        )
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Style Scores\n")
        out.append("Presence of each of the five canonical styles in the trace.\n\n")
        for s in STYLES:
            score = self.observed_style_scores.get(s, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{s}**: {score:.2f}  {bar}\n")

        out.append(f"\n## Rationale\n\n{self.rationale}\n")

        out.append("\n## Evidence by Style\n")
        for ev in self.style_evidence:
            if ev.score < 0.1:
                continue
            out.append(f"\n### {ev.style} (score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for q in ev.evidence_quotes:
                    out.append(f"> {q}\n")

        if self.style_fit_audit:
            sf = self.style_fit_audit
            out.append("\n## Style Fit Audit (Forensic)\n")
            out.append(
                f"- task_category_inferred: {sf.task_category_inferred}\n"
                f"- optimal_style_inferred: {sf.optimal_style_inferred}\n"
                f"- fit_score: {sf.fit_score:.2f}\n"
                f"- cost_of_mismatch_estimate: {sf.cost_of_mismatch_estimate:.2f}\n"
            )
            if sf.explanation:
                out.append(f"- {sf.explanation}\n")

        if self.pattern_consistency_audit:
            pc = self.pattern_consistency_audit
            out.append("\n## Pattern Consistency Audit (Forensic)\n")
            out.append(
                f"- early_dominant_style: {pc.early_dominant_style}\n"
                f"- late_dominant_style: {pc.late_dominant_style}\n"
                f"- style_flips: {pc.style_flips}\n"
                f"- consistency_estimate: {pc.consistency_estimate:.2f}\n"
            )
            if pc.explanation:
                out.append(f"- {pc.explanation}\n")

        out.append("\n## Recommendations\n")
        if not self.recommendations:
            out.append("(Observed style matched the optimal; no changes recommended.)\n")
        for i, rec in enumerate(self.recommendations, 1):
            out.append(f"\n### Recommendation {i}: `{rec.intervention_type}`\n")
            out.append(f"- **What:** {rec.description}\n")
            out.append(f"- **Implementation:** {rec.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {rec.estimated_impact}\n")
            if rec.rationale:
                out.append(f"- **Rationale:** {rec.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(style={pb.style}, failure_mode={pb.failure_mode})_\n"
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
