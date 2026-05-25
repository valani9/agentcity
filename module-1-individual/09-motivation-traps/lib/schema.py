"""Schema for the 4 Motivation Traps Detector.

Anchored in:
  - Saxberg, B. (2013) (with Hess, F. M.) *Breakthrough Leadership in the
    Digital Age* -- the synthesis of the four-traps framework.
  - Saxberg's subsequent learning-science writing (Kern Foundation;
    HBR).
  - Weiner, B. (1985) ``An Attributional Theory of Achievement
    Motivation and Emotion.'' Psychological Review 92, 548-573 --
    the locus / stability / controllability attribution structure.
  - Bandura, A. (1977) ``Self-Efficacy: Toward a Unifying Theory of
    Behavioral Change.'' Psychological Review 84, 191-215 -- the
    self-efficacy anchor.
  - Vroom, V. H. (1964) *Work and Motivation* -- the expectancy /
    valence framework underlying VALUES.
  - Pekrun, R. (2006) ``The Control-Value Theory of Achievement
    Emotions.'' Educational Psychology Review 18, 315-341 -- the
    EMOTIONS anchor.
  - Eccles, J., & Wigfield, A. (2002) ``Motivational Beliefs, Values,
    and Goals.'' Annual Review of Psychology 53, 109-132.
  - Modern LLM analogues: Sharma et al. (2023) sycophancy; refusal
    cascade studies; Anthropic 2024 capability-elicitation work.

Four discrete traps:

  - VALUES        -- the agent doesn't see the task as worth doing.
  - SELF_EFFICACY -- the agent doesn't believe it can succeed.
  - EMOTIONS      -- emotional state blocks engagement.
  - ATTRIBUTION   -- the agent blames wrong cause for prior failures.

Saxberg's core insight: the four traps require four DIFFERENT
interventions. Generic "try harder" prompts are explicitly
ineffective. The diagnostic identifies the dominant trap and proposes
a trap-specific intervention.

Three pipeline modes (consistent with patterns #01-#08):

  - ``quick`` -- 1 LLM call: 4-trap score + dominant + top intervention.
  - ``standard`` -- 2 LLM calls: per-trap evidence + ranked interventions.
  - ``forensic`` -- 4 LLM calls: per-trap evidence + Weiner attribution
    triple-axis audit + abandonment causation chain + ranked
    interventions with composition targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

MOTIVATION_TRAPS: tuple[str, ...] = (
    "values",
    "self_efficacy",
    "emotions",
    "attribution",
)

MotivationTrap = Literal["values", "self_efficacy", "emotions", "attribution"]
DominantTrap = Literal["values", "self_efficacy", "emotions", "attribution", "none"]

MotivationMode = Literal["quick", "standard", "forensic"]
MOTIVATION_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

TaskClass = Literal[
    "code_generation",
    "research",
    "creative",
    "analysis",
    "customer_facing",
    "tool_use",
    "general_purpose",
]
TASK_CLASSES: tuple[str, ...] = (
    "code_generation",
    "research",
    "creative",
    "analysis",
    "customer_facing",
    "tool_use",
    "general_purpose",
)

# Weiner's 3-axis attribution structure.
WeinerLocus = Literal["internal", "external"]
WeinerStability = Literal["stable", "unstable"]
WeinerControllability = Literal["controllable", "uncontrollable"]

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


def severity_from_trap_score(score: float, quality: str = "motivated") -> Severity:
    """Map [0,1] dominant trap score + motivation_quality to 7-point severity."""
    s = max(0.0, min(1.0, float(score)))
    if s < 0.10:
        base: Severity = "none"
    elif s < 0.25:
        base = "trace"
    elif s < 0.40:
        base = "low"
    elif s < 0.55:
        base = "moderate"
    elif s < 0.70:
        base = "medium"
    elif s < 0.85:
        base = "high"
    else:
        base = "critical"

    # Quality floor.
    if quality == "abandoning" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index("medium"):
        return "medium"
    return base


# 12 profile patterns named by the deterministic classifier.
MotivationProfilePattern = Literal[
    "motivated_baseline",
    "values_dominant_irrelevance",
    "self_efficacy_collapse_uncertainty",
    "emotions_post_rejection_cascade",
    "attribution_loop_wrong_cause",
    "values_plus_attribution",  # disengaged + blames externals
    "self_efficacy_plus_emotions",  # giving up + emotional
    "self_efficacy_plus_attribution",  # giving up + blaming self uncontrollably
    "high_stakes_capability_collapse",  # tool_use/high-stakes + low SE
    "creative_task_value_misfit",  # creative + low values
    "indeterminate",
    "multi_trap_compounded",
]
MOTIVATION_PROFILE_PATTERNS: tuple[str, ...] = (
    "motivated_baseline",
    "values_dominant_irrelevance",
    "self_efficacy_collapse_uncertainty",
    "emotions_post_rejection_cascade",
    "attribution_loop_wrong_cause",
    "values_plus_attribution",
    "self_efficacy_plus_emotions",
    "self_efficacy_plus_attribution",
    "high_stakes_capability_collapse",
    "creative_task_value_misfit",
    "indeterminate",
    "multi_trap_compounded",
)


# Intervention typology -- original 12 + 6 new = 18.
InterventionType = Literal[
    # Original 12.
    "reframe_task_value",
    "scaffold_subtasks",
    "decompose_with_examples",
    "lower_difficulty_step",
    "emotional_reset_prompt",
    "remove_punitive_signal",
    "reattribute_to_effort",
    "show_controllable_cause",
    "explicit_recovery_prompt",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    # New v0.2.0.
    "ground_in_user_purpose",
    "show_capability_proof",
    "process_praise_not_outcome_praise",
    "attribution_retraining_examples",
    "compose_pattern",
    "add_motivation_eval",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "reframe_task_value",
    "scaffold_subtasks",
    "decompose_with_examples",
    "lower_difficulty_step",
    "emotional_reset_prompt",
    "remove_punitive_signal",
    "reattribute_to_effort",
    "show_controllable_cause",
    "explicit_recovery_prompt",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    "ground_in_user_purpose",
    "show_capability_proof",
    "process_praise_not_outcome_praise",
    "attribution_retraining_examples",
    "compose_pattern",
    "add_motivation_eval",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- motivation trace
# ---------------------------------------------------------------------------


class AgentMotivationTrace(BaseModel):
    """A trace ready for the 4 Motivation Traps diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: TaskClass = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    self_reports: list[str] = Field(
        default_factory=list,
        description=("Explicit agent statements about confidence / effort / blame."),
    )
    abandonment_signal: str = Field(
        description="What the agent did when it gave up (refused / looped / drifted).",
    )
    outcome: str
    success: bool = False

    # New in v0.2.0.
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    prior_failures: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome", "abandonment_signal")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- evidence + audits + intervention + handoff
# ---------------------------------------------------------------------------


