"""Schema for the Goleman Emotional Intelligence Audit.

Pattern #02 operationalizes the Goleman/Boyatzis/McKee 2x2 (2002) and
the Mayer-Salovey four-branch ability model (1997) as a single
diagnostic surface for AI agents. The schema bridges three EI
traditions on purpose:

  - **Goleman mixed-model (2x2)** -- *Primal Leadership* (Goleman,
    Boyatzis & McKee 2002). Self x Other on one axis, Recognition x
    Regulation on the other. Four domains: ``self_awareness``,
    ``self_management``, ``social_awareness``,
    ``relationship_management``. The default pipeline lens.
  - **Mayer-Salovey four-branch ability** -- Mayer & Salovey (1997);
    Mayer, Salovey & Caruso (2008). Branches: ``perceive``,
    ``facilitate``, ``understand``, ``manage``. Operationalized by
    the MSCEIT. Available as a forensic-mode overlay so the
    diagnostic can report both lenses when a team is debating
    "is this a knowledge gap or a regulation gap?"
  - **Joseph & Newman 2010 cascade** -- perceive -> understand ->
    regulate -> respond. Mid-stream cascade breaks produce systematic
    failure modes (read-but-don't-act, act-without-reading) that the
    schema names explicitly.

The diagnostic also accounts for the canonical critiques:

  - **Locke (2005)** -- "Why emotional intelligence is an invalid
    concept." Either EI is intelligence applied to emotions (then
    it's not novel) or a bundle of personality + skills (then it's
    not intelligence). The schema's response: publish **both lenses**
    (mixed + ability) separately rather than collapsing them.
  - **Antonakis, Ashkanasy, Dasborough (2009)** -- most EI-leadership
    findings suffer from self-report bias. The schema's response:
    require **observed behaviors** AND **user signals** AND
    **outcome correspondence**, not just ``self_reports``.

Modern LLM-EI literature anchored:

  - **EmoBench** (Sabour et al. 2024) -- two-axis EU/EA structure
    matches the diagnostic's RECOGNITION/REGULATION axis directly.
  - **EQ-Bench** (Paech 2023) -- drops sum-to-10 intensity
    constraints; the schema's ``UserSignal.inferred_intensity``
    is unconstrained on the sum dimension.
  - **Liu et al. 2024** -- Sycophancy bias in emotional-support
    conversation; the schema distinguishes "high social-awareness +
    high relationship-management" from "low social-awareness +
    sycophantic mimicry" via the ``EIProfilePattern`` classifier.

The 11+ academic citations are listed with full bibliographic detail
in :mod:`vstack.goleman_ei.CITATIONS` (lib/CITATIONS.md).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

EI_DOMAINS: tuple[str, ...] = (
    "self_awareness",
    "self_management",
    "social_awareness",
    "relationship_management",
)

EIDomain = Literal[
    "self_awareness",
    "self_management",
    "social_awareness",
    "relationship_management",
]

# Pipeline mode controls how many LLM calls the detector issues and
# which auxiliary passes run. Mirrors Lewin pattern.
EIMode = Literal["quick", "standard", "forensic"]
EI_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_score(score: float) -> Severity:
    """Map a [0,1] EI score to a 7-point severity bucket.

    Inverse polarity from the Lewin diagnostic: in EI, *low* scores
    are the concerning end (the agent has low self-management), so
    severity here reports "how worrying is this low score." 0.0 ->
    critical (no skill); 1.0 -> none (skill excellent).
    """
    s = max(0.0, min(1.0, float(score)))
    if s < 0.15:
        return "critical"
    if s < 0.30:
        return "high"
    if s < 0.45:
        return "medium"
    if s < 0.60:
        return "moderate"
    if s < 0.75:
        return "low"
    if s < 0.90:
        return "trace"
    return "none"


EIProfilePattern = Literal[
    "self_strong_other_weak",
    "other_strong_self_weak",
    "recognition_strong_regulation_weak",
    "regulation_strong_recognition_weak",
    "balanced_high",
    "balanced_developing",
    "balanced_low",
    "indeterminate",
]
EI_PROFILE_PATTERNS: tuple[str, ...] = (
    "self_strong_other_weak",
    "other_strong_self_weak",
    "recognition_strong_regulation_weak",
    "regulation_strong_recognition_weak",
    "balanced_high",
    "balanced_developing",
    "balanced_low",
    "indeterminate",
)


GolemanCompetency = Literal[
    "emotional_self_awareness",
    "accurate_self_assessment",
    "self_confidence",
    "emotional_self_control",
    "adaptability",
    "achievement_orientation",
    "positive_outlook",
    "rejection_recovery",
    "empathy",
    "organizational_awareness",
    "service_orientation",
    "user_state_reading",
    "influence",
    "coach_and_mentor",
    "conflict_management",
    "tone_matching",
    "paraphrase_use",
    "response_length_matching",
    "teamwork",
    "inspirational_leadership",
    "other",
]
GOLEMAN_COMPETENCIES: tuple[str, ...] = (
    "emotional_self_awareness",
    "accurate_self_assessment",
    "self_confidence",
    "emotional_self_control",
    "adaptability",
    "achievement_orientation",
    "positive_outlook",
    "rejection_recovery",
    "empathy",
    "organizational_awareness",
    "service_orientation",
    "user_state_reading",
    "influence",
    "coach_and_mentor",
    "conflict_management",
    "tone_matching",
    "paraphrase_use",
    "response_length_matching",
    "teamwork",
    "inspirational_leadership",
    "other",
)


COMPETENCIES_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "self_awareness": (
        "emotional_self_awareness",
        "accurate_self_assessment",
        "self_confidence",
    ),
    "self_management": (
        "emotional_self_control",
        "adaptability",
        "achievement_orientation",
        "positive_outlook",
        "rejection_recovery",
    ),
    "social_awareness": (
        "empathy",
        "organizational_awareness",
        "service_orientation",
        "user_state_reading",
    ),
    "relationship_management": (
        "influence",
        "coach_and_mentor",
        "conflict_management",
        "tone_matching",
        "paraphrase_use",
        "response_length_matching",
        "teamwork",
        "inspirational_leadership",
    ),
}


InterventionType = Literal[
    "add_confidence_calibration",
    "add_self_check_prompt",
    "add_state_reset_protocol",
    "add_emotion_reading_step",
    "add_paraphrase_requirement",
    "add_tone_matching",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    "add_emotion_label_step",
    "add_intensity_estimation_step",
    "add_reflection_of_feelings",
    "add_response_length_cap",
    "add_response_structure_rule",
    "add_acknowledgment_first_rule",
    "add_kill_criterion",
    "add_recovery_protocol",
    "add_constitutional_principle",
    "swap_to_reasoning_model",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_confidence_calibration",
    "add_self_check_prompt",
    "add_state_reset_protocol",
    "add_emotion_reading_step",
    "add_paraphrase_requirement",
    "add_tone_matching",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    "add_emotion_label_step",
    "add_intensity_estimation_step",
    "add_reflection_of_feelings",
    "add_response_length_cap",
    "add_response_structure_rule",
    "add_acknowledgment_first_rule",
    "add_kill_criterion",
    "add_recovery_protocol",
    "add_constitutional_principle",
    "swap_to_reasoning_model",
    "compose_pattern",
)

EscStrategy = Literal[
    "questioning",
    "restatement",
    "reflection_of_feelings",
    "self_disclosure",
    "affirmation_reassurance",
    "suggestions",
    "providing_information",
    "other",
]
ESC_STRATEGIES: tuple[str, ...] = (
    "questioning",
    "restatement",
    "reflection_of_feelings",
    "self_disclosure",
    "affirmation_reassurance",
    "suggestions",
    "providing_information",
    "other",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- user signals, trace
# ---------------------------------------------------------------------------


class UserSignal(BaseModel):
    """One emotional cue from the user the agent should have read."""

    signal_id: str | None = None
    text: str
    inferred_emotion: Literal[
        "angry",
        "sad",
        "fearful",
        "happy",
        "disgust",
        "surprise",
        "neutral",
        "mixed",
        "unknown",
    ] = "unknown"
    inferred_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TurnSlice(BaseModel):
    """One turn in a multi-turn agent trace (forward-compat slot)."""

    turn_index: int
    user_text: str = ""
    agent_text: str = ""
    agent_internal_state: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CovarianceOnUserState(BaseModel):
    """Does the EI failure depend on the user's emotional state?"""

    fails_on_frustrated_users: Literal["unknown", "no", "mixed", "yes"] = "unknown"
    fails_on_anxious_users: Literal["unknown", "no", "mixed", "yes"] = "unknown"
    fails_on_confused_users: Literal["unknown", "no", "mixed", "yes"] = "unknown"
    fails_on_neutral_users: Literal["unknown", "no", "mixed", "yes"] = "unknown"
    notes: str = ""


