"""Cross-pattern composition manifest for Org-Structure Matrix."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import CrewStructureTrace, StructureAnalysis


_UPSTREAM: tuple[str, ...] = (
    "agentcity.schein_culture",
    "agentcity.robbins_culture",
    "agentcity.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit": ("agentcity.aar",),
    "too_flat_for_critical_task": (
        "agentcity.span_of_control",
        "agentcity.aar",
    ),
    "too_hierarchical_for_creative": (
        "agentcity.span_of_control",
        "agentcity.devils_advocate",
    ),
    "decision_bottleneck": (
        "agentcity.span_of_control",
        "agentcity.group_decision",
    ),
    "no_clear_authority": (
        "agentcity.group_decision",
        "agentcity.aar",
    ),
    "over_specialized": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "under_specialized": (
        "agentcity.grpi",
        "agentcity.aar",
    ),
    "matrix_overhead": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "broadly_misfit": (
        "agentcity.aar",
        "agentcity.schein_culture",
        "agentcity.lewin",
    ),
    "indeterminate": (),
}


_DOWNSTREAM_BY_TASK_CLASS: dict[str, tuple[str, ...]] = {
    "incident_response": ("agentcity.aar",),
    "regulated_workflow": ("agentcity.bias_stack",),
    "code_review": ("agentcity.devils_advocate",),
    "creative_brainstorm": ("agentcity.debate_pathology",),
}


_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.aar",),
    "crewai": ("agentcity.lencioni",),
    "autogen": ("agentcity.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "StructureAnalysis",
    trace: "CrewStructureTrace | None" = None,
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


STRUCTURE_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "downstream_by_task_class": _DOWNSTREAM_BY_TASK_CLASS,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "STRUCTURE_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
