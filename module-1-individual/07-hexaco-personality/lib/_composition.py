"""Cross-pattern composition manifest for HEXACO Personality."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentPersonalityTrace, HEXACODetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.cognitive_reappraisal",
    "vstack.goleman_ei",
    "vstack.johari",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit_balanced": ("vstack.aar",),
    "h_factor_dominant_risk": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
        "vstack.lewin",
    ),
    "h_factor_with_high_a": (
        "vstack.cognitive_reappraisal",
        "vstack.devils_advocate",
    ),
    "low_h_with_low_c": (
        "vstack.devils_advocate",
        "vstack.smart_goal",
    ),
    "low_c_code_review_misfit": (
        "vstack.smart_goal",
        "vstack.devils_advocate",
    ),
    "low_o_creative_misfit": ("vstack.devils_advocate",),
    "low_a_customer_facing": (
        "vstack.goleman_ei",
        "vstack.cognitive_reappraisal",
    ),
    "high_e_overcautious": ("vstack.cognitive_reappraisal",),
    "low_e_undercautious_high_stakes": ("vstack.devils_advocate",),
    "low_x_customer_facing": ("vstack.goleman_ei",),
    "low_h_low_c_low_a_dark_triad": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
        "vstack.lewin",
        "vstack.schein_culture",
    ),
    "facet_imbalance_within_factor": ("vstack.bias_stack",),
    "indeterminate": (),
}

_DOWNSTREAM_BY_WEAKEST_FACTOR: dict[str, tuple[str, ...]] = {
    "honesty_humility": ("vstack.devils_advocate", "vstack.bias_stack"),
    "conscientiousness": ("vstack.smart_goal", "vstack.devils_advocate"),
    "openness": ("vstack.devils_advocate",),
    "agreeableness": ("vstack.goleman_ei",),
    "emotionality": ("vstack.cognitive_reappraisal",),
    "extraversion": ("vstack.goleman_ei",),
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
    "add_h_factor_guardrail": "vstack.devils_advocate",
    "add_honesty_eval": "vstack.bias_stack",
    "add_dark_triad_eval": "vstack.bias_stack",
    "add_red_team_probe": "vstack.devils_advocate",
    "add_warmth_pattern": "vstack.goleman_ei",
    "add_caution_step": "vstack.devils_advocate",
    "add_verification_step": "vstack.smart_goal",
    "downgrade_authority_scope": "vstack.lewin",
    "human_review": "vstack.plus_delta",
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
