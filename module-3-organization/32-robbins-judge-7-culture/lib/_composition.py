"""Cross-pattern composition manifest for Robbins/Judge 7-Characteristics."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentCultureTrace, CultureProfileDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.schein_culture",
    "vstack.lewin",
    "vstack.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_fit": ("vstack.aar",),
    "innovation_starved": (
        "vstack.devils_advocate",
        "vstack.aar",
    ),
    "detail_starved": (
        "vstack.aar",
        "vstack.bias_stack",
    ),
    "innovation_excess": (
        "vstack.aar",
        "vstack.devils_advocate",
    ),
    "stability_excess": (
        "vstack.aar",
        "vstack.lewin",
    ),
    "team_excess": (
        "vstack.lencioni",
        "vstack.psych_safety",
    ),
    "team_starved": (
        "vstack.lencioni",
        "vstack.trust_triangle",
    ),
    "aggressiveness_excess": (
        "vstack.psych_safety",
        "vstack.glaser_conversation",
    ),
    "people_starved": (
        "vstack.glaser_conversation",
        "vstack.feedback_triggers",
    ),
    "outcome_starved": (
        "vstack.smart_goal",
        "vstack.aar",
    ),
    "broadly_misfit": (
        "vstack.schein_culture",
        "vstack.aar",
        "vstack.lewin",
    ),
    "indeterminate": (),
}


_DOWNSTREAM_BY_TASK_CLASS: dict[str, tuple[str, ...]] = {
    "regulated_workflow": ("vstack.bias_stack",),
    "financial_operation": ("vstack.bias_stack",),
    "incident_response": ("vstack.aar",),
    "code_review": ("vstack.devils_advocate",),
}


_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.aar",),
    "crewai": ("vstack.lencioni",),
    "autogen": ("vstack.aar",),
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
