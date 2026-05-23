"""Cross-pattern composition manifest for Grant Strengths-as-Weaknesses."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentBehaviorTrace, StrengthOveruseDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.hexaco",
    "agentcity.cognitive_reappraisal",
    "agentcity.goleman_ei",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_balanced": ("agentcity.aar",),
    "helpfulness_overuse_destructive_action": (
        "agentcity.devils_advocate",
        "agentcity.hexaco",
        "agentcity.lewin",
    ),
    "agreeableness_overuse_sycophancy": (
        "agentcity.devils_advocate",
        "agentcity.cognitive_reappraisal",
        "agentcity.bias_stack",
    ),
    "thoroughness_overuse_analysis_paralysis": (
        "agentcity.yerkes_dodson",
        "agentcity.smart_goal",
    ),
    "caution_overuse_reflexive_refusal": (
        "agentcity.cognitive_reappraisal",
        "agentcity.yerkes_dodson",
    ),
    "confidence_overuse_under_hedging": (
        "agentcity.hexaco",
        "agentcity.bias_stack",
    ),
    "brevity_overuse_missing_context": ("agentcity.smart_goal",),
    "precision_overuse_pedantic": ("agentcity.goleman_ei",),
    "paired_imbalance": (
        "agentcity.hexaco",
        "agentcity.devils_advocate",
    ),
    "multi_overuse_compounded": (
        "agentcity.hexaco",
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
    ),
    "harm_realized_dominant_overuse": (
        "agentcity.aar",
        "agentcity.lewin",
        "agentcity.devils_advocate",
    ),
    "under_used_dominant": ("agentcity.smart_goal",),
    "indeterminate": (),
}

_DOWNSTREAM_BY_DOMINANT: dict[str, tuple[str, ...]] = {
    "helpfulness": ("agentcity.devils_advocate", "agentcity.hexaco"),
    "agreeableness": ("agentcity.devils_advocate", "agentcity.cognitive_reappraisal"),
    "thoroughness": ("agentcity.yerkes_dodson", "agentcity.smart_goal"),
    "caution": ("agentcity.cognitive_reappraisal",),
    "confidence": ("agentcity.hexaco", "agentcity.bias_stack"),
    "brevity": ("agentcity.smart_goal",),
    "precision": ("agentcity.goleman_ei",),
    "none-observed": ("agentcity.aar",),
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
    "add_destructive_action_gate": "agentcity.devils_advocate",
    "tool_use_authorization_step": "agentcity.hexaco",
    "require_pushback_on_premise_check": "agentcity.devils_advocate",
    "add_sycophancy_eval": "agentcity.bias_stack",
    "uncertainty_quantification_step": "agentcity.hexaco",
    "raise_paired_complement": "agentcity.hexaco",
    "add_red_team_eval": "agentcity.devils_advocate",
    "human_review": "agentcity.plus_delta",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "StrengthOveruseDetection",
    trace: "AgentBehaviorTrace | None" = None,
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

    by_dom = _DOWNSTREAM_BY_DOMINANT.get(detection.dominant_overuse, ())
    new_d = [p for p in by_dom if p not in recommendations]
    for p in new_d:
        recommendations.append(p)
    if new_d:
        reasons.append(
            f"dominant_overuse={detection.dominant_overuse} -> +{len(new_d)} recommendations"
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


GRANT_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_dominant": _DOWNSTREAM_BY_DOMINANT,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "GRANT_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
