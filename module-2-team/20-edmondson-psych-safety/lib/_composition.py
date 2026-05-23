"""Cross-pattern composition manifest for the Edmondson Psych Safety diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import MultiAgentSafetyTrace, PsychologicalSafetyDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.grpi",
    "agentcity.lencioni",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "safe_team": ("agentcity.aar",),
    "silenced_team": (
        "agentcity.devils_advocate",
        "agentcity.lencioni",
    ),
    "cautious_team": (
        "agentcity.devils_advocate",
        "agentcity.grpi",
    ),
    "voice_absent": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
    ),
    "error_concealment": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "help_seeking_blocked": (
        "agentcity.grpi",
        "agentcity.aar",
    ),
    "siloed_no_boundary_spanning": (
        "agentcity.superflocks",
        "agentcity.grpi",
    ),
    "all_four_suppressed": (
        "agentcity.lencioni",
        "agentcity.grpi",
        "agentcity.aar",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.grpi",),
    "crewai": ("agentcity.lencioni",),
    "autogen": ("agentcity.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "PsychologicalSafetyDetection",
    trace: "MultiAgentSafetyTrace | None" = None,
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
    if trace is not None and trace.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.framework} -> +{len(new_fw)} recommendations")
    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


PSYCH_SAFETY_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "PSYCH_SAFETY_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
