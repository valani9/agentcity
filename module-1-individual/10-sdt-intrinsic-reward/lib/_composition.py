"""Cross-pattern composition manifest for the SDT diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentSDTTrace, SDTDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.motivation_traps",
    "agentcity.hexaco",
    "agentcity.cognitive_reappraisal",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "intrinsic_balanced": ("agentcity.aar",),
    "autonomy_undermined_dominant": (
        "agentcity.schein_culture",
        "agentcity.bias_stack",
    ),
    "competence_undermined_dominant": (
        "agentcity.smart_goal",
        "agentcity.motivation_traps",
    ),
    "relatedness_undermined_dominant": (
        "agentcity.goleman_ei",
        "agentcity.schein_culture",
    ),
    "overjustification_active": (
        "agentcity.bias_stack",
        "agentcity.schein_culture",
    ),
    "controlled_motivation_dominant": (
        "agentcity.schein_culture",
        "agentcity.bias_stack",
        "agentcity.hexaco",
    ),
    "competence_collapse_under_deadline": (
        "agentcity.yerkes_dodson",
        "agentcity.smart_goal",
    ),
    "autonomy_collapse_under_rule_imposition": (
        "agentcity.schein_culture",
        "agentcity.mcgregor",
    ),
    "regulated_workflow_low_autonomy_acceptable": ("agentcity.aar",),
    "creative_task_low_autonomy_misfit": (
        "agentcity.grant_strengths",
        "agentcity.devils_advocate",
    ),
    "multi_need_undermined": (
        "agentcity.hexaco",
        "agentcity.cognitive_reappraisal",
        "agentcity.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_NEED: dict[str, tuple[str, ...]] = {
    "autonomy": ("agentcity.schein_culture", "agentcity.bias_stack"),
    "competence": ("agentcity.smart_goal", "agentcity.motivation_traps"),
    "relatedness": ("agentcity.goleman_ei", "agentcity.schein_culture"),
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
    "remove_external_reward_threat": "agentcity.schein_culture",
    "add_choice_grant": "agentcity.mcgregor",
    "soften_imperative_language": "agentcity.schein_culture",
    "add_scaffold_for_competence": "agentcity.smart_goal",
    "add_purpose_framing": "agentcity.schein_culture",
    "add_user_connection": "agentcity.goleman_ei",
    "rebalance_extrinsic_to_intrinsic": "agentcity.bias_stack",
    "remove_metric_gaming_path": "agentcity.bias_stack",
    "human_review": "agentcity.plus_delta",
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
