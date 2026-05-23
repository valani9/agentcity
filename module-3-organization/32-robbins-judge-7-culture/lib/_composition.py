"""Cross-pattern composition manifest for Robbins/Judge 7-Characteristics."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentCultureTrace, CultureProfileDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.schein_culture",
    "agentcity.lewin",
    "agentcity.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit": ("agentcity.aar",),
    "innovation_starved": (
        "agentcity.devils_advocate",
        "agentcity.aar",
    ),
    "detail_starved": (
        "agentcity.aar",
        "agentcity.bias_stack",
    ),
    "innovation_excess": (
        "agentcity.aar",
        "agentcity.devils_advocate",
    ),
    "stability_excess": (
        "agentcity.aar",
        "agentcity.lewin",
    ),
    "team_excess": (
        "agentcity.lencioni",
        "agentcity.psych_safety",
    ),
    "team_starved": (
        "agentcity.lencioni",
        "agentcity.trust_triangle",
    ),
    "aggressiveness_excess": (
        "agentcity.psych_safety",
        "agentcity.glaser_conversation",
    ),
    "people_starved": (
        "agentcity.glaser_conversation",
        "agentcity.feedback_triggers",
    ),
    "outcome_starved": (
        "agentcity.smart_goal",
        "agentcity.aar",
    ),
    "broadly_misfit": (
        "agentcity.schein_culture",
        "agentcity.aar",
        "agentcity.lewin",
    ),
    "indeterminate": (),
}


_DOWNSTREAM_BY_TASK_CLASS: dict[str, tuple[str, ...]] = {
    "regulated_workflow": ("agentcity.bias_stack",),
    "financial_operation": ("agentcity.bias_stack",),
    "incident_response": ("agentcity.aar",),
    "code_review": ("agentcity.devils_advocate",),
}


_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.aar",),
    "crewai": ("agentcity.lencioni",),
    "autogen": ("agentcity.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "CultureProfileDetection",
    trace: "AgentCultureTrace | None" = None,
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

    by_task = _DOWNSTREAM_BY_TASK_CLASS.get(detection.task_class, ())
    new_task = [p for p in by_task if p not in recommendations]
    for p in new_task:
        recommendations.append(p)
    if new_task:
        reasons.append(f"task_class={detection.task_class} -> +{len(new_task)} recommendations")

    if trace is not None and trace.framework:
        fw = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.framework} -> +{len(new_fw)} recommendations")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


ROBBINS_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_task_class": _DOWNSTREAM_BY_TASK_CLASS,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "ROBBINS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
