"""Cross-pattern composition manifest for the Devil's Advocate Separator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import RoleSeparationDetection, SingleAgentTrace


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.bias_stack",
    "vstack.psych_safety",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_separated_critique": ("vstack.aar",),
    "self_review_only": (
        "vstack.bias_stack",
        "vstack.debate_pathology",
    ),
    "rubber_stamping": (
        "vstack.bias_stack",
        "vstack.aar",
    ),
    "missing_critic_phase": (
        "vstack.debate_pathology",
        "vstack.bias_stack",
    ),
    "fully_conflated_roles": (
        "vstack.aar",
        "vstack.bias_stack",
        "vstack.debate_pathology",
    ),
    "external_critic_present_weak": (
        "vstack.psych_safety",
        "vstack.glaser_conversation",
    ),
    "no_pre_mortem": (
        "vstack.bias_stack",
        "vstack.aar",
    ),
    "no_alternative_hypothesis": (
        "vstack.bias_stack",
        "vstack.debate_pathology",
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
