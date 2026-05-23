"""Cross-pattern composition manifest for the SMART Goal Generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import GoalRequest, SMARTGoal


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.grpi",
    "agentcity.aar",
    "agentcity.schein_culture",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "strong_smart_goal": ("agentcity.aar",),
    "vague_unspecific": (
        "agentcity.devils_advocate",
        "agentcity.aar",
    ),
    "unmeasurable": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "unachievable_stretch": (
        "agentcity.grpi",
        "agentcity.lewin",
    ),
    "irrelevant_to_context": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
    ),
    "no_deadline": ("agentcity.aar",),
    "missing_kill_criteria": (
        "agentcity.aar",
        "agentcity.devils_advocate",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.aar",),
    "crewai": ("agentcity.grpi", "agentcity.lencioni"),
    "autogen": ("agentcity.aar",),
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
