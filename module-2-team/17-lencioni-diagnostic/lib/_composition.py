"""Cross-pattern composition manifest for Lencioni."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import LencioniDiagnosis, MultiAgentTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.grpi",
    "agentcity.schein_culture",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "healthy_team": ("agentcity.aar",),
    "foundational_trust_collapse": (
        "agentcity.edmondson_psych_safety",
        "agentcity.trust_triangle",
    ),
    "conflict_avoidance": ("agentcity.devils_advocate", "agentcity.bias_stack"),
    "commitment_collapse": ("agentcity.smart_goal", "agentcity.grpi"),
    "accountability_void": ("agentcity.plus_delta", "agentcity.grpi"),
    "results_inattention": ("agentcity.aar", "agentcity.smart_goal"),
    "full_pyramid_dysfunction": (
        "agentcity.grpi",
        "agentcity.edmondson_psych_safety",
        "agentcity.lewin",
    ),
    "foundation_unstable_top_strong": ("agentcity.trust_triangle",),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.grpi",),
    "crewai": ("agentcity.grpi", "agentcity.social_loafing"),
    "autogen": ("agentcity.grpi",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    diagnosis: "LencioniDiagnosis",
    trace: "MultiAgentTrace | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(diagnosis.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={diagnosis.profile_pattern} -> {len(by_profile)} recommendations"
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


LENCIONI_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "LENCIONI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
