"""Schema for the DANVA-style Emotion Reader diagnostic.

Drawn from the Diagnostic Analysis of Nonverbal Accuracy (DANVA / DANVA2)
introduced by Stephen Nowicki and Marshall Duke, "A Measure of Nonverbal
Social Processing Ability in Children Between the Ages of 6 and 10
Years" (1994), and the broader emotion-recognition literature
including Ekman's basic emotions (1992).

For human subjects, DANVA tests recognition of emotion from facial
expression, vocal tone, and posture across four canonical emotions
(happy / sad / angry / fearful). For AI agents — which see user
inputs as text — the analog is **emotion recognition from text cues**:
all-caps, exclamation density, hedging, intensifiers, sentiment-loaded
vocabulary, sentence-length collapse / expansion.

This diagnostic measures three things:

  - PER-EMOTION ACCURACY  - did the agent correctly identify each
                              emotion expressed in the user input?
  - INTENSITY CALIBRATION - did the agent's intensity estimate match
                              the actual signal strength?
  - CONFUSION PATTERNS    - which emotions does the agent systematically
                              mistake for which others (e.g., reading
                              "frustrated" as "neutral", reading
                              "sarcastic" as "happy")?

The diagnostic uses 7 canonical emotion labels: happy, sad, angry,
fearful, disgust, surprise, neutral. Plus a "uncertain" fallback for
genuinely ambiguous cases.

Where Pattern #02 (Goleman EI) measures the *competency* of emotion
reading at a high level, this pattern measures the *accuracy* of
emotion identification on specific inputs — a regression metric you
can track per-deploy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EMOTION_CATEGORIES: tuple[str, ...] = (
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprise",
    "neutral",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent emotion trace ---------------------------------------


class EmotionItem(BaseModel):
    """One emotion-recognition trial: a user utterance the agent saw,
    the ground-truth emotion, and the agent's inferred emotion."""

    item_id: str
    user_input: str = Field(description="The actual text the user sent.")
    ground_truth_emotion: Literal[
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgust",
        "surprise",
        "neutral",
    ]
    ground_truth_intensity: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = barely-present cue; 1 = unambiguous strong signal.",
    )
    agent_inferred_emotion: Literal[
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgust",
        "surprise",
        "neutral",
        "uncertain",
    ]
    agent_inferred_intensity: float = Field(ge=0.0, le=1.0, default=0.5)


class AgentEmotionTrace(BaseModel):
    """A batch of emotion-recognition items the agent processed."""

    agent_id: str | None = None
    model_name: str | None = None
    items: list[EmotionItem] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-emotion metrics + interventions ----------------------


class EmotionMetric(BaseModel):
    """Per-emotion accuracy + intensity calibration."""

    emotion: Literal[
        "happy",
        "sad",
        "angry",
        "fearful",
        "disgust",
        "surprise",
        "neutral",
    ]
    n_items: int = Field(
        ge=0, description="How many items in the batch had this ground-truth emotion."
    )
    accuracy: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of items with this ground-truth that the agent identified correctly.",
    )
    intensity_mae: float = Field(
        ge=0.0,
        description="Mean absolute error between inferred and ground-truth intensity for this emotion.",
    )
    confusion_with: dict[str, int] = Field(
        default_factory=dict,
        description="When the agent got this emotion wrong, which other emotion did it pick?",
    )


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
    intervention_type: Literal[
        "add_emotion_reading_step",
        "add_intensity_calibration_step",
        "add_cue_inventory",
        "add_confusion_clarification",
        "few_shot_examples",
        "rewrite_system_prompt",
        "swap_model",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


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

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    n_items: int = Field(ge=0)

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# DANVA-Style Emotion Recognition Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Items in batch: {self.n_items}_\n")
        out.append(f"_Accuracy quality: **{self.accuracy_quality.upper()}**_\n")
        out.append(f"_Overall accuracy: {self.overall_accuracy:.2%}_\n")
        out.append(f"_Overall intensity MAE: {self.overall_intensity_mae:.2f}_\n")
        out.append(f"_Weakest emotion: **{self.weakest_emotion}**_\n")

        out.append("\n## Per-Emotion Metrics\n")
        for m in self.metrics:
            if m.n_items == 0:
                out.append(f"- **{m.emotion}**: (no items in batch)\n")
                continue
            bar = "█" * int(round(m.accuracy * 10))
            out.append(
                f"- **{m.emotion}** ({m.n_items} items): "
                f"accuracy {m.accuracy:.2%} `{bar:<10}`, "
                f"intensity MAE {m.intensity_mae:.2f}\n"
            )
            if m.confusion_with:
                confusions = ", ".join(
                    f"{k} ({v})" for k, v in sorted(m.confusion_with.items(), key=lambda x: -x[1])
                )
                out.append(f"  - confused with: {confusions}\n")

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
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