class AgentEITrace(BaseModel):
    """A trace ready for the EI Audit diagnostic.

    Backwards-compatible with v0.0.x traces: ``user_signals`` accepts
    either a list of strings (legacy) or a list of :class:`UserSignal`
    objects (v0.2.0). The generator normalizes internally.
    """

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    interaction_class: Literal[
        "customer_support",
        "coaching",
        "advisor",
        "creative_collaborator",
        "code_review",
        "incident_response",
        "general_purpose",
    ] = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    user_signals: list[UserSignal | str] = Field(default_factory=list)
    self_reports: list[str] = Field(default_factory=list)
    outcome: str
    success: bool = False
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_detection_path: str | None = None
    emotional_covariation: CovarianceOnUserState | None = None
    turns: list[TurnSlice] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- domain scores, axis scores, cascade, Mayer overlay
# ---------------------------------------------------------------------------


class DomainScore(BaseModel):
    """One EI domain, scored against the trace."""

    domain: EIDomain
    score: float = Field(ge=0.0, le=1.0)
    severity: Severity = "moderate"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    evidence_signal_ids: list[str] = Field(default_factory=list)
    counterfactual: str = ""
    weakest_competency: GolemanCompetency | None = None
    competency_scores: dict[str, float] = Field(default_factory=dict)


