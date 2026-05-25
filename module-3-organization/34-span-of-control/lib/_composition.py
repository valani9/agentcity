"""Cross-pattern composition manifest for Span-of-Control diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import CrewLoadTrace, SpanLoadAnalysis


_UPSTREAM: tuple[str, ...] = (
    "vstack.org_structure",
    "vstack.robbins_culture",
    "vstack.schein_culture",
    "vstack.aar",
)


_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_balanced": ("vstack.aar",),
    "wide_span_orchestrator": (
        "vstack.org_structure",
        "vstack.group_decision",
    ),
    "deep_hierarchy": (
        "vstack.org_structure",
        "vstack.aar",
    ),
    "single_bottleneck": (
        "vstack.org_structure",
        "vstack.group_decision",
    ),
    "load_amplified_bottleneck": (
        "vstack.org_structure",
        "vstack.aar",
    ),
    "imbalanced_supervisors": (
        "vstack.org_structure",
        "vstack.social_loafing",
    ),
    "over_centralized": (
        "vstack.group_decision",
        "vstack.devils_advocate",
    ),
    "under_centralized": (
        "vstack.group_decision",
        "vstack.org_structure",
    ),
    "broadly_overloaded": (
        "vstack.org_structure",
        "vstack.lewin",
        "vstack.aar",
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
