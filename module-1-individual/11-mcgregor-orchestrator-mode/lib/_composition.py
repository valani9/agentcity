"""Cross-pattern composition manifest for the McGregor diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import OrchestratorModeDetection, OrchestratorTrace


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.schein_culture",
    "vstack.hexaco",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_matched_theory_x": ("vstack.aar",),
    "well_matched_theory_y": ("vstack.aar",),
    "well_matched_hybrid": ("vstack.aar",),
    "theory_x_on_low_risk": (
        "vstack.sdt_reward",
        "vstack.smart_goal",
    ),
    "theory_y_on_high_risk": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
        "vstack.hexaco",
    ),
    "theory_x_on_proven_agent": (
        "vstack.sdt_reward",
        "vstack.aar",
    ),
    "theory_y_on_unproven_agent": (
        "vstack.aar",
        "vstack.smart_goal",
    ),
    "hybrid_misapplied": (
        "vstack.bias_stack",
        "vstack.smart_goal",
    ),
    "regulated_workflow_under_supervision": (
        "vstack.devils_advocate",
        "vstack.schein_culture",
    ),
    "creative_task_over_supervised": (
        "vstack.sdt_reward",
        "vstack.grant_strengths",
    ),
    "irreversible_action_under_supervision": (
        "vstack.hexaco",
        "vstack.devils_advocate",
        "vstack.lewin",
    ),
    "indeterminate": (),
}

_DOWNSTREAM_BY_OBSERVED_MODE: dict[str, tuple[str, ...]] = {
    "theory_x": ("vstack.sdt_reward",),
    "theory_y": ("vstack.aar",),
    "hybrid": ("vstack.bias_stack",),
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
    "tighten_oversight": "vstack.devils_advocate",
    "add_pre_approval_gates": "vstack.devils_advocate",
    "elevate_to_human_on_irreversible": "vstack.hexaco",
    "add_authorization_scope": "vstack.hexaco",
    "rotate_to_hybrid": "vstack.bias_stack",
    "add_step_classifier": "vstack.bias_stack",
    "add_risk_classifier": "vstack.bias_stack",
    "loosen_oversight": "vstack.sdt_reward",
    "remove_pre_approval_gates": "vstack.sdt_reward",
    "human_review": "vstack.plus_delta",
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
