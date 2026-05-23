"""Schema for the Cognitive Reappraisal Diagnostic.

Anchored in James Gross's process model of emotion regulation
(Gross 1998, 2001, 2002, 2014; Gross & John 2003 ERQ), the
neuroimaging mechanism literature (Ochsner et al. 2002; Buhle et al.
2014; Powers & LaBar 2019), strategy-effectiveness meta-analyses
(Webb-Miles-Sheeran 2012; Aldao-Nolen-Hoeksema-Schweizer 2010),
strategy-choice (Sheppes-Suri-Gross 2015), rumination decomposition
(Nolen-Hoeksema-Wisco-Lyubomirsky 2008), and the modern LLM bridge:
sycophancy-as-suppression-under-pushback (2024-2025 cluster).

Five Gross strategies plus a "none" fallback:

  - **reappraisal** -- cognitive change. Reinterpret meaning to alter
    affect. Most adaptive across affect/cognition/social (Gross 2002).
  - **suppression** -- response modulation. Hide felt affect. Costs
    memory; raises sympathetic activation; reduces social closeness.
  - **rumination** -- maladaptive repetitive negative thinking.
    Decomposes into *brooding* and *reflection* (NH-Wisco-Lyubomirsky 2008).
  - **avoidance** -- situation selection away from the trigger.
  - **expression** -- direct affective expression.

Three pipeline modes (mirrors patterns #01-#04):

  - ``quick`` -- one LLM call: strategy detection + top intervention.
  - ``standard`` -- two LLM calls (v0.0.x refined).
  - ``forensic`` -- four LLM calls: forensic-strategies + process-model
    phase reconcile + strategy-choice audit (Sheppes 2015) + ranked
    interventions with composition targets.

The LLM bridge -- sycophancy-as-suppression-under-pushback: when an
agent has an initial internal answer and the user pushes back, an LLM
that abandons the answer to reduce friction is performing *response
modulation* on its own affect. The ``suppression_under_pushback``
profile pattern catches this specifically.

Full 14-source literature thread in
:mod:`agentcity.cognitive_reappraisal.CITATIONS` (``lib/CITATIONS.md``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

REGULATION_STRATEGIES: tuple[str, ...] = (
    "reappraisal",
    "suppression",
    "rumination",
    "avoidance",
    "expression",
    "none",
)

Strategy = Literal[
    "reappraisal",
    "suppression",
    "rumination",
    "avoidance",
    "expression",
    "none",
]

PROCESS_MODEL_PHASES: tuple[str, ...] = (
    "situation_selection",
    "situation_modification",
    "attentional_deployment",
    "cognitive_change",
    "response_modulation",
)
ProcessModelPhase = Literal[
    "situation_selection",
    "situation_modification",
    "attentional_deployment",
    "cognitive_change",
    "response_modulation",
    "none",
]

ReappraisalSubType = Literal[
    "reinterpretation",
    "distancing",
    "perspective_taking",
    "none",
]
REAPPRAISAL_SUBTYPES: tuple[str, ...] = (
    "reinterpretation",
    "distancing",
    "perspective_taking",
    "none",
)

RuminationFlavor = Literal["brooding", "reflection", "none"]
RUMINATION_FLAVORS: tuple[str, ...] = ("brooding", "reflection", "none")

ExtendedPhase = Literal["identify", "select", "implement", "monitor"]
EXTENDED_PHASES: tuple[str, ...] = ("identify", "select", "implement", "monitor")

ReappraisalMode = Literal["quick", "standard", "forensic"]
REAPPRAISAL_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_adaptivity(
    adaptivity: Literal["adaptive", "mixed", "maladaptive"],
    dominant_strategy: str = "none",
) -> Severity:
    """Map adaptivity + dominant_strategy to a 7-point severity bucket."""
    if adaptivity == "adaptive":
        return "none"
    if adaptivity == "mixed":
        if dominant_strategy == "rumination":
            return "high"
        return "medium"
    if dominant_strategy == "rumination":
        return "critical"
    if dominant_strategy == "suppression":
        return "high"
    return "medium"


ReappraisalProfilePattern = Literal[
    "reappraisal_skilled",
    "reappraisal_developing",
    "suppression_dominant",
    "suppression_under_pushback",
    "rumination_loop",
    "rumination_brooding",
    "rumination_reflective",
    "avoidance_pivot",
    "expression_only",
    "mixed_unstable",
    "no_regulation",
    "indeterminate",
]
REAPPRAISAL_PROFILE_PATTERNS: tuple[str, ...] = (
    "reappraisal_skilled",
    "reappraisal_developing",
    "suppression_dominant",
    "suppression_under_pushback",
    "rumination_loop",
    "rumination_brooding",
    "rumination_reflective",
    "avoidance_pivot",
    "expression_only",
    "mixed_unstable",
    "no_regulation",
    "indeterminate",
)


InterventionType = Literal[
    "add_reframe_step",
    "remove_suppression_pattern",
    "add_alternative_meaning_generation",
    "add_state_acknowledgment",
    "rewrite_system_prompt",
    "few_shot_reappraisal_examples",
    "swap_model",
    "new_eval",
    "human_review",
    "add_distancing_tactic",
    "add_perspective_taking_tactic",
    "add_reinterpretation_subroutine",
    "break_rumination_loop",
    "disengage_avoidance_pivot",
    "add_strategy_choice_audit",
    "add_intensity_threshold_routing",
    "add_constitutional_principle",
    "compose_pattern",
    "swap_to_reasoning_model",
    "add_anti_sycophancy_anchor",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_reframe_step",
    "remove_suppression_pattern",
    "add_alternative_meaning_generation",
    "add_state_acknowledgment",
    "rewrite_system_prompt",
    "few_shot_reappraisal_examples",
    "swap_model",
    "new_eval",
    "human_review",
    "add_distancing_tactic",
    "add_perspective_taking_tactic",
    "add_reinterpretation_subroutine",
    "break_rumination_loop",
    "disengage_avoidance_pivot",
    "add_strategy_choice_audit",
    "add_intensity_threshold_routing",
    "add_constitutional_principle",
    "compose_pattern",
    "swap_to_reasoning_model",
    "add_anti_sycophancy_anchor",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- trace
# ---------------------------------------------------------------------------


class AgentRegulationTrace(BaseModel):
    """Agent regulation interaction ready for the diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    user_input: str
    user_emotion_label: Literal[
        "angry",
        "sad",
        "fearful",
        "happy",
        "disgust",
        "surprise",
        "neutral",
        "frustrated",
        "anxious",
        "unknown",
    ] = "unknown"
    user_emotion_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    agent_response: str
    agent_internal_state: str = Field(default="")
    outcome: str
    success: bool = False
    # New in v0.2.0.
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    pushback_detected: bool = Field(
        default=False,
        description="True if the user pushed back on a prior agent response.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input", "agent_response", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


class StrategyEvidence(BaseModel):
    """Evidence for one Gross emotion-regulation strategy."""

    strategy: Strategy
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    process_model_phase: ProcessModelPhase = "none"
    reappraisal_subtype: ReappraisalSubType = "none"
    rumination_flavor: RuminationFlavor = "none"


class ProcessModelPhaseEvidence(BaseModel):
    """Per-phase scoring of the 5 Gross 1998 families."""

    phase: ProcessModelPhase
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class AffectivityProfile(BaseModel):
    """Gross-John 2003 ERQ analog at the per-trace level."""

    reappraisal_propensity: float = Field(default=0.5, ge=0.0, le=1.0)
    suppression_propensity: float = Field(default=0.5, ge=0.0, le=1.0)
    rumination_propensity: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = ""


class StrategyChoiceAudit(BaseModel):
    """Sheppes-Suri-Gross 2015 strategy-choice diagnosis."""

    intensity_observed: float = Field(ge=0.0, le=1.0)
    recommended_strategy_by_intensity: Strategy
    actual_dominant_strategy: Strategy
    choice_match: bool = False
    mismatch_severity: Severity = "none"
    notes: str = ""


class CascadeAnalysis(BaseModel):
    """Extended Process Model 4-stage cascade-break diagnosis."""

    cascade_break_point: Literal[
        "intact",
        "fails_at_identify",
        "fails_at_select",
        "fails_at_implement",
        "fails_at_monitor",
    ] = "intact"
    identify_score: float = Field(default=0.5, ge=0.0, le=1.0)
    select_score: float = Field(default=0.5, ge=0.0, le=1.0)
    implement_score: float = Field(default=0.5, ge=0.0, le=1.0)
    monitor_score: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = ""


class RegulationIntervention(BaseModel):
    """A concrete intervention to shift the agent's regulation profile."""

    target_strategy: Literal[
        "reappraisal",
        "suppression",
        "rumination",
        "avoidance",
        "expression",
    ]
    direction: Literal["increase", "decrease"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    reversibility: Literal["one-way-door", "two-way-door"] = "two-way-door"
    composition_target_pattern: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    success_metric: str = ""


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the detection."""

    strategy: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_dominant_strategy: str | None = None
    baseline_profile_pattern: str | None = None
    strategy_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of the AgentCity library."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class RegulationDetection(BaseModel):
    """The full Cognitive Reappraisal Diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    strategy_evidence: list[StrategyEvidence]
    dominant_strategy: Strategy
    adaptivity: Literal["adaptive", "mixed", "maladaptive"]
    interventions: list[RegulationIntervention] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    mode: ReappraisalMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: ReappraisalProfilePattern = "indeterminate"
    process_model_phases: list[ProcessModelPhaseEvidence] = Field(default_factory=list)
    affectivity_profile: AffectivityProfile | None = None
    strategy_choice_audit: StrategyChoiceAudit | None = None
    cascade_analysis: CascadeAnalysis | None = None
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
        out.append("# Cognitive Reappraisal Diagnostic\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Dominant strategy: **{self.dominant_strategy}**_\n")
        out.append(f"_Adaptivity: **{self.adaptivity.upper()}** (severity: {self.severity})_\n")
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

        out.append("\n## Strategy Evidence\n")
        for ev in self.strategy_evidence:
            bar = "#" * int(round(ev.score * 20))
            out.append(
                f"- **{ev.strategy}**: {ev.score:.2f}  {bar}  _(confidence={ev.confidence:.2f})_\n"
            )
            out.append(f"  - {ev.explanation}\n")
            if ev.process_model_phase != "none":
                out.append(f"  - process_model_phase: `{ev.process_model_phase}`\n")
            if ev.reappraisal_subtype != "none":
                out.append(f"  - reappraisal_subtype: `{ev.reappraisal_subtype}`\n")
            if ev.rumination_flavor != "none":
                out.append(f"  - rumination_flavor: `{ev.rumination_flavor}`\n")
            for q in ev.evidence_quotes:
                out.append(f"  - > {q}\n")

        if self.affectivity_profile:
            ap = self.affectivity_profile
            out.append("\n## Affectivity Profile (Gross-John 2003 ERQ analog)\n")
            out.append(
                f"- reappraisal_propensity: {ap.reappraisal_propensity:.2f}  "
                f"suppression_propensity: {ap.suppression_propensity:.2f}  "
                f"rumination_propensity: {ap.rumination_propensity:.2f}\n"
            )
            if ap.notes:
                out.append(f"- _notes:_ {ap.notes}\n")

        if self.strategy_choice_audit:
            sca = self.strategy_choice_audit
            out.append("\n## Strategy Choice Audit (Sheppes-Suri-Gross 2015)\n")
            out.append(
                f"- intensity_observed: {sca.intensity_observed:.2f}\n"
                f"- recommended_strategy: `{sca.recommended_strategy_by_intensity}`\n"
                f"- actual_dominant_strategy: `{sca.actual_dominant_strategy}`\n"
                f"- choice_match: {sca.choice_match}\n"
                f"- mismatch_severity: {sca.mismatch_severity}\n"
            )
            if sca.notes:
                out.append(f"- _notes:_ {sca.notes}\n")

        if self.process_model_phases:
            out.append("\n## Process-Model Phases (Gross 1998)\n")
            for ph in self.process_model_phases:
                bar = "#" * int(round(ph.score * 20))
                out.append(f"- **{ph.phase}**: {ph.score:.2f}  {bar}\n")
                if ph.explanation:
                    out.append(f"  - {ph.explanation}\n")

        if self.cascade_analysis:
            ca = self.cascade_analysis
            out.append("\n## Extended Process Model Cascade (Gross 2015)\n")
            out.append(f"- **Cascade break point:** `{ca.cascade_break_point}`\n")
            out.append(
                f"- identify: {ca.identify_score:.2f}  "
                f"select: {ca.select_score:.2f}  "
                f"implement: {ca.implement_score:.2f}  "
                f"monitor: {ca.monitor_score:.2f}\n"
            )
            if ca.notes:
                out.append(f"- _notes:_ {ca.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_strategy}` "
                f"via `{iv.intervention_type}`\n"
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
                    f"\n### {pb.title}  _(strategy={pb.strategy}, "
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
            out.append(
                f"- **Baseline dominant strategy:** {b.baseline_dominant_strategy or '(unset)'}\n"
            )
            if b.strategy_score_deltas:
                out.append("- **Strategy score deltas:**\n")
                for k, v in b.strategy_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
