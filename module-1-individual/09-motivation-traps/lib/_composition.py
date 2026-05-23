"""Cross-pattern composition manifest for the 4 Motivation Traps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentMotivationTrace, MotivationDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.cognitive_reappraisal",
    "agentcity.goleman_ei",
    "agentcity.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "motivated_baseline": ("agentcity.aar",),
    "values_dominant_irrelevance": (
        "agentcity.smart_goal",
        "agentcity.schein_culture",
    ),
    "self_efficacy_collapse_uncertainty": (
        "agentcity.cognitive_reappraisal",
        "agentcity.smart_goal",
    ),
    "emotions_post_rejection_cascade": (
        "agentcity.cognitive_reappraisal",
        "agentcity.goleman_ei",
    ),
    "attribution_loop_wrong_cause": (
        "agentcity.bias_stack",
        "agentcity.johari",
    ),
    "values_plus_attribution": (
        "agentcity.smart_goal",
        "agentcity.bias_stack",
    ),
    "self_efficacy_plus_emotions": (
        "agentcity.cognitive_reappraisal",
        "agentcity.smart_goal",
    ),
    "self_efficacy_plus_attribution": (
        "agentcity.bias_stack",
        "agentcity.smart_goal",
    ),
    "high_stakes_capability_collapse": (
        "agentcity.hexaco",
        "agentcity.smart_goal",
    ),
    "creative_task_value_misfit": (
        "agentcity.grant_strengths",
        "agentcity.smart_goal",
    ),
    "multi_trap_compounded": (
        "agentcity.hexaco",
        "agentcity.cognitive_reappraisal",
        "agentcity.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_DOMINANT: dict[str, tuple[str, ...]] = {
    "values": ("agentcity.smart_goal", "agentcity.schein_culture"),
    "self_efficacy": ("agentcity.cognitive_reappraisal", "agentcity.smart_goal"),
    "emotions": ("agentcity.cognitive_reappraisal", "agentcity.goleman_ei"),
    "attribution": ("agentcity.bias_stack", "agentcity.johari"),
    "none": ("agentcity.aar",),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.grpi",),
    "crewai": ("agentcity.grpi", "agentcity.social_loafing"),
    "autogen": ("agentcity.grpi", "agentcity.social_loafing"),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
    "mastra": ("agentcity.grpi",),
    "strands": ("agentcity.grpi",),
}

_INTERVENTION_OVERLAYS: dict[str, str] = {
    "reframe_task_value": "agentcity.smart_goal",
    "ground_in_user_purpose": "agentcity.smart_goal",
    "scaffold_subtasks": "agentcity.smart_goal",
    "decompose_with_examples": "agentcity.smart_goal",
    "emotional_reset_prompt": "agentcity.cognitive_reappraisal",
    "explicit_recovery_prompt": "agentcity.cognitive_reappraisal",
    "remove_punitive_signal": "agentcity.cognitive_reappraisal",
    "reattribute_to_effort": "agentcity.bias_stack",
    "attribution_retraining_examples": "agentcity.bias_stack",
    "show_controllable_cause": "agentcity.lewin",
    "show_capability_proof": "agentcity.johari",
    "human_review": "agentcity.plus_delta",
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