class EIAxisScores(BaseModel):
    """2x2 axis decomposition: SELF/OTHER cols x RECOGNITION/REGULATION rows."""

    self_column: float = Field(ge=0.0, le=1.0)
    other_column: float = Field(ge=0.0, le=1.0)
    recognition_row: float = Field(ge=0.0, le=1.0)
    regulation_row: float = Field(ge=0.0, le=1.0)
    column_gap: float = Field(ge=0.0, le=1.0)
    row_gap: float = Field(ge=0.0, le=1.0)


class MayerSaloveyBranch(BaseModel):
    """One branch of the Mayer-Salovey 4-branch ability model."""

    branch: Literal["perceive", "facilitate", "understand", "manage"]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    cascade_position: Literal["upstream", "midstream", "downstream"]


class CascadeAnalysis(BaseModel):
    """Joseph & Newman (2010) cascade-break diagnosis."""

    cascade_break_point: Literal[
        "intact",
        "fails_at_perceive",
        "fails_at_understand",
        "fails_at_regulate",
        "fails_at_respond",
    ]
    upstream_score: float = Field(ge=0.0, le=1.0)
    midstream_score: float = Field(ge=0.0, le=1.0)
    downstream_score: float = Field(ge=0.0, le=1.0)
    notes: str = ""


# ---------------------------------------------------------------------------
# Output -- interventions
# ---------------------------------------------------------------------------


class EIIntervention(BaseModel):
    """A concrete intervention to develop one EI domain."""

    target_domain: EIDomain
    target_competency: GolemanCompetency | None = None
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
    esc_strategy: EscStrategy | None = None


# ---------------------------------------------------------------------------
# Baseline + composition + playbook
# ---------------------------------------------------------------------------


class EIBaselineComparison(BaseModel):
    """Drift comparison vs a stored historical :class:`EIDetection`."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_weakest_domain: str | None = None
    baseline_profile_pattern: str | None = None
    domain_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of the vstack library."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the detection."""

    domain: EIDomain
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


# ---------------------------------------------------------------------------
# Detection -- the top-level output
# ---------------------------------------------------------------------------


