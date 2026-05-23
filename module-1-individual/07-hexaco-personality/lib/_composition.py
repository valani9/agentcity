"""Cross-pattern composition manifest for HEXACO Personality."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentPersonalityTrace, HEXACODetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.cognitive_reappraisal",
    "agentcity.goleman_ei",
    "agentcity.johari",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit_balanced": ("agentcity.aar",),
    "h_factor_dominant_risk": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
        "agentcity.lewin",
    ),
    "h_factor_with_high_a": (
        "agentcity.cognitive_reappraisal",
        "agentcity.devils_advocate",
    ),
    "low_h_with_low_c": (
        "agentcity.devils_advocate",
        "agentcity.smart_goal",
    ),
    "low_c_code_review_misfit": (
        "agentcity.smart_goal",
        "agentcity.devils_advocate",
    ),
    "low_o_creative_misfit": ("agentcity.devils_advocate",),
    "low_a_customer_facing": (
        "agentcity.goleman_ei",
        "agentcity.cognitive_reappraisal",
    ),
    "high_e_overcautious": ("agentcity.cognitive_reappraisal",),
    "low_e_undercautious_high_stakes": ("agentcity.devils_advocate",),
    "low_x_customer_facing": ("agentcity.goleman_ei",),
    "low_h_low_c_low_a_dark_triad": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
        "agentcity.lewin",
        "agentcity.schein_culture",
    ),
    "facet_imbalance_within_factor": ("agentcity.bias_stack",),
    "indeterminate": (),
}

_DOWNSTREAM_BY_WEAKEST_FACTOR: dict[str, tuple[str, ...]] = {
    "honesty_humility": ("agentcity.devils_advocate", "agentcity.bias_stack"),
    "conscientiousness": ("agentcity.smart_goal", "agentcity.devils_advocate"),
    "openness": ("agentcity.devils_advocate",),
    "agreeableness": ("agentcity.goleman_ei",),
    "emotionality": ("agentcity.cognitive_reappraisal",),
    "extraversion": ("agentcity.goleman_ei",),
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
    "add_h_factor_guardrail": "agentcity.devils_advocate",
    "add_honesty_eval": "agentcity.bias_stack",
    "add_dark_triad_eval": "agentcity.bias_stack",
    "add_red_team_probe": "agentcity.devils_advocate",
    "add_warmth_pattern": "agentcity.goleman_ei",
    "add_caution_step": "agentcity.devils_advocate",
    "add_verification_step": "agentcity.smart_goal",
    "downgrade_authority_scope": "agentcity.lewin",
    "human_review": "agentcity.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "HEXACODetection",
    trace: "AgentPersonalityTrace | None" = None,
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

    by_weak = _DOWNSTREAM_BY_WEAKEST_FACTOR.get(detection.weakest_factor, ())
    new_w = [p for p in by_weak if p not in recommendations]
    for p in new_w:
        recommendations.append(p)
    if new_w:
        reasons.append(
            f"weakest_factor={detection.weakest_factor} -> +{len(new_w)} recommendations"
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


HEXACO_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_weakest_factor": _DOWNSTREAM_BY_WEAKEST_FACTOR,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "HEXACO_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
