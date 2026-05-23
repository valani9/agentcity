"""Cross-pattern composition manifest for the McGregor diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import OrchestratorModeDetection, OrchestratorTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.schein_culture",
    "agentcity.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_matched_theory_x": ("agentcity.aar",),
    "well_matched_theory_y": ("agentcity.aar",),
    "well_matched_hybrid": ("agentcity.aar",),
    "theory_x_on_low_risk": (
        "agentcity.sdt_reward",
        "agentcity.smart_goal",
    ),
    "theory_y_on_high_risk": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
        "agentcity.hexaco",
    ),
    "theory_x_on_proven_agent": (
        "agentcity.sdt_reward",
        "agentcity.aar",
    ),
    "theory_y_on_unproven_agent": (
        "agentcity.aar",
        "agentcity.smart_goal",
    ),
    "hybrid_misapplied": (
        "agentcity.bias_stack",
        "agentcity.smart_goal",
    ),
    "regulated_workflow_under_supervision": (
        "agentcity.devils_advocate",
        "agentcity.schein_culture",
    ),
    "creative_task_over_supervised": (
        "agentcity.sdt_reward",
        "agentcity.grant_strengths",
    ),
    "irreversible_action_under_supervision": (
        "agentcity.hexaco",
        "agentcity.devils_advocate",
        "agentcity.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_OBSERVED_MODE: dict[str, tuple[str, ...]] = {
    "theory_x": ("agentcity.sdt_reward",),
    "theory_y": ("agentcity.aar",),
    "hybrid": ("agentcity.bias_stack",),
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
    "tighten_oversight": "agentcity.devils_advocate",
    "add_pre_approval_gates": "agentcity.devils_advocate",
    "elevate_to_human_on_irreversible": "agentcity.hexaco",
    "add_authorization_scope": "agentcity.hexaco",
    "rotate_to_hybrid": "agentcity.bias_stack",
    "add_step_classifier": "agentcity.bias_stack",
    "add_risk_classifier": "agentcity.bias_stack",
    "loosen_oversight": "agentcity.sdt_reward",
    "remove_pre_approval_gates": "agentcity.sdt_reward",
    "human_review": "agentcity.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "OrchestratorModeDetection",
    trace: "OrchestratorTrace | None" = None,
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

    by_obs = _DOWNSTREAM_BY_OBSERVED_MODE.get(detection.observed_mode, ())
    new_o = [p for p in by_obs if p not in recommendations]
    for p in new_o:
        recommendations.append(p)
    if new_o:
        reasons.append(f"observed_mode={detection.observed_mode} -> +{len(new_o)} recommendations")

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


MCGREGOR_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_observed_mode": _DOWNSTREAM_BY_OBSERVED_MODE,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "MCGREGOR_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
