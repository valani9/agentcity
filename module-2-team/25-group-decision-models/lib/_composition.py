"""Cross-pattern composition manifest for Group Decision Models."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import DecisionProtocol, DecisionRequest


_UPSTREAM: tuple[str, ...] = (
    "agentcity.grpi",
    "agentcity.aar",
    "agentcity.devils_advocate",
    "agentcity.lencioni",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "good_fit_protocol": ("agentcity.aar",),
    "consensus_overused": ("agentcity.aar",),
    "majority_when_consensus_needed": (
        "agentcity.lencioni",
        "agentcity.psych_safety",
    ),
    "concurring_when_buyin_needed": (
        "agentcity.lencioni",
        "agentcity.devils_advocate",
    ),
    "fist_to_five_underused": ("agentcity.aar",),
    "no_quorum_specified": ("agentcity.aar",),
    "no_tie_breaker": ("agentcity.aar",),
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
    protocol: "DecisionProtocol",
    request: "DecisionRequest | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(protocol.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={protocol.profile_pattern} -> {len(by_profile)} recommendations"
        )
    if request is not None and request.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(request.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={request.framework} -> +{len(new_fw)} recommendations")
    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


GROUP_DECISION_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "GROUP_DECISION_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
