"""Cross-pattern composition manifest for the Edmondson Psych Safety diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import MultiAgentSafetyTrace, PsychologicalSafetyDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.grpi",
    "vstack.lencioni",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "safe_team": ("vstack.aar",),
    "silenced_team": (
        "vstack.devils_advocate",
        "vstack.lencioni",
    ),
    "cautious_team": (
        "vstack.devils_advocate",
        "vstack.grpi",
    ),
    "voice_absent": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
    ),
    "error_concealment": (
        "vstack.aar",
        "vstack.grpi",
    ),
    "help_seeking_blocked": (
        "vstack.grpi",
        "vstack.aar",
    ),
    "siloed_no_boundary_spanning": (
        "vstack.superflocks",
        "vstack.grpi",
    ),
    "all_four_suppressed": (
        "vstack.lencioni",
        "vstack.grpi",
        "vstack.aar",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.grpi",),
    "crewai": ("vstack.lencioni",),
    "autogen": ("vstack.aar",),
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
