"""Cross-pattern composition manifest for the Trust Triangle Audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentInteractionTrace, TrustTriangleAudit


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.lencioni",
    "vstack.mcallister_trust",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_trust": ("vstack.aar",),
    "logic_wobble_dominant": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
    ),
    "authenticity_wobble_dominant": (
        "vstack.psych_safety",
        "vstack.devils_advocate",
    ),
    "empathy_wobble_dominant": (
        "vstack.glaser_conversation",
        "vstack.mcallister_trust",
    ),
    "full_triangle_collapse": (
        "vstack.lencioni",
        "vstack.psych_safety",
        "vstack.aar",
    ),
    "logic_authenticity_paired": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
        "vstack.psych_safety",
    ),
    "empathy_isolated_wobble": ("vstack.glaser_conversation",),
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
    audit: "TrustTriangleAudit",
    trace: "AgentInteractionTrace | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(audit.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={audit.profile_pattern} -> {len(by_profile)} recommendations"
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


TRUST_TRIANGLE_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "TRUST_TRIANGLE_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
