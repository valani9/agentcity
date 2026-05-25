"""Cross-pattern composition manifest for the Thomas-Kilmann selector."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentInteractionTrace, ConflictStyleSelection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.glaser_conversation",
    "vstack.mcallister_trust",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_matched": ("vstack.aar",),
    "competing_when_collaborating": (
        "vstack.glaser_conversation",
        "vstack.psych_safety",
    ),
    "accommodating_when_competing": (
        "vstack.trust_triangle",
        "vstack.devils_advocate",
    ),
    "avoiding_when_collaborating": (
        "vstack.aar",
        "vstack.grpi",
    ),
    "default_compromising": (
        "vstack.aar",
        "vstack.devils_advocate",
    ),
    "rigid_single_style": (
        "vstack.aar",
        "vstack.hexaco",
    ),
    "context_blind": (
        "vstack.aar",
        "vstack.glaser_conversation",
    ),
    "mixed_inconsistent": (
        "vstack.aar",
        "vstack.lencioni",
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