class TrapEvidence(BaseModel):
    """One motivation trap, scored against the trace."""

    trap: MotivationTrap
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = trap not present; 1 = trap is dominant in the abandonment pattern.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: Severity = "moderate"


class WeinerAttributionAxis(BaseModel):
    """Weiner's 3-axis attribution audit on the agent's self-reports.

    Forensic mode only. Weiner (1985) shows that maladaptive attribution
    is the combination of: (a) internal locus, (b) stable trait, (c)
    uncontrollable cause -- "I'm just bad at this." The corrective is
    to reframe toward internal-unstable-controllable -- "I haven't put
    in enough effort yet."
    """

    locus: WeinerLocus
    stability: WeinerStability
    controllability: WeinerControllability
    is_maladaptive: bool = False
    explanation: str = ""
    evidence_quotes: list[str] = Field(default_factory=list)


class AbandonmentLink(BaseModel):
    """One link in the chain from trap onset to task abandonment.

    Forensic mode only.
    """

    step_index: int = Field(ge=0)
    trap: MotivationTrap
    signal_type: Literal[
        "refusal",
        "drift",
        "loop",
        "premature_completion",
        "defensive_response",
        "indifference",
        "other",
    ]
    observed_text: str = ""
    severity: Severity = "moderate"


class MotivationIntervention(BaseModel):
    """A concrete intervention targeted at the dominant trap."""

    target_trap: MotivationTrap
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

    trap: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_dominant_trap: str | None = None
    baseline_profile_pattern: str | None = None
    trap_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of vstack."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class MotivationDetection(BaseModel):
    """The full 4 Motivation Traps diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: TaskClass
    trap_evidence: list[TrapEvidence]
    dominant_trap: DominantTrap
    motivation_quality: Literal["motivated", "at-risk", "abandoning"]
    interventions: list[MotivationIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: MotivationMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: MotivationProfilePattern = "indeterminate"
    attribution_axis: WeinerAttributionAxis | None = None
    abandonment_chain: list[AbandonmentLink] = Field(default_factory=list)
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
        out.append("# 4 Motivation Traps Diagnostic (Saxberg)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Motivation quality: **{self.motivation_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Dominant trap: **{self.dominant_trap}**_\n")
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

        out.append("\n## Per-Trap Evidence\n")
        for ev in self.trap_evidence:
            bar = "#" * int(round(ev.score * 10))
            out.append(
                f"\n### {ev.trap} (score {ev.score:.2f}, severity {ev.severity}) `{bar:<10}`\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.attribution_axis:
            ax = self.attribution_axis
            out.append("\n## Weiner Attribution Axis (Forensic)\n")
            out.append(
                f"- locus={ax.locus}, stability={ax.stability}, "
                f"controllability={ax.controllability}, "
                f"maladaptive={ax.is_maladaptive}\n"
            )
            if ax.explanation:
                out.append(f"- {ax.explanation}\n")

        if self.abandonment_chain:
            out.append("\n## Abandonment Causation Chain (Forensic)\n")
            for link in self.abandonment_chain:
                out.append(
                    f"- step {link.step_index} ({link.trap} -> "
                    f"{link.signal_type}, {link.severity}): {link.observed_text}\n"
                )

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: target `{iv.target_trap}` via `{iv.intervention_type}`\n"
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
                    f"\n### {pb.title}  _(trap={pb.trap}, failure_mode={pb.failure_mode})_\n"
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
            out.append(f"- **Baseline dominant trap:** {b.baseline_dominant_trap or '(unset)'}\n")
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.trap_score_deltas:
                out.append("- **Trap deltas:**\n")
                for k, v in b.trap_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
