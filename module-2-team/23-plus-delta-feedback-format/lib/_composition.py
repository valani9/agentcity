"""Cross-pattern composition manifest for Plus/Delta feedback generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import FeedbackRequest, PlusDeltaFeedback


_UPSTREAM: tuple[str, ...] = (
    "agentcity.aar",
    "agentcity.feedback_triggers",
    "agentcity.grpi",
    "agentcity.psych_safety",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "balanced_specific": ("agentcity.aar",),
    "plus_heavy_morale": (
        "agentcity.aar",
        "agentcity.feedback_triggers",
    ),
    "delta_heavy_rework": (
        "agentcity.smart_goal",
        "agentcity.grpi",
    ),
    "generic_noise": (
        "agentcity.aar",
        "agentcity.glaser_conversation",
    ),
    "no_evidence_cited": (
        "agentcity.aar",
        "agentcity.devils_advocate",
    ),
    "no_alternatives_named": (
        "agentcity.smart_goal",
        "agentcity.aar",
    ),
    "critical_findings": (
        "agentcity.aar",
        "agentcity.lencioni",
        "agentcity.smart_goal",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.aar",),
    "crewai": ("agentcity.lencioni",),
    "autogen": ("agentcity.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    feedback: "PlusDeltaFeedback",
    request: "FeedbackRequest | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(feedback.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={feedback.profile_pattern} -> {len(by_profile)} recommendations"
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


PLUS_DELTA_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "PLUS_DELTA_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
