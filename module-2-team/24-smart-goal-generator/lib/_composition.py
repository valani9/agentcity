"""Cross-pattern composition manifest for the SMART Goal Generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import GoalRequest, SMARTGoal


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.grpi",
    "vstack.aar",
    "vstack.schein_culture",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "strong_smart_goal": ("vstack.aar",),
    "vague_unspecific": (
        "vstack.devils_advocate",
        "vstack.aar",
    ),
    "unmeasurable": (
        "vstack.aar",
        "vstack.grpi",
    ),
    "unachievable_stretch": (
        "vstack.grpi",
        "vstack.lewin",
    ),
    "irrelevant_to_context": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
    ),
    "no_deadline": ("vstack.aar",),
    "missing_kill_criteria": (
        "vstack.aar",
        "vstack.devils_advocate",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.aar",),
    "crewai": ("vstack.grpi", "vstack.lencioni"),
    "autogen": ("vstack.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    goal: "SMARTGoal",
    request: "GoalRequest | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(goal.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={goal.profile_pattern} -> {len(by_profile)} recommendations"
        )
    if request is not None and request.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(request.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={request.framework} -> +{len(new_fw)} recommendations")
    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


SMART_GOAL_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "SMART_GOAL_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
