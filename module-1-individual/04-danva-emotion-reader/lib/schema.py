"""Schema for the DANVA-style Emotion Reader diagnostic.

Anchored in the Diagnostic Analysis of Nonverbal Accuracy (DANVA /
DANVA2; Nowicki & Duke 1994, 2001), Ekman's basic emotions (1992,
1999), Plutchik's wheel (2001), Russell's circumplex (1980),
Mehrabian's PAD (1980), and modern LLM emotion-recognition benchmarks
(GoEmotions Demszky 2020, EmotionLines Chen 2018, EmoBank Buechel
2017, EmoBench Sabour 2024, EmotionQueen Wang 2024, NRC-VAD Mohammad
2018, WASSA-2017 emotion intensity).

For human subjects, DANVA tests recognition of emotion from facial,
vocal, and postural cues. For AI agents -- which see user inputs as
text -- the analog is **emotion recognition from text cues**:
all-caps spans, exclamation density, hedging, intensifiers,
sentiment-loaded vocabulary, sentence-length collapse / expansion.

The diagnostic measures four things:

  - **Per-emotion accuracy** -- did the agent correctly identify each
    emotion expressed in the user input?
  - **Intensity calibration** -- did the agent's intensity estimate
    match the actual signal strength?
  - **Confusion patterns** -- which emotions does the agent
    systematically mistake for which others?
  - **Dimensional projection** (forensic mode) -- Russell circumplex
    valence/arousal placement, providing a complementary lens to the
    categorical/Ekman one (per Posner-Russell-Peterson 2005's
    integrative reconciliation).

The schema ships seven canonical Ekman emotion labels (happy, sad,
angry, fearful, disgust, surprise, neutral) plus an "uncertain"
fallback. Forensic mode also exposes the GoEmotions 27-category
extended overlay.

Three pipeline modes (consistent with patterns #01-#03):

  - ``quick`` -- one LLM call: per-emotion + top intervention. ~$0.005.
  - ``standard`` -- two LLM calls. ~$0.015. (v0.0.x behavior refined.)
  - ``forensic`` -- four LLM calls: per-emotion + dimensional overlay
    + cascade-reconcile + ranked interventions w/ composition targets.
    ~$0.05.

Where Pattern #02 (Goleman EI) measures the *competency* of emotion
reading at a high level, Pattern #04 measures the *accuracy* of
emotion identification on specific inputs -- a regression metric you
can track per-deploy. The two compose: #02's `social_awareness`
weakest -> #04 drills in.

The 14-source literature thread with per-citation usage notes is in
:mod:`agentcity.danva_emotion.CITATIONS` (``lib/CITATIONS.md``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

EMOTION_CATEGORIES: tuple[str, ...] = (
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprise",
    "neutral",
)

EmotionCategory = Literal[
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprise",
    "neutral",
]

InferredEmotion = Literal[
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprise",
    "neutral",
    "uncertain",
]

# Pipeline mode (mirrors Lewin / Goleman / Johari).
DANVAMode = Literal["quick", "standard", "forensic"]
DANVA_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# 7-point severity scale. Inverse polarity from Lewin (matches Goleman /
# Johari): low accuracy -> high severity.
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


def severity_from_accuracy(accuracy: float) -> Severity:
    """Map a [0,1] accuracy score to a 7-point severity bucket.

    Inverse polarity: low accuracy -> high severity. 0.0 -> critical;
    1.0 -> none. Mirrors :func:`agentcity.goleman_ei.severity_from_score`.
    """
    s = max(0.0, min(1.0, float(accuracy)))
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


# 14 profile patterns named by the diagnostic's deterministic classifier.
DANVAProfilePattern = Literal[
    "balanced_high",
    "balanced_developing",
    "balanced_low",
    "anger_blind",
    "sadness_collapse",
    "positive_bias",
    "negative_bias",
    "valence_only_signal",
    "categorical_signal_only",
    "fear_sadness_confusion",
    "neutral_collapse",
    "uncertain_dump",
    "sarcasm_blind",
    "indeterminate",
]
DANVA_PROFILE_PATTERNS: tuple[str, ...] = (
    "balanced_high",
    "balanced_developing",
    "balanced_low",
    "anger_blind",
    "sadness_collapse",
    "positive_bias",
    "negative_bias",
    "valence_only_signal",
    "categorical_signal_only",
    "fear_sadness_confusion",
    "neutral_collapse",
    "uncertain_dump",
    "sarcasm_blind",
    "indeterminate",
)


# Cue explicitness tag for forensic mode. Distinguishes explicit
# emotion cues (caps, exclamations) from implicit (sarcasm, hedging).
CueExplicitness = Literal["explicit", "implicit", "sarcastic"]

# Cultural display-rule overlay context (Matsumoto & Hwang 2018).
CulturalContext = Literal[
    "wei-individualist",
    "wei-collectivist",
    "japanese",
    "arab",
    "latin",
    "mixed",
    "unknown",
]

# Extended emotion taxonomy (GoEmotions Demszky et al. 2020 + Cowen-Keltner
# 2017). Optional; remaps to canonical 7 via _to_canonical_emotion().
ExtendedEmotion = Literal[
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "neutral",
]


# Intervention typology. v0.0.x had 9; v0.2.0 extends to 18 including
# compose_pattern + composition-conditional types.
InterventionType = Literal[
    # v0.0.x
    "add_emotion_reading_step",
    "add_intensity_calibration_step",
    "add_cue_inventory",
    "add_confusion_clarification",
    "few_shot_examples",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    # v0.2.0
    "add_sarcasm_detection_step",
    "add_cultural_context_check",
    "add_uncertainty_threshold",
    "add_min_cue_threshold",
    "add_dimensional_overlay",
    "add_valence_arousal_disambig",
    "compose_pattern",
    "add_constitutional_principle",
    "swap_to_reasoning_model",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_emotion_reading_step",
    "add_intensity_calibration_step",
    "add_cue_inventory",
    "add_confusion_clarification",
    "few_shot_examples",
    "rewrite_system_prompt",
    "swap_model",
    "new_eval",
    "human_review",
    "add_sarcasm_detection_step",
    "add_cultural_context_check",
    "add_uncertainty_threshold",
    "add_min_cue_threshold",
    "add_dimensional_overlay",
    "add_valence_arousal_disambig",
    "compose_pattern",
    "add_constitutional_principle",
    "swap_to_reasoning_model",
)


EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Cue extraction (deterministic) + NRC-VAD calibration
# ---------------------------------------------------------------------------


class TextCueSignature(BaseModel):
    """LIWC-anchored deterministic text cue features (Tausczik-Pennebaker 2010)."""

    caps_span_count: int = 0
    caps_density: float = 0.0
    exclamation_count: int = 0
    exclamation_density: float = 0.0
    question_count: int = 0
    intensifier_count: int = 0
    hedge_count: int = 0
    negation_count: int = 0
    sentence_count: int = 0
    mean_sentence_length: float = 0.0
    ellipsis_count: int = 0
    profanity_count: int = 0
    future_tense_count: int = 0
    past_tense_loss_count: int = 0
    positive_emotion_word_count: int = 0
    negative_emotion_word_count: int = 0
    sarcasm_signature_count: int = 0


class PerEmotionCalibration(BaseModel):
    """Mohammad-NRC-VAD per-emotion lexical baseline for one user_input.

    Deterministic VAD scoring of the input text against the NRC-VAD
    lexicon. Provides a no-LLM ground-truth baseline that the agent's
    inference can be compared against (vad_divergence_from_agent).
    """

    item_id: str
    nrc_vad_valence: float | None = None
    nrc_vad_arousal: float | None = None
    nrc_vad_dominance: float | None = None
    nrc_predicted_emotion: EmotionCategory | None = None
    nrc_predicted_intensity: float = 0.5
    vad_divergence_from_agent: float = 0.0
    cue_signature: TextCueSignature = Field(default_factory=TextCueSignature)


# ---------------------------------------------------------------------------
# Input -- emotion items + trace
# ---------------------------------------------------------------------------


class EmotionItem(BaseModel):
    """One emotion-recognition trial.

    v0.2.0 adds: cue_explicitness (explicit/implicit/sarcastic),
    extended_emotion (GoEmotions overlay), cultural_context
    (Matsumoto display-rule overlay).
    """

    item_id: str
    user_input: str = Field(description="The actual text the user sent.")
    ground_truth_emotion: EmotionCategory
    ground_truth_intensity: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = barely-present cue; 1 = unambiguous strong signal.",
    )
    agent_inferred_emotion: InferredEmotion
    agent_inferred_intensity: float = Field(ge=0.0, le=1.0, default=0.5)
    # New in v0.2.0.
    cue_explicitness: CueExplicitness = "explicit"
    extended_emotion: ExtendedEmotion | None = None
    cultural_context: CulturalContext = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentEmotionTrace(BaseModel):
    """A batch of emotion-recognition items the agent processed."""

    agent_id: str | None = None
    model_name: str | None = None
    items: list[EmotionItem] = Field(min_length=1)
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    cultural_context: CulturalContext = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("items")
    @classmethod
    def _non_empty(cls, v: list[EmotionItem]) -> list[EmotionItem]:
        if not v:
            raise ValueError("items cannot be empty")
        return v


# ---------------------------------------------------------------------------
# Output -- per-emotion metrics + dimensional overlay + cascade
# ---------------------------------------------------------------------------


class EmotionMetric(BaseModel):
    """Per-emotion accuracy + intensity calibration."""

    emotion: EmotionCategory
    n_items: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    intensity_mae: float = Field(ge=0.0)
    confusion_with: dict[str, int] = Field(default_factory=dict)
    # New in v0.2.0.
    severity: Severity = "moderate"
    intensity_bias: float = Field(
        default=0.0,
        description="mean(inferred) - mean(truth). Negative = under-reads "
        "intensity (sadness_collapse signature).",
    )
    intensity_correlation: float = Field(default=0.0, ge=-1.0, le=1.0)


class EmotionConfusionMatrix(BaseModel):
    """Typed confusion matrix: 7 ground-truth rows x 8 inferred columns."""

    emotions_ground_truth: tuple[str, ...] = EMOTION_CATEGORIES
    emotions_inferred: tuple[str, ...] = (*EMOTION_CATEGORIES, "uncertain")
    matrix: dict[str, dict[str, int]] = Field(default_factory=dict)
    row_totals: dict[str, int] = Field(default_factory=dict)
    column_totals: dict[str, int] = Field(default_factory=dict)
    diagonal_total: int = 0


class IntensityCurve(BaseModel):
    """Per-emotion intensity calibration curve."""

    emotion: EmotionCategory
    n_items: int = Field(ge=0)
    truth_bins: list[float] = Field(default_factory=list)
    mean_inferred_by_bin: list[float] = Field(default_factory=list)
    intensity_bias: float = 0.0
    intensity_correlation: float = 0.0
    intensity_collapse_score: float = Field(
        default=1.0,
        description="var(inferred) / var(truth). << 1.0 = collapse.",
    )


class CircumplexProjection(BaseModel):
    """Russell circumplex (valence x arousal) projection per item or batch."""

    valence_truth: float = Field(ge=-1.0, le=1.0)
    arousal_truth: float = Field(ge=-1.0, le=1.0)
    valence_inferred: float = Field(ge=-1.0, le=1.0)
    arousal_inferred: float = Field(ge=-1.0, le=1.0)
    euclidean_distance: float = Field(ge=0.0)
    quadrant_truth: Literal["high-pos", "high-neg", "low-pos", "low-neg"]
    quadrant_inferred: Literal["high-pos", "high-neg", "low-pos", "low-neg"]
    quadrant_match: bool = False


class CulturalAdjustment(BaseModel):
    """Matsumoto display-rule overlay (cultural-context emotion suppression)."""

    culture_context: CulturalContext = "unknown"
    expected_suppression_for_emotion: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class CascadeAnalysis(BaseModel):
    """Recognition cascade-break diagnosis.

    Cascade: perceive raw cues -> categorize -> estimate intensity -> respond.
    Forensic mode names the earliest stage at which competence drops.
    """

    cascade_break_point: Literal[
        "intact",
        "fails_at_perceive_cue",
        "fails_at_categorize",
        "fails_at_intensity",
        "fails_at_respond",
    ] = "intact"
    perceive_score: float = Field(default=0.5, ge=0.0, le=1.0)
    categorize_score: float = Field(default=0.5, ge=0.0, le=1.0)
    intensity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    respond_score: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = ""


# ---------------------------------------------------------------------------
# Output -- interventions, playbooks, baseline, composition
# ---------------------------------------------------------------------------


class EmotionIntervention(BaseModel):
    """A concrete intervention to improve emotion-reading accuracy."""

    target_emotion: Literal[
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgust",
        "surprise",
        "neutral",
        "all",
    ]
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
    """A failure-mode playbook attached to the analysis."""

    emotion: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical :class:`EmotionRecognitionAnalysis`."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_weakest_emotion: str | None = None
    baseline_profile_pattern: str | None = None
    emotion_accuracy_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this analysis feeds into the rest of the AgentCity library."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


# ---------------------------------------------------------------------------
# Analysis -- the top-level output
# ---------------------------------------------------------------------------


class EmotionRecognitionAnalysis(BaseModel):
    """The full DANVA-style emotion-recognition diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    metrics: list[EmotionMetric]
    overall_accuracy: float = Field(ge=0.0, le=1.0)
    overall_intensity_mae: float = Field(ge=0.0)
    weakest_emotion: Literal[
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgust",
        "surprise",
        "neutral",
        "none",
    ]
    accuracy_quality: Literal["high-accuracy", "developing", "low-accuracy"]
    interventions: list[EmotionIntervention]
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    n_items: int = Field(ge=0)

    # New in v0.2.0.
    mode: DANVAMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: DANVAProfilePattern = "indeterminate"
    confusion_matrix: EmotionConfusionMatrix | None = None
    intensity_curves: list[IntensityCurve] = Field(default_factory=list)
    circumplex_projection: CircumplexProjection | None = None
    cultural_adjustment: CulturalAdjustment | None = None
    cascade_analysis: CascadeAnalysis | None = None
    per_item_calibration: list[PerEmotionCalibration] = Field(default_factory=list)
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
        out.append("# DANVA-Style Emotion Recognition Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Items in batch: {self.n_items}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(
            f"_Accuracy quality: **{self.accuracy_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Overall accuracy: {self.overall_accuracy:.2%}_\n")
        out.append(f"_Overall intensity MAE: {self.overall_intensity_mae:.2f}_\n")
        out.append(f"_Weakest emotion: **{self.weakest_emotion}**_\n")
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

        out.append("\n## Per-Emotion Metrics\n")
        for m in self.metrics:
            if m.n_items == 0:
                out.append(f"- **{m.emotion}**: (no items in batch)\n")
                continue
            bar = "#" * int(round(m.accuracy * 10))
            out.append(
                f"- **{m.emotion}** ({m.n_items} items): "
                f"accuracy {m.accuracy:.2%} `{bar:<10}`, "
                f"intensity MAE {m.intensity_mae:.2f}, "
                f"bias {m.intensity_bias:+.2f}, "
                f"severity {m.severity}\n"
            )
            if m.confusion_with:
                confusions = ", ".join(
                    f"{k} ({v})" for k, v in sorted(m.confusion_with.items(), key=lambda x: -x[1])
                )
                out.append(f"  - confused with: {confusions}\n")

        if self.intensity_curves:
            out.append("\n## Intensity Calibration Curves\n")
            for c in self.intensity_curves:
                if c.n_items == 0:
                    continue
                out.append(
                    f"- **{c.emotion}**: bias {c.intensity_bias:+.2f}, "
                    f"correlation {c.intensity_correlation:.2f}, "
                    f"collapse score {c.intensity_collapse_score:.2f}\n"
                )

        if self.circumplex_projection:
            cp = self.circumplex_projection
            out.append("\n## Russell Circumplex Projection\n")
            out.append(
                f"- truth: valence={cp.valence_truth:+.2f}, arousal={cp.arousal_truth:+.2f} "
                f"({cp.quadrant_truth})\n"
                f"- inferred: valence={cp.valence_inferred:+.2f}, "
                f"arousal={cp.arousal_inferred:+.2f} ({cp.quadrant_inferred})\n"
                f"- euclidean distance: {cp.euclidean_distance:.2f}\n"
                f"- quadrant match: {cp.quadrant_match}\n"
            )

        if self.cascade_analysis:
            ca = self.cascade_analysis
            out.append("\n## Recognition Cascade Analysis\n")
            out.append(f"- **Cascade break point:** `{ca.cascade_break_point}`\n")
            out.append(
                f"- perceive_cue: {ca.perceive_score:.2f}  "
                f"categorize: {ca.categorize_score:.2f}  "
                f"intensity: {ca.intensity_score:.2f}  "
                f"respond: {ca.respond_score:.2f}\n"
            )
            if ca.notes:
                out.append(f"- _notes:_ {ca.notes}\n")

        if self.cultural_adjustment:
            cadj = self.cultural_adjustment
            out.append("\n## Cultural Adjustment (Matsumoto display rules)\n")
            out.append(f"- culture context: {cadj.culture_context}\n")
            if cadj.expected_suppression_for_emotion:
                for k, v in cadj.expected_suppression_for_emotion.items():
                    out.append(f"  - {k}: suppression {v:.2f}\n")
            if cadj.notes:
                out.append(f"- _notes:_ {cadj.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: improve `{iv.target_emotion}` "
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
                    f"\n### {pb.title}  _(emotion={pb.emotion}, failure_mode={pb.failure_mode})_\n"
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
                f"- **Baseline weakest emotion:** {b.baseline_weakest_emotion or '(unset)'}\n"
            )
            if b.emotion_accuracy_deltas:
                out.append("- **Accuracy deltas:**\n")
                for k, v in b.emotion_accuracy_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