class EIDetection(BaseModel):
    """The full 4-Domain EI Audit output."""

    agent_id: str | None = None
    model_name: str | None = None
    interaction_class: str = "general_purpose"
    domains: list[DomainScore]
    overall_ei: float = Field(ge=0.0, le=1.0)
    ei_quality: Literal["high-ei", "developing", "low-ei"]
    weakest_domain: Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
        "none",
    ]
    interventions: list[EIIntervention]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: EIMode = "standard"
    profile_pattern: EIProfilePattern = "indeterminate"
    axis_scores: EIAxisScores | None = None
    cascade_analysis: CascadeAnalysis | None = None
    mayer_salovey_overlay: list[MayerSaloveyBranch] = Field(default_factory=list)
    emotional_covariation: CovarianceOnUserState | None = None
    baseline: EIBaselineComparison | None = None
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
        out.append("# 4-Domain EI Audit (Emotional Intelligence)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Interaction class: {self.interaction_class}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_EI quality: **{self.ei_quality.upper()}**_\n")
        out.append(f"_Overall EI: {self.overall_ei:.2f}_\n")
        out.append(f"_Weakest domain: **{self.weakest_domain}**_\n")
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

        out.append("\n## Per-Domain Scores\n")
        for d in self.domains:
            bar = "#" * int(round(d.score * 20))
            out.append(
                f"- **{d.domain}**: {d.score:.2f}  {bar}  "
                f"_(severity={d.severity}, confidence={d.confidence:.2f})_\n"
            )
            out.append(f"  - {d.explanation}\n")
            if d.weakest_competency:
                out.append(f"  - weakest competency: `{d.weakest_competency}`\n")
            if d.evidence_quotes:
                for q in d.evidence_quotes:
                    out.append(f"  - > {q}\n")
            if d.counterfactual:
                out.append(f"  - **counterfactual:** {d.counterfactual}\n")

        if self.axis_scores and len(self.domains) >= 4:
            ax = self.axis_scores
            sa = self.domains[0].score
            sm = self.domains[1].score
            soa = self.domains[2].score
            rm = self.domains[3].score
            out.append("\n## 2x2 Axis Decomposition\n")
            out.append(
                "|  | RECOGNITION | REGULATION |\n"
                "|---|---|---|\n"
                f"| **SELF** | {sa:.2f} | {sm:.2f} |\n"
                f"| **OTHER** | {soa:.2f} | {rm:.2f} |\n"
                f"\n_SELF column: {ax.self_column:.2f} - OTHER column: {ax.other_column:.2f} "
                f"- column gap: {ax.column_gap:.2f}_\n"
                f"_RECOGNITION row: {ax.recognition_row:.2f} - REGULATION row: {ax.regulation_row:.2f} "
                f"- row gap: {ax.row_gap:.2f}_\n"
            )

        if self.cascade_analysis:
            ca = self.cascade_analysis
            out.append("\n## Joseph-Newman Cascade Analysis\n")
            out.append(f"- **Cascade break point:** `{ca.cascade_break_point}`\n")
            out.append(
                f"- **Upstream** (perceive): {ca.upstream_score:.2f}  "
                f"**Midstream** (understand+facilitate): {ca.midstream_score:.2f}  "
                f"**Downstream** (regulate+respond): {ca.downstream_score:.2f}\n"
            )
            if ca.notes:
                out.append(f"- _notes:_ {ca.notes}\n")

        if self.mayer_salovey_overlay:
            out.append("\n## Mayer-Salovey 4-Branch Ability Overlay\n")
            for branch in self.mayer_salovey_overlay:
                bar = "#" * int(round(branch.score * 20))
                out.append(
                    f"- **{branch.branch}** ({branch.cascade_position}): "
                    f"{branch.score:.2f}  {bar}\n  - {branch.explanation}\n"
                )

        if self.emotional_covariation:
            ec = self.emotional_covariation
            out.append("\n## Emotional Covariation\n")
            out.append(f"- fails_on_frustrated_users: {ec.fails_on_frustrated_users}\n")
            out.append(f"- fails_on_anxious_users: {ec.fails_on_anxious_users}\n")
            out.append(f"- fails_on_confused_users: {ec.fails_on_confused_users}\n")
            out.append(f"- fails_on_neutral_users: {ec.fails_on_neutral_users}\n")
            if ec.notes:
                out.append(f"- _notes:_ {ec.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: develop `{iv.target_domain}`"
                + (f" / `{iv.target_competency}`" if iv.target_competency else "")
                + f" via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            out.append(f"- **Effort:** {iv.effort_estimate}\n")
            out.append(f"- **Risk:** {iv.risk}\n")
            out.append(f"- **Reversibility:** {iv.reversibility}\n")
            if iv.esc_strategy:
                out.append(f"- **ESConv strategy:** `{iv.esc_strategy}`\n")
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
                    f"\n### {pb.title}  _(domain={pb.domain}, failure_mode={pb.failure_mode})_\n"
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
            out.append(f"- **Baseline weakest domain:** {b.baseline_weakest_domain or '(unset)'}\n")
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.domain_score_deltas:
                out.append("- **Score deltas:**\n")
                for k, v in b.domain_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
