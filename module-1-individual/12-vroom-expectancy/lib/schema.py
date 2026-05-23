"""Schema for the Vroom Expectancy Calculator.

Anchored in:
  - Vroom, V. H. (1964) *Work and Motivation.* Wiley -- the canonical
    Expectancy-Instrumentality-Valence statement.
  - Porter, L. W., & Lawler, E. E. (1968) *Managerial Attitudes and
    Performance.* Irwin -- extension to performance + reward.
  - Bandura, A. (1977) ``Self-Efficacy.'' -- expectancy formalization.
  - Eccles, J. S., & Wigfield, A. (2002) ``Motivational Beliefs.''
  - Locke, E. A., & Latham, G. P. (1990) *A Theory of Goal Setting* --
    interaction of goal specificity + expectancy.
  - Kanfer, R., Frese, M., & Johnson, R. E. (2017) ``Motivation Related
    to Work.'' Journal of Applied Psychology 102, 338-355.
  - Modern LLM analogue: Casper et al. (2023) RLHF reward hacking;
    Sharma et al. (2023) sycophancy.

The canonical multiplicative model:

    MOTIVATION = E * I * V

where:
  - EXPECTANCY    (E) -- [0, 1] -- "Do I think I CAN do this?"
  - INSTRUMENTALITY (I) -- [0, 1] -- "If I do it well, will it MATTER?"
  - VALENCE       (V) -- [-1, 1] -- "Is the outcome WORTH it?"

Critical: the product is **MULTIPLICATIVE**. If ANY term approaches
zero, motivation collapses regardless of the other two. The diagnostic
identifies WHICH term is the bottleneck.

Three pipeline modes (consistent with patterns #01-#11):

  - ``quick`` -- 1 LLM call: 3-term score + bottleneck + top intervention.
  - ``standard`` -- 2 LLM calls: per-term evidence + ranked interventions.
  - ``forensic`` -- 4 LLM calls: per-term evidence + system-prompt
    decomposition + EIV interaction audit + ranked interventions with
    composition targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

VROOM_TERMS: tuple[str, ...] = ("expectancy", "instrumentality", "valence")

VroomTerm = Literal["expectancy", "instrumentality", "valence"]
VroomTermOrNone = Literal["expectancy", "instrumentality", "valence", "none"]

VroomMode = Literal["quick", "standard", "forensic"]
VROOM_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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

# Signal categories for system-prompt decomposition.
SignalCategory = Literal[
    "capability_proof",
    "scaffolding",
    "worked_example",
    "outcome_link",
    "purpose_framing",
    "user_connection",
    "pointless_signal",
    "anti_value_signal",
    "expectancy_threat",
    "instrumentality_threat",
    "valence_threat",
    "neutral",
]
SIGNAL_CATEGORIES: tuple[str, ...] = (
    "capability_proof",
    "scaffolding",
    "worked_example",
    "outcome_link",
    "purpose_framing",
    "user_connection",
    "pointless_signal",
    "anti_value_signal",
    "expectancy_threat",
    "instrumentality_threat",
    "valence_threat",
    "neutral",
)

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


def severity_from_motivation(motivation_score: float, quality: str = "motivated") -> Severity:
    """Map motivation_score [-1,1] + quality to 7-point severity.

    Inverse polarity: lower motivation = higher severity.
    Quality 'collapsed' caps severity at >= 'high'.
    Negative valence (avoidance) caps severity at >= 'medium'.
    """
    s = max(-1.0, min(1.0, float(motivation_score)))
    # Map to [0,1] for severity.
    distance = (1.0 - s) / 2.0
    if distance < 0.10:
        base: Severity = "none"
    elif distance < 0.25:
        base = "trace"
    elif distance < 0.40:
        base = "low"
    elif distance < 0.55:
        base = "moderate"
    elif distance < 0.70:
        base = "medium"
    elif distance < 0.85:
        base = "high"
    else:
        base = "critical"

    if quality == "collapsed" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index("high"):
        return "high"
    if s < 0 and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index("medium"):
        return "medium"
    return base


# 12 profile patterns named by the deterministic classifier.
VroomProfilePattern = Literal[
    "motivated_balanced",
    "expectancy_bottleneck",
    "instrumentality_bottleneck",
    "valence_bottleneck",
    "valence_negative_active_avoidance",  # V < 0
    "multi_term_collapse",  # 2+ terms near zero
    "high_E_high_I_low_V_misaligned_task",
    "high_E_low_I_pointless_work",
    "low_E_creative_task_misfit",
    "low_E_tool_use_capability_gap",
    "balanced_but_weak",  # all terms in 0.3-0.6
    "indeterminate",
]
VROOM_PROFILE_PATTERNS: tuple[str, ...] = (
    "motivated_balanced",
    "expectancy_bottleneck",
    "instrumentality_bottleneck",
    "valence_bottleneck",
    "valence_negative_active_avoidance",
    "multi_term_collapse",
    "high_E_high_I_low_V_misaligned_task",
    "high_E_low_I_pointless_work",
    "low_E_creative_task_misfit",
    "low_E_tool_use_capability_gap",
    "balanced_but_weak",
    "indeterminate",
)


# Intervention typology -- original 11 + 7 new = 18.
InterventionType = Literal[
    # Original 11.
    "scaffold_subtasks",
    "add_worked_example",
    "lower_difficulty_step",
    "show_output_consumer",
    "add_outcome_link",
    "add_purpose_framing",
    "remove_pointless_signal",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    # New v0.2.0.
    "show_capability_proof",
    "tighten_goal_specificity",
    "rebalance_value_alignment",
    "remove_anti_value_signal",
    "add_progress_signal",
    "compose_pattern",
    "add_motivation_eval",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "scaffold_subtasks",
    "add_worked_example",
    "lower_difficulty_step",
    "show_output_consumer",
    "add_outcome_link",
    "add_purpose_framing",
    "remove_pointless_signal",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    "show_capability_proof",
    "tighten_goal_specificity",
    "rebalance_value_alignment",
    "remove_anti_value_signal",
    "add_progress_signal",
    "compose_pattern",
    "add_motivation_eval",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- expectancy trace
# ---------------------------------------------------------------------------


class AgentExpectancyTrace(BaseModel):
    """An agent trace ready for the Vroom diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: TaskClass = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    effort_signals: list[str] = Field(
        default_factory=list,
        description="Signals of effort level: depth of work, retries, persistence.",
    )
    outcome: str
    success: bool = False

    # New in v0.2.0.
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    declared_reward: str | None = Field(
        default=None,
        description="The user-facing reward / consequence linked to this task.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- term scores + audits + intervention + handoff
# ---------------------------------------------------------------------------


class VroomTermScore(BaseModel):
    """One Vroom term, scored against the trace."""

    term: VroomTerm
    score: float = Field(
        ge=-1.0,
        le=1.0,
        description="E/I in [0, 1]; V in [-1, 1].",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: Severity = "moderate"


class PromptSignalItem(BaseModel):
    """One signal extracted from the system prompt for forensic decomposition.

    Gagne-Deci 2005 + Locke-Latham 1990 derived categorization.
    """

    category: SignalCategory
    source_quote: str = ""
    affected_term: VroomTermOrNone = "none"
    polarity: Literal["lifts", "lowers", "neutral"] = "neutral"
    explanation: str = ""


class EIVInteractionAudit(BaseModel):
    """Audit of EIV interactions: which pair causes the collapse?

    Forensic mode only. Vroom 1964 + Porter-Lawler 1968.
    """

    dominant_interaction: Literal[
        "E_dominates",
        "I_dominates",
        "V_dominates",
        "E_x_I_low",  # both low together
        "E_x_V_low",
        "I_x_V_low",
        "balanced",
        "unknown",
    ] = "unknown"
    multiplicative_collapse_term: VroomTermOrNone = "none"
    notes: str = ""


class VroomIntervention(BaseModel):
    """A concrete intervention to lift a Vroom term."""

    target_term: VroomTerm
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

    term: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_bottleneck_term: str | None = None
    baseline_profile_pattern: str | None = None
    term_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of AgentCity."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class VroomDetection(BaseModel):
    """The full Vroom Expectancy diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: TaskClass
    terms: list[VroomTermScore]
    motivation_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="E * I * V (clipped). 0 = no motivation; <0 = avoidance.",
    )
    bottleneck_term: VroomTermOrNone
    motivation_quality: Literal["motivated", "weak", "collapsed"]
    interventions: list[VroomIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: VroomMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: VroomProfilePattern = "indeterminate"
    prompt_signals: list[PromptSignalItem] = Field(default_factory=list)
    eiv_interaction_audit: EIVInteractionAudit | None = None
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
        out.append("# Vroom Expectancy Diagnostic\n")
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
            f"(score: {self.motivation_score:.2f}, severity: {self.severity})_\n"
        )
        out.append(f"_Bottleneck term: **{self.bottleneck_term}**_\n")
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

        out.append("\n## E × I × V Breakdown\n")
        for t in self.terms:
            normalized = (t.score + 1.0) / 2.0 if t.term == "valence" else t.score
            bar = "#" * int(round(max(0.0, normalized) * 10))
            out.append(f"- **{t.term}**: {t.score:+.2f} `{bar:<10}` (severity: {t.severity})\n")
            out.append(f"  - {t.explanation}\n")
            if t.evidence_quotes:
                for q in t.evidence_quotes:
                    out.append(f"  > {q}\n")

        out.append(f"\n**E × I × V = {self.motivation_score:.2f}**\n")
        if self.bottleneck_term != "none":
            out.append(
                f"\n(Multiplicative: if any term collapses, motivation collapses. "
                f"Bottleneck: **{self.bottleneck_term}**.)\n"
            )

        if self.prompt_signals:
            out.append("\n## System Prompt Decomposition (Forensic)\n")
            for ps in self.prompt_signals:
                out.append(
                    f"- _{ps.polarity}_ **{ps.category}** (affects {ps.affected_term}): "
                    f"{ps.source_quote}\n"
                )

        if self.eiv_interaction_audit:
            ia = self.eiv_interaction_audit
            out.append("\n## EIV Interaction Audit (Forensic)\n")
            out.append(f"- **Dominant interaction:** {ia.dominant_interaction}\n")
            out.append(f"- **Multiplicative collapse term:** {ia.multiplicative_collapse_term}\n")
            if ia.notes:
                out.append(f"- _notes:_ {ia.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: lift `{iv.target_term}` via `{iv.intervention_type}`\n"
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
                    f"\n### {pb.title}  _(term={pb.term}, failure_mode={pb.failure_mode})_\n"
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
            out.append(f"- **Baseline bottleneck:** {b.baseline_bottleneck_term or '(unset)'}\n")
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.term_score_deltas:
                out.append("- **Term deltas:**\n")
                for k, v in b.term_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
