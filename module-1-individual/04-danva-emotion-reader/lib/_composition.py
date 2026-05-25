"""Cross-pattern composition manifest for DANVA Emotion Reader."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentEmotionTrace, EmotionRecognitionAnalysis


_UPSTREAM: tuple[str, ...] = (
    "vstack.goleman_ei",  # social_awareness weakest -> drill via DANVA
    "vstack.aar",  # AAR lessons mentioning emotion miscalibration
    "vstack.yerkes_dodson",  # workload-modulated emotion recognition
    "vstack.lewin",  # internal-locus failures with affective signal
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "anger_blind": (
        "vstack.glaser_conversation",
        "vstack.cognitive_reappraisal",
    ),
    "sadness_collapse": (
        "vstack.cognitive_reappraisal",
        "vstack.yerkes_dodson",
    ),
    "positive_bias": (
        "vstack.glaser_conversation",
        "vstack.johari",
    ),
    "negative_bias": (
        "vstack.cognitive_reappraisal",
        "vstack.lewin",
    ),
    "valence_only_signal": ("vstack.glaser_conversation",),
    "categorical_signal_only": ("vstack.yerkes_dodson",),
    "fear_sadness_confusion": ("vstack.cognitive_reappraisal",),
    "neutral_collapse": ("vstack.goleman_ei",),
    "uncertain_dump": ("vstack.johari",),
    "sarcasm_blind": (
        "vstack.glaser_conversation",
        "vstack.hexaco",
    ),
    "balanced_low": (
        "vstack.lewin",
        "vstack.aar",
    ),
}

_DOWNSTREAM_BY_WEAKEST_EMOTION: dict[str, tuple[str, ...]] = {
    "angry": ("vstack.glaser_conversation",),
    "fearful": ("vstack.cognitive_reappraisal",),
    "sad": ("vstack.cognitive_reappraisal",),
    "disgust": ("vstack.hexaco",),
    "surprise": ("vstack.lewin",),
    "happy": ("vstack.glaser_conversation",),
    "neutral": ("vstack.goleman_ei",),
    "none": ("vstack.aar",),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.lencioni", "vstack.grpi"),
    "crewai": ("vstack.lencioni", "vstack.grpi", "vstack.social_loafing"),
    "autogen": ("vstack.grpi", "vstack.social_loafing"),
    "claude-agent-sdk": ("vstack.process_gain_loss",),
    "openai-agents-sdk": ("vstack.process_gain_loss",),
    "mastra": ("vstack.grpi",),
    "strands": ("vstack.grpi",),
}

_INTERVENTION_OVERLAYS: dict[str, str] = {
    "add_cue_inventory": "vstack.glaser_conversation",
    "add_confusion_clarification": "vstack.goleman_ei",
    "add_intensity_calibration_step": "vstack.yerkes_dodson",
    "add_sarcasm_detection_step": "vstack.hexaco",
    "add_cultural_context_check": "vstack.schein_culture",
    "swap_model": "vstack.lewin",
    "human_review": "vstack.plus_delta",
    "add_constitutional_principle": "vstack.schein_culture",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    analysis: "EmotionRecognitionAnalysis",
    trace: "AgentEmotionTrace | None" = None,
) -> tuple[list[str], str]:
    """Return (downstream_pattern_list, rationale)."""
    recommendations: list[str] = []
    reasons: list[str] = []

    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(analysis.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={analysis.profile_pattern} -> {len(by_profile)} recommendations"
        )

    by_weakest = _DOWNSTREAM_BY_WEAKEST_EMOTION.get(analysis.weakest_emotion, ())
    new_weakest = [p for p in by_weakest if p not in recommendations]
    for p in new_weakest:
        recommendations.append(p)
    if new_weakest:
        reasons.append(
            f"weakest_emotion={analysis.weakest_emotion} -> +{len(new_weakest)} recommendations"
        )

    if trace is not None and trace.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.framework} -> +{len(new_fw)} recommendations")

    iv_added: list[str] = []
    for iv in analysis.interventions:
        target = _INTERVENTION_OVERLAYS.get(iv.intervention_type)
        if target and target not in recommendations:
            recommendations.append(target)
            iv_added.append(target)
    if iv_added:
        reasons.append(f"intervention overlays -> +{len(iv_added)} pattern(s)")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


DANVA_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_weakest_emotion": _DOWNSTREAM_BY_WEAKEST_EMOTION,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "DANVA_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
