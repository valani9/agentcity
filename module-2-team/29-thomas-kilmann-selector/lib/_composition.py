"""Cross-pattern composition manifest for the Thomas-Kilmann selector."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentInteractionTrace, ConflictStyleSelection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.glaser_conversation",
    "agentcity.mcallister_trust",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_matched": ("agentcity.aar",),
    "competing_when_collaborating": (
        "agentcity.glaser_conversation",
        "agentcity.psych_safety",
    ),
    "accommodating_when_competing": (
        "agentcity.trust_triangle",
        "agentcity.devils_advocate",
    ),
    "avoiding_when_collaborating": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "default_compromising": (
        "agentcity.aar",
        "agentcity.devils_advocate",
    ),
    "rigid_single_style": (
        "agentcity.aar",
        "agentcity.hexaco",
    ),
    "context_blind": (
        "agentcity.aar",
        "agentcity.glaser_conversation",
    ),
    "mixed_inconsistent": (
        "agentcity.aar",
        "agentcity.lencioni",
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
    selection: "ConflictStyleSelection",
    trace: "AgentInteractionTrace | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(selection.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={selection.profile_pattern} -> {len(by_profile)} recommendations"
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


THOMAS_KILMANN_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "THOMAS_KILMANN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
