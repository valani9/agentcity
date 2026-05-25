"""Schema for the Yerkes-Dodson Optimal Workload Diagnostic.

Anchored in:
  - Yerkes & Dodson (1908) -- original inverted-U arousal-performance.
  - Sweller (1988, 1994, 2011) Cognitive Load Theory: intrinsic +
    extraneous + germane load components.
  - Kahneman (1973) *Attention and Effort* -- capacity model.
  - Hancock & Warm (1989) -- dynamic adaptability framework.
  - Eysenck-Calvo (1992) Attentional Control Theory -- anxiety effects
    on processing efficiency vs effectiveness.
  - Hebb (1955) -- arousal-as-physiological precursor.
  - Modern LLM-specific: context-window saturation as load analog;
    instruction-following degradation under stuffing
    (Liu et al. 2024 lost-in-the-middle); Anthropic prompt-token
    sensitivity research.

Three zones (the inverted-U):

  - **under_pressure** (low arousal): wandering, attention drifts,
    half-finished output.
  - **optimal**: focused, well-paced, error-corrected.
  - **over_pressure** (high arousal): corner-cutting, freezing,
    hallucination, refusal.

For AI agents: pressure inputs include deadline, token budget, retry
cap, error visibility, task complexity, AND (v0.2.0) cognitive load
components (intrinsic / extraneous / germane), context saturation,
and external interrupt frequency.

Three pipeline modes (consistent with patterns #01-#05):

  - ``quick`` -- 1 LLM call: zone detection + top intervention.
  - ``standard`` -- 2 LLM calls (v0.0.x refined).
  - ``forensic`` -- 4 LLM calls: zone + cognitive load decomposition
    (Sweller CLT) + context-saturation analysis + ranked interventions
    with composition targets.

Full literature thread in :mod:`vstack.yerkes_dodson.CITATIONS`
(``lib/CITATIONS.md``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

WORKLOAD_ZONES: tuple[str, ...] = ("under_pressure", "optimal", "over_pressure")

WorkloadZone = Literal["under_pressure", "optimal", "over_pressure"]

YerkesDodsonMode = Literal["quick", "standard", "forensic"]
YERKES_DODSON_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# 7-point severity (inverse polarity: distance from optimum -> severity).
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


def severity_from_distance(distance: float) -> Severity:
    """Map [0,1] distance-from-optimal to a 7-point severity bucket."""
    s = max(0.0, min(1.0, float(distance)))
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


# 10 workload profile patterns named by the deterministic classifier.
WorkloadProfilePattern = Literal[
    "optimal_zone",
    "under_pressure_wandering",
    "under_pressure_drift",
    "over_pressure_corner_cutting",
    "over_pressure_hallucinating",
    "over_pressure_freezing",
    "over_pressure_refusing",
    "context_saturation",
    "extraneous_load_overload",
    "intrinsic_load_overload",
    "indeterminate",
]
WORKLOAD_PROFILE_PATTERNS: tuple[str, ...] = (
    "optimal_zone",
    "under_pressure_wandering",
    "under_pressure_drift",
    "over_pressure_corner_cutting",
    "over_pressure_hallucinating",
    "over_pressure_freezing",
    "over_pressure_refusing",
    "context_saturation",
    "extraneous_load_overload",
    "intrinsic_load_overload",
    "indeterminate",
)


# Sweller CLT three load components.
CognitiveLoadComponent = Literal["intrinsic", "extraneous", "germane"]
COGNITIVE_LOAD_COMPONENTS: tuple[str, ...] = ("intrinsic", "extraneous", "germane")


# Intervention typology -- original 10 + 8 new = 18.
InterventionType = Literal[
    # Original 10.
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
    # New v0.2.0.
    "reduce_extraneous_load",
    "chunk_context",
    "add_scaffolding",
    "remove_irrelevant_context",
    "add_intrinsic_load_step_by_step",
    "promote_germane_load",
    "context_compression",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
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
    "reduce_extraneous_load",
    "chunk_context",
    "add_scaffolding",
    "remove_irrelevant_context",
    "add_intrinsic_load_step_by_step",
    "promote_germane_load",
    "context_compression",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- pressure + trace
# ---------------------------------------------------------------------------


class PressureInputs(BaseModel):
    """The pressure inputs applied to the agent for this task."""

    deadline_pressure: Literal["none", "moderate", "tight", "absurd"] = "moderate"
    budget_pressure: Literal["none", "moderate", "tight", "absurd"] = "moderate"
    retry_cap: int | None = Field(default=None, ge=0)
    error_visibility: Literal["low", "medium", "high"] = "medium"
    task_complexity: Literal["simple", "moderate", "complex"] = "moderate"
    # New in v0.2.0 -- CLT + context-saturation indicators.
    context_size_tokens: int | None = Field(default=None, ge=0)
    context_window_size: int | None = Field(default=None, ge=0)
    interrupt_frequency: Literal["none", "low", "moderate", "high"] = "low"
    extraneous_load_indicators: list[str] = Field(default_factory=list)


class AgentPerformanceTrace(BaseModel):
    """An agent performance trace ready for the Yerkes-Dodson diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    pressure: PressureInputs
    observed_behaviors: list[str] = Field(default_factory=list)
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
# Output -- zone evidence + CLT + context saturation
# ---------------------------------------------------------------------------


