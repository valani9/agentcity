"""Cross-pattern composition manifest for Span-of-Control diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import CrewLoadTrace, SpanLoadAnalysis


_UPSTREAM: tuple[str, ...] = (
    "agentcity.org_structure",
    "agentcity.robbins_culture",
    "agentcity.schein_culture",
    "agentcity.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_balanced": ("agentcity.aar",),
    "wide_span_orchestrator": (
        "agentcity.org_structure",
        "agentcity.group_decision",
    ),
    "deep_hierarchy": (
        "agentcity.org_structure",
        "agentcity.aar",
    ),
    "single_bottleneck": (
        "agentcity.org_structure",
        "agentcity.group_decision",
    ),
    "load_amplified_bottleneck": (
        "agentcity.org_structure",
        "agentcity.aar",
    ),
    "imbalanced_supervisors": (
        "agentcity.org_structure",
        "agentcity.social_loafing",
    ),
    "over_centralized": (
        "agentcity.group_decision",
        "agentcity.devils_advocate",
    ),
    "under_centralized": (
        "agentcity.group_decision",
        "agentcity.org_structure",
    ),
    "broadly_overloaded": (
        "agentcity.org_structure",
        "agentcity.lewin",
        "agentcity.aar",
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
    detection: "SpanLoadAnalysis",
    trace: "CrewLoadTrace | None" = None,
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
        fw = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.framework} -> +{len(new_fw)} recommendations")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


SPAN_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "SPAN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
