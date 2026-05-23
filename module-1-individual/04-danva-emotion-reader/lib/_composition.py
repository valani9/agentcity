"""Cross-pattern composition manifest for DANVA Emotion Reader."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentEmotionTrace, EmotionRecognitionAnalysis


_UPSTREAM: tuple[str, ...] = (
    "agentcity.goleman_ei",  # social_awareness weakest -> drill via DANVA
    "agentcity.aar",  # AAR lessons mentioning emotion miscalibration
    "agentcity.yerkes_dodson",  # workload-modulated emotion recognition
    "agentcity.lewin",  # internal-locus failures with affective signal
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "anger_blind": (
        "agentcity.glaser_conversation",
        "agentcity.cognitive_reappraisal",
    ),
    "sadness_collapse": (
        "agentcity.cognitive_reappraisal",
        "agentcity.yerkes_dodson",
    ),
    "positive_bias": (
        "agentcity.glaser_conversation",
        "agentcity.johari",
    ),
    "negative_bias": (
        "agentcity.cognitive_reappraisal",
        "agentcity.lewin",
    ),
    "valence_only_signal": ("agentcity.glaser_conversation",),
    "categorical_signal_only": ("agentcity.yerkes_dodson",),
    "fear_sadness_confusion": ("agentcity.cognitive_reappraisal",),
    "neutral_collapse": ("agentcity.goleman_ei",),
    "uncertain_dump": ("agentcity.johari",),
    "sarcasm_blind": (
        "agentcity.glaser_conversation",
        "agentcity.hexaco",
    ),
    "balanced_low": (
        "agentcity.lewin",
        "agentcity.aar",
    ),
}

_DOWNSTREAM_BY_WEAKEST_EMOTION: dict[str, tuple[str, ...]] = {
    "angry": ("agentcity.glaser_conversation",),
    "fearful": ("agentcity.cognitive_reappraisal",),
    "sad": ("agentcity.cognitive_reappraisal",),
    "disgust": ("agentcity.hexaco",),
    "surprise": ("agentcity.lewin",),
    "happy": ("agentcity.glaser_conversation",),
    "neutral": ("agentcity.goleman_ei",),
    "none": ("agentcity.aar",),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.lencioni", "agentcity.grpi"),
    "crewai": ("agentcity.lencioni", "agentcity.grpi", "agentcity.social_loafing"),
    "autogen": ("agentcity.grpi", "agentcity.social_loafing"),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
    "mastra": ("agentcity.grpi",),
    "strands": ("agentcity.grpi",),
}

_INTERVENTION_OVERLAYS: dict[str, str] = {
    "add_cue_inventory": "agentcity.glaser_conversation",
    "add_confusion_clarification": "agentcity.goleman_ei",
    "add_intensity_calibration_step": "agentcity.yerkes_dodson",
    "add_sarcasm_detection_step": "agentcity.hexaco",
    "add_cultural_context_check": "agentcity.schein_culture",
    "swap_model": "agentcity.lewin",
    "human_review": "agentcity.plus_delta",
    "add_constitutional_principle": "agentcity.schein_culture",
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