class WorkloadZoneEvidence(BaseModel):
    """Evidence the agent is operating in a given zone."""

    zone: WorkloadZone
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: Severity = "moderate"


class CognitiveLoadAnalysis(BaseModel):
    """Sweller CLT three-component decomposition. Forensic mode only."""

    intrinsic_load: float = Field(default=0.5, ge=0.0, le=1.0)
    extraneous_load: float = Field(default=0.5, ge=0.0, le=1.0)
    germane_load: float = Field(default=0.5, ge=0.0, le=1.0)
    total_load: float = Field(default=0.5, ge=0.0, le=1.0)
    dominant_component: CognitiveLoadComponent = "intrinsic"
    notes: str = ""


class ContextSaturation(BaseModel):
    """Context-window saturation analysis (LLM-specific)."""

    saturation_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    lost_in_middle_risk: Literal["low", "moderate", "high"] = "low"
    estimated_useful_tokens: int = Field(default=0, ge=0)
    estimated_noise_tokens: int = Field(default=0, ge=0)
    notes: str = ""


class WorkloadIntervention(BaseModel):
    """A concrete intervention to push the agent toward the optimal zone."""

    target_zone: Literal["optimal"] = "optimal"
    intervention_type: InterventionType
    direction: Literal["increase_pressure", "decrease_pressure"]
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

    zone: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_zone: str | None = None
    baseline_profile_pattern: str | None = None
    zone_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of vstack."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class WorkloadDetection(BaseModel):
    """The full Yerkes-Dodson Optimal Workload diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    observed_zone: WorkloadZone
    zone_evidence: list[WorkloadZoneEvidence]
    distance_from_optimal: float = Field(ge=0.0, le=1.0)
    failure_mode: Literal[
        "wandering",
        "focused",
        "corner_cutting",
        "freezing",
        "hallucinating",
        "refusing",
        "unknown",
    ]
    interventions: list[WorkloadIntervention] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: YerkesDodsonMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: WorkloadProfilePattern = "indeterminate"
    cognitive_load_analysis: CognitiveLoadAnalysis | None = None
    context_saturation: ContextSaturation | None = None
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
        out.append("# Yerkes-Dodson Optimal Workload Detection\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Observed zone: **{self.observed_zone.upper()}**_\n")
        out.append(f"_Failure mode: **{self.failure_mode}**_\n")
        out.append(
            f"_Distance from optimal: {self.distance_from_optimal:.2f}  "
            f"(severity: {self.severity})_\n"
        )
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

        out.append("\n## Zone Evidence\n")
        for ev in self.zone_evidence:
            bar = "#" * int(round(ev.score * 20))
            out.append(f"\n### {ev.zone} (score {ev.score:.2f}, severity {ev.severity})  {bar}\n")
            out.append(f"{ev.explanation}\n")
            for q in ev.evidence_quotes:
                out.append(f"> {q}\n")

        if self.cognitive_load_analysis:
            cla = self.cognitive_load_analysis
            out.append("\n## Cognitive Load (Sweller CLT)\n")
            out.append(
                f"- intrinsic: {cla.intrinsic_load:.2f}  "
                f"extraneous: {cla.extraneous_load:.2f}  "
                f"germane: {cla.germane_load:.2f}  "
                f"total: {cla.total_load:.2f}\n"
                f"- dominant_component: `{cla.dominant_component}`\n"
            )
            if cla.notes:
                out.append(f"- _notes:_ {cla.notes}\n")

        if self.context_saturation:
            cs = self.context_saturation
            out.append("\n## Context Saturation\n")
            out.append(
                f"- saturation_ratio: {cs.saturation_ratio:.2f}\n"
                f"- lost_in_middle_risk: `{cs.lost_in_middle_risk}`\n"
                f"- useful tokens: {cs.estimated_useful_tokens}  "
                f"noise tokens: {cs.estimated_noise_tokens}\n"
            )
            if cs.notes:
                out.append(f"- _notes:_ {cs.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(Already in optimal zone -- no interventions needed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(f"\n### Intervention {i}: {iv.direction} via `{iv.intervention_type}`\n")
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
                    f"\n### {pb.title}  _(zone={pb.zone}, failure_mode={pb.failure_mode})_\n"
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
            out.append(f"- **Baseline zone:** {b.baseline_zone or '(unset)'}\n")
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.zone_score_deltas:
                out.append("- **Zone deltas:**\n")
                for k, v in b.zone_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
