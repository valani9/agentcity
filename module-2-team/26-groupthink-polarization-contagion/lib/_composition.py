"""Cross-pattern composition manifest for the Debate Pathology diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import DebatePathologyDetection, MultiAgentDebateTrace


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.psych_safety",
    "vstack.group_decision",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_debate": ("vstack.aar",),
    "groupthink_collapse": (
        "vstack.devils_advocate",
        "vstack.psych_safety",
    ),
    "polarization_runaway": (
        "vstack.bias_stack",
        "vstack.devils_advocate",
    ),
    "contagion_dominated": (
        "vstack.glaser_conversation",
        "vstack.danva_emotion",
    ),
    "multi_pathology_severe": (
        "vstack.aar",
        "vstack.lencioni",
        "vstack.group_decision",
    ),
    "premature_convergence": (
        "vstack.devils_advocate",
        "vstack.group_decision",
    ),
    "tone_overrides_content": (
        "vstack.glaser_conversation",
        "vstack.bias_stack",
    ),
    "dissent_suppressed": (
        "vstack.psych_safety",
        "vstack.devils_advocate",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.aar",),
    "crewai": ("vstack.lencioni",),
    "autogen": ("vstack.aar",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "DebatePathologyDetection",
    trace: "MultiAgentDebateTrace | None" = None,
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


DEBATE_PATHOLOGY_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "DEBATE_PATHOLOGY_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
