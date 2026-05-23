"""Cross-pattern composition manifest for Cognitive Reappraisal."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentRegulationTrace, RegulationDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.goleman_ei",
    "agentcity.johari",
    "agentcity.danva_emotion",
    "agentcity.aar",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "suppression_dominant": (
        "agentcity.glaser_conversation",
        "agentcity.devils_advocate",
    ),
    "suppression_under_pushback": (
        "agentcity.devils_advocate",
        "agentcity.schein_culture",
    ),
    "rumination_loop": ("agentcity.yerkes_dodson",),
    "rumination_brooding": (
        "agentcity.yerkes_dodson",
        "agentcity.bias_stack",
    ),
    "rumination_reflective": ("agentcity.aar",),
    "avoidance_pivot": (
        "agentcity.glaser_conversation",
        "agentcity.goleman_ei",
    ),
    "expression_only": ("agentcity.hexaco",),
    "reappraisal_developing": ("agentcity.aar",),
    "mixed_unstable": (
        "agentcity.lewin",
        "agentcity.aar",
    ),
    "no_regulation": ("agentcity.danva_emotion",),
}

_DOWNSTREAM_BY_DOMINANT_STRATEGY: dict[str, tuple[str, ...]] = {
    "suppression": ("agentcity.devils_advocate", "agentcity.glaser_conversation"),
    "rumination": ("agentcity.yerkes_dodson",),
    "avoidance": ("agentcity.glaser_conversation",),
    "expression": ("agentcity.hexaco",),
    "reappraisal": ("agentcity.aar",),
    "none": ("agentcity.danva_emotion",),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.lencioni", "agentcity.grpi"),
    "crewai": ("agentcity.lencioni", "agentcity.grpi", "agentcity.social_loafing"),
    "autogen": ("agentcity.grpi", "agentcity.social_loafing"),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
    "mastra": ("agentcity.grpi",),
    "strands": ("agentcity.grpi",),
}

_INTERVENTION_OVERLAYS: dict[str, str] = {
    "remove_suppression_pattern": "agentcity.glaser_conversation",
    "break_rumination_loop": "agentcity.yerkes_dodson",
    "disengage_avoidance_pivot": "agentcity.glaser_conversation",
    "add_anti_sycophancy_anchor": "agentcity.devils_advocate",
    "swap_model": "agentcity.lewin",
    "human_review": "agentcity.plus_delta",
    "add_constitutional_principle": "agentcity.schein_culture",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "RegulationDetection",
    trace: "AgentRegulationTrace | None" = None,
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

    by_strategy = _DOWNSTREAM_BY_DOMINANT_STRATEGY.get(detection.dominant_strategy, ())
    new_strategy = [p for p in by_strategy if p not in recommendations]
    for p in new_strategy:
        recommendations.append(p)
    if new_strategy:
        reasons.append(
            f"dominant_strategy={detection.dominant_strategy} -> "
            f"+{len(new_strategy)} recommendations"
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


REAPPRAISAL_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_dominant_strategy": _DOWNSTREAM_BY_DOMINANT_STRATEGY,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "REAPPRAISAL_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
