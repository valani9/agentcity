"""Cross-pattern composition manifest for the Vroom diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentExpectancyTrace, VroomDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.sdt_reward",
    "agentcity.motivation_traps",
    "agentcity.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "motivated_balanced": ("agentcity.aar",),
    "expectancy_bottleneck": (
        "agentcity.smart_goal",
        "agentcity.motivation_traps",
    ),
    "instrumentality_bottleneck": (
        "agentcity.sdt_reward",
        "agentcity.smart_goal",
    ),
    "valence_bottleneck": (
        "agentcity.hexaco",
        "agentcity.schein_culture",
    ),
    "valence_negative_active_avoidance": (
        "agentcity.hexaco",
        "agentcity.cognitive_reappraisal",
        "agentcity.bias_stack",
    ),
    "multi_term_collapse": (
        "agentcity.hexaco",
        "agentcity.cognitive_reappraisal",
        "agentcity.lewin",
    ),
    "high_E_high_I_low_V_misaligned_task": (
        "agentcity.hexaco",
        "agentcity.schein_culture",
    ),
    "high_E_low_I_pointless_work": (
        "agentcity.sdt_reward",
        "agentcity.smart_goal",
    ),
    "low_E_creative_task_misfit": (
        "agentcity.grant_strengths",
        "agentcity.smart_goal",
    ),
    "low_E_tool_use_capability_gap": (
        "agentcity.hexaco",
        "agentcity.smart_goal",
    ),
    "balanced_but_weak": ("agentcity.smart_goal",),
    "indeterminate": (),
}

_DOWNSTREAM_BY_BOTTLENECK: dict[str, tuple[str, ...]] = {
    "expectancy": ("agentcity.smart_goal", "agentcity.motivation_traps"),
    "instrumentality": ("agentcity.sdt_reward", "agentcity.smart_goal"),
    "valence": ("agentcity.hexaco", "agentcity.schein_culture"),
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
    "scaffold_subtasks": "agentcity.smart_goal",
    "tighten_goal_specificity": "agentcity.smart_goal",
    "add_worked_example": "agentcity.smart_goal",
    "show_capability_proof": "agentcity.johari",
    "show_output_consumer": "agentcity.sdt_reward",
    "add_outcome_link": "agentcity.smart_goal",
    "add_progress_signal": "agentcity.smart_goal",
    "remove_pointless_signal": "agentcity.sdt_reward",
    "add_purpose_framing": "agentcity.schein_culture",
    "rebalance_value_alignment": "agentcity.hexaco",
    "remove_anti_value_signal": "agentcity.hexaco",
    "human_review": "agentcity.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "VroomDetection",
    trace: "AgentExpectancyTrace | None" = None,
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

    by_bn = _DOWNSTREAM_BY_BOTTLENECK.get(detection.bottleneck_term, ())
    new_b = [p for p in by_bn if p not in recommendations]
    for p in new_b:
        recommendations.append(p)
    if new_b:
        reasons.append(
            f"bottleneck_term={detection.bottleneck_term} -> +{len(new_b)} recommendations"
        )

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


VROOM_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_bottleneck": _DOWNSTREAM_BY_BOTTLENECK,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "VROOM_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
