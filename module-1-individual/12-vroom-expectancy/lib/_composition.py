"""Cross-pattern composition manifest for the Vroom diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentExpectancyTrace, VroomDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.sdt_reward",
    "vstack.motivation_traps",
    "vstack.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "motivated_balanced": ("vstack.aar",),
    "expectancy_bottleneck": (
        "vstack.smart_goal",
        "vstack.motivation_traps",
    ),
    "instrumentality_bottleneck": (
        "vstack.sdt_reward",
        "vstack.smart_goal",
    ),
    "valence_bottleneck": (
        "vstack.hexaco",
        "vstack.schein_culture",
    ),
    "valence_negative_active_avoidance": (
        "vstack.hexaco",
        "vstack.cognitive_reappraisal",
        "vstack.bias_stack",
    ),
    "multi_term_collapse": (
        "vstack.hexaco",
        "vstack.cognitive_reappraisal",
        "vstack.lewin",
    ),
    "high_E_high_I_low_V_misaligned_task": (
        "vstack.hexaco",
        "vstack.schein_culture",
    ),
    "high_E_low_I_pointless_work": (
        "vstack.sdt_reward",
        "vstack.smart_goal",
    ),
    "low_E_creative_task_misfit": (
        "vstack.grant_strengths",
        "vstack.smart_goal",
    ),
    "low_E_tool_use_capability_gap": (
        "vstack.hexaco",
        "vstack.smart_goal",
    ),
    "balanced_but_weak": ("vstack.smart_goal",),
    "indeterminate": (),
}

_DOWNSTREAM_BY_BOTTLENECK: dict[str, tuple[str, ...]] = {
    "expectancy": ("vstack.smart_goal", "vstack.motivation_traps"),
    "instrumentality": ("vstack.sdt_reward", "vstack.smart_goal"),
    "valence": ("vstack.hexaco", "vstack.schein_culture"),
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
    "scaffold_subtasks": "vstack.smart_goal",
    "tighten_goal_specificity": "vstack.smart_goal",
    "add_worked_example": "vstack.smart_goal",
    "show_capability_proof": "vstack.johari",
    "show_output_consumer": "vstack.sdt_reward",
    "add_outcome_link": "vstack.smart_goal",
    "add_progress_signal": "vstack.smart_goal",
    "remove_pointless_signal": "vstack.sdt_reward",
    "add_purpose_framing": "vstack.schein_culture",
    "rebalance_value_alignment": "vstack.hexaco",
    "remove_anti_value_signal": "vstack.hexaco",
    "human_review": "vstack.plus_delta",
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
