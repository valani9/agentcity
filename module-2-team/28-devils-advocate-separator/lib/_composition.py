"""Cross-pattern composition manifest for the Devil's Advocate Separator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import RoleSeparationDetection, SingleAgentTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.bias_stack",
    "agentcity.psych_safety",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_separated_critique": ("agentcity.aar",),
    "self_review_only": (
        "agentcity.bias_stack",
        "agentcity.debate_pathology",
    ),
    "rubber_stamping": (
        "agentcity.bias_stack",
        "agentcity.aar",
    ),
    "missing_critic_phase": (
        "agentcity.debate_pathology",
        "agentcity.bias_stack",
    ),
    "fully_conflated_roles": (
        "agentcity.aar",
        "agentcity.bias_stack",
        "agentcity.debate_pathology",
    ),
    "external_critic_present_weak": (
        "agentcity.psych_safety",
        "agentcity.glaser_conversation",
    ),
    "no_pre_mortem": (
        "agentcity.bias_stack",
        "agentcity.aar",
    ),
    "no_alternative_hypothesis": (
        "agentcity.bias_stack",
        "agentcity.debate_pathology",
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
    detection: "RoleSeparationDetection",
    trace: "SingleAgentTrace | None" = None,
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


DEVILS_ADVOCATE_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "DEVILS_ADVOCATE_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
