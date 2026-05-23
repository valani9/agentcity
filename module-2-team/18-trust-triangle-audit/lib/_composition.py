"""Cross-pattern composition manifest for the Trust Triangle Audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentInteractionTrace, TrustTriangleAudit


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.lencioni",
    "agentcity.mcallister_trust",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_trust": ("agentcity.aar",),
    "logic_wobble_dominant": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
    ),
    "authenticity_wobble_dominant": (
        "agentcity.psych_safety",
        "agentcity.devils_advocate",
    ),
    "empathy_wobble_dominant": (
        "agentcity.glaser_conversation",
        "agentcity.mcallister_trust",
    ),
    "full_triangle_collapse": (
        "agentcity.lencioni",
        "agentcity.psych_safety",
        "agentcity.aar",
    ),
    "logic_authenticity_paired": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
        "agentcity.psych_safety",
    ),
    "empathy_isolated_wobble": ("agentcity.glaser_conversation",),
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
