"""Cross-pattern composition manifest for Yerkes-Dodson Workload."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentPerformanceTrace, WorkloadDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.cognitive_reappraisal",
    "agentcity.goleman_ei",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "under_pressure_wandering": ("agentcity.smart_goal", "agentcity.mcgregor"),
    "under_pressure_drift": ("agentcity.smart_goal", "agentcity.aar"),
    "over_pressure_corner_cutting": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
    ),
    "over_pressure_hallucinating": (
        "agentcity.johari",
        "agentcity.lewin",
    ),
    "over_pressure_freezing": (
        "agentcity.cognitive_reappraisal",
        "agentcity.mcgregor",
    ),
    "over_pressure_refusing": (
        "agentcity.cognitive_reappraisal",
        "agentcity.grant_strengths",
    ),
    "context_saturation": ("agentcity.lewin",),
    "extraneous_load_overload": ("agentcity.schein_culture",),
    "intrinsic_load_overload": ("agentcity.smart_goal",),
    "optimal_zone": ("agentcity.aar",),
}

_DOWNSTREAM_BY_ZONE: dict[str, tuple[str, ...]] = {
    "under_pressure": ("agentcity.smart_goal", "agentcity.mcgregor"),
    "over_pressure": ("agentcity.cognitive_reappraisal", "agentcity.devils_advocate"),
    "optimal": ("agentcity.aar",),
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
    "chunk_context": "agentcity.lewin",
    "context_compression": "agentcity.lewin",
    "add_scaffolding": "agentcity.smart_goal",
    "explicit_focus_prompt": "agentcity.smart_goal",
    "human_review": "agentcity.plus_delta",
    "add_kill_criterion": "agentcity.devils_advocate",
    "reduce_extraneous_load": "agentcity.schein_culture",
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "WorkloadDetection",
    trace: "AgentPerformanceTrace | None" = None,
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

    by_zone = _DOWNSTREAM_BY_ZONE.get(detection.observed_zone, ())
    new_zone = [p for p in by_zone if p not in recommendations]
    for p in new_zone:
        recommendations.append(p)
    if new_zone:
        reasons.append(
            f"observed_zone={detection.observed_zone} -> +{len(new_zone)} recommendations"
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


YERKES_DODSON_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_zone": _DOWNSTREAM_BY_ZONE,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "YERKES_DODSON_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
