"""Cross-pattern composition manifest for Yerkes-Dodson Workload."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentPerformanceTrace, WorkloadDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.cognitive_reappraisal",
    "vstack.goleman_ei",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "under_pressure_wandering": ("vstack.smart_goal", "vstack.mcgregor"),
    "under_pressure_drift": ("vstack.smart_goal", "vstack.aar"),
    "over_pressure_corner_cutting": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
    ),
    "over_pressure_hallucinating": (
        "vstack.johari",
        "vstack.lewin",
    ),
    "over_pressure_freezing": (
        "vstack.cognitive_reappraisal",
        "vstack.mcgregor",
    ),
    "over_pressure_refusing": (
        "vstack.cognitive_reappraisal",
        "vstack.grant_strengths",
    ),
    "context_saturation": ("vstack.lewin",),
    "extraneous_load_overload": ("vstack.schein_culture",),
    "intrinsic_load_overload": ("vstack.smart_goal",),
    "optimal_zone": ("vstack.aar",),
}

_DOWNSTREAM_BY_ZONE: dict[str, tuple[str, ...]] = {
    "under_pressure": ("vstack.smart_goal", "vstack.mcgregor"),
    "over_pressure": ("vstack.cognitive_reappraisal", "vstack.devils_advocate"),
    "optimal": ("vstack.aar",),
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
    "chunk_context": "vstack.lewin",
    "context_compression": "vstack.lewin",
    "add_scaffolding": "vstack.smart_goal",
    "explicit_focus_prompt": "vstack.smart_goal",
    "human_review": "vstack.plus_delta",
    "add_kill_criterion": "vstack.devils_advocate",
    "reduce_extraneous_load": "vstack.schein_culture",
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
