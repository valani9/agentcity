"""Cross-pattern composition manifest for the Debate Pathology diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import DebatePathologyDetection, MultiAgentDebateTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.psych_safety",
    "agentcity.group_decision",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_debate": ("agentcity.aar",),
    "groupthink_collapse": (
        "agentcity.devils_advocate",
        "agentcity.psych_safety",
    ),
    "polarization_runaway": (
        "agentcity.bias_stack",
        "agentcity.devils_advocate",
    ),
    "contagion_dominated": (
        "agentcity.glaser_conversation",
        "agentcity.danva_emotion",
    ),
    "multi_pathology_severe": (
        "agentcity.aar",
        "agentcity.lencioni",
        "agentcity.group_decision",
    ),
    "premature_convergence": (
        "agentcity.devils_advocate",
        "agentcity.group_decision",
    ),
    "tone_overrides_content": (
        "agentcity.glaser_conversation",
        "agentcity.bias_stack",
    ),
    "dissent_suppressed": (
        "agentcity.psych_safety",
        "agentcity.devils_advocate",
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
