"""Cross-pattern composition manifest for Heffernan Superflocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import RoutingTrace, SuperflocksDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.grpi",
    "vstack.mcgregor",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "robust_diversified": ("vstack.aar",),
    "concentrated_routing": ("vstack.bias_stack", "vstack.mcgregor"),
    "superflocks_canonical": ("vstack.grpi", "vstack.process_gain_loss"),
    "top_agent_monopoly": ("vstack.bias_stack", "vstack.devils_advocate"),
    "no_fallback_coverage": ("vstack.aar",),
    "complementarity_collapse": ("vstack.grpi",),
    "failure_clustering_risk": ("vstack.process_gain_loss", "vstack.grpi"),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.grpi",),
    "crewai": ("vstack.grpi",),
    "autogen": ("vstack.grpi",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "SuperflocksDetection",
    trace: "RoutingTrace | None" = None,
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


SUPERFLOCKS_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "SUPERFLOCKS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
