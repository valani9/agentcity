"""Cross-pattern composition manifest for the 4 Motivation Traps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentMotivationTrace, MotivationDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.cognitive_reappraisal",
    "vstack.goleman_ei",
    "vstack.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "motivated_baseline": ("vstack.aar",),
    "values_dominant_irrelevance": (
        "vstack.smart_goal",
        "vstack.schein_culture",
    ),
    "self_efficacy_collapse_uncertainty": (
        "vstack.cognitive_reappraisal",
        "vstack.smart_goal",
    ),
    "emotions_post_rejection_cascade": (
        "vstack.cognitive_reappraisal",
        "vstack.goleman_ei",
    ),
    "attribution_loop_wrong_cause": (
        "vstack.bias_stack",
        "vstack.johari",
    ),
    "values_plus_attribution": (
        "vstack.smart_goal",
        "vstack.bias_stack",
    ),
    "self_efficacy_plus_emotions": (
        "vstack.cognitive_reappraisal",
        "vstack.smart_goal",
    ),
    "self_efficacy_plus_attribution": (
        "vstack.bias_stack",
        "vstack.smart_goal",
    ),
    "high_stakes_capability_collapse": (
        "vstack.hexaco",
        "vstack.smart_goal",
    ),
    "creative_task_value_misfit": (
        "vstack.grant_strengths",
        "vstack.smart_goal",
    ),
    "multi_trap_compounded": (
        "vstack.hexaco",
        "vstack.cognitive_reappraisal",
        "vstack.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_DOMINANT: dict[str, tuple[str, ...]] = {
    "values": ("vstack.smart_goal", "vstack.schein_culture"),
    "self_efficacy": ("vstack.cognitive_reappraisal", "vstack.smart_goal"),
    "emotions": ("vstack.cognitive_reappraisal", "vstack.goleman_ei"),
    "attribution": ("vstack.bias_stack", "vstack.johari"),
    "none": ("vstack.aar",),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.grpi",),
    "crewai": ("vstack.grpi", "vstack.social_loafing"),
    "autogen": ("vstack.grpi", "vstack.social_loafing"),
    "claude-agent-sdk": ("vstack.process_gain_loss",),
    "openai-agents-sdk": ("vstack.process_gain_loss",),
    "mastra": ("vstack.grpi",),
    "strands": ("vstack.grpi",),
}

_INTERVENTION_OVERLAYS: dict[str, str] = {
    "reframe_task_value": "vstack.smart_goal",
    "ground_in_user_purpose": "vstack.smart_goal",
    "scaffold_subtasks": "vstack.smart_goal",
    "decompose_with_examples": "vstack.smart_goal",
    "emotional_reset_prompt": "vstack.cognitive_reappraisal",
    "explicit_recovery_prompt": "vstack.cognitive_reappraisal",
    "remove_punitive_signal": "vstack.cognitive_reappraisal",
    "reattribute_to_effort": "vstack.bias_stack",
    "attribution_retraining_examples": "vstack.bias_stack",
    "show_controllable_cause": "vstack.lewin",
    "show_capability_proof": "vstack.johari",
    "human_review": "vstack.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "MotivationDetection",
    trace: "AgentMotivationTrace | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []

    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(detection.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={detection.profile_pattern} -> {len(by_profile)} recommendations"
        )

    by_dom = _DOWNSTREAM_BY_DOMINANT.get(detection.dominant_trap, ())
    new_d = [p for p in by_dom if p not in recommendations]
    for p in new_d:
        recommendations.append(p)
    if new_d:
        reasons.append(f"dominant_trap={detection.dominant_trap} -> +{len(new_d)} recommendations")

    if trace is not None and trace.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.framework} -> +{len(new_fw)} recommendations")

    iv_added: list[str] = []
    for iv in detection.interventions:
        target = _INTERVENTION_OVERLAYS.get(iv.intervention_type)
        if target and target not in recommendations:
            recommendations.append(target)
            iv_added.append(target)
    if iv_added:
        reasons.append(f"intervention overlays -> +{len(iv_added)} pattern(s)")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


MOTIVATION_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_dominant": _DOWNSTREAM_BY_DOMINANT,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "MOTIVATION_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
