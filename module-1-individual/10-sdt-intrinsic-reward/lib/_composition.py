"""Cross-pattern composition manifest for the SDT diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentSDTTrace, SDTDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.motivation_traps",
    "vstack.hexaco",
    "vstack.cognitive_reappraisal",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "intrinsic_balanced": ("vstack.aar",),
    "autonomy_undermined_dominant": (
        "vstack.schein_culture",
        "vstack.bias_stack",
    ),
    "competence_undermined_dominant": (
        "vstack.smart_goal",
        "vstack.motivation_traps",
    ),
    "relatedness_undermined_dominant": (
        "vstack.goleman_ei",
        "vstack.schein_culture",
    ),
    "overjustification_active": (
        "vstack.bias_stack",
        "vstack.schein_culture",
    ),
    "controlled_motivation_dominant": (
        "vstack.schein_culture",
        "vstack.bias_stack",
        "vstack.hexaco",
    ),
    "competence_collapse_under_deadline": (
        "vstack.yerkes_dodson",
        "vstack.smart_goal",
    ),
    "autonomy_collapse_under_rule_imposition": (
        "vstack.schein_culture",
        "vstack.mcgregor",
    ),
    "regulated_workflow_low_autonomy_acceptable": ("vstack.aar",),
    "creative_task_low_autonomy_misfit": (
        "vstack.grant_strengths",
        "vstack.devils_advocate",
    ),
    "multi_need_undermined": (
        "vstack.hexaco",
        "vstack.cognitive_reappraisal",
        "vstack.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_NEED: dict[str, tuple[str, ...]] = {
    "autonomy": ("vstack.schein_culture", "vstack.bias_stack"),
    "competence": ("vstack.smart_goal", "vstack.motivation_traps"),
    "relatedness": ("vstack.goleman_ei", "vstack.schein_culture"),
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
    "remove_external_reward_threat": "vstack.schein_culture",
    "add_choice_grant": "vstack.mcgregor",
    "soften_imperative_language": "vstack.schein_culture",
    "add_scaffold_for_competence": "vstack.smart_goal",
    "add_purpose_framing": "vstack.schein_culture",
    "add_user_connection": "vstack.goleman_ei",
    "rebalance_extrinsic_to_intrinsic": "vstack.bias_stack",
    "remove_metric_gaming_path": "vstack.bias_stack",
    "human_review": "vstack.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "SDTDetection",
    trace: "AgentSDTTrace | None" = None,
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

    by_need = _DOWNSTREAM_BY_NEED.get(detection.most_undermined_need, ())
    new_n = [p for p in by_need if p not in recommendations]
    for p in new_n:
        recommendations.append(p)
    if new_n:
        reasons.append(
            f"most_undermined_need={detection.most_undermined_need} -> "
            f"+{len(new_n)} recommendations"
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


SDT_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_need": _DOWNSTREAM_BY_NEED,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "SDT_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
