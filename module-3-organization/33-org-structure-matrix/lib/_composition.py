"""Cross-pattern composition manifest for Org-Structure Matrix."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import CrewStructureTrace, StructureAnalysis


_UPSTREAM: tuple[str, ...] = (
    "vstack.schein_culture",
    "vstack.robbins_culture",
    "vstack.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit": ("vstack.aar",),
    "too_flat_for_critical_task": (
        "vstack.span_of_control",
        "vstack.aar",
    ),
    "too_hierarchical_for_creative": (
        "vstack.span_of_control",
        "vstack.devils_advocate",
    ),
    "decision_bottleneck": (
        "vstack.span_of_control",
        "vstack.group_decision",
    ),
    "no_clear_authority": (
        "vstack.group_decision",
        "vstack.aar",
    ),
    "over_specialized": (
        "vstack.aar",
        "vstack.grpi",
    ),
    "under_specialized": (
        "vstack.grpi",
        "vstack.aar",
    ),
    "matrix_overhead": (
        "vstack.aar",
        "vstack.grpi",
    ),
    "broadly_misfit": (
        "vstack.aar",
        "vstack.schein_culture",
        "vstack.lewin",
    ),
    "indeterminate": (),
}


_DOWNSTREAM_BY_TASK_CLASS: dict[str, tuple[str, ...]] = {
    "incident_response": ("vstack.aar",),
    "regulated_workflow": ("vstack.bias_stack",),
    "code_review": ("vstack.devils_advocate",),
    "creative_brainstorm": ("vstack.debate_pathology",),
}


_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.aar",),
    "crewai": ("vstack.lencioni",),
    "autogen": ("vstack.aar",),
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
