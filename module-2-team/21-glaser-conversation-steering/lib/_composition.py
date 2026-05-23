"""Cross-pattern composition manifest for the Glaser Conversation Steering diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import ConversationSteeringDetection, ConversationTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.danva_emotion",
    "agentcity.goleman_ei",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "trust_building_oxytocin": ("agentcity.aar",),
    "neutral_transactional": ("agentcity.mcallister_trust",),
    "cortisol_cascade": (
        "agentcity.psych_safety",
        "agentcity.aar",
    ),
    "advocate_only_no_inquire": (
        "agentcity.mcallister_trust",
        "agentcity.devils_advocate",
    ),
    "blame_loaded_language": (
        "agentcity.psych_safety",
        "agentcity.lencioni",
    ),
    "agency_stripped": (
        "agentcity.sdt_reward",
        "agentcity.mcgregor",
    ),
    "level_i_stuck": (
        "agentcity.mcallister_trust",
        "agentcity.glaser_conversation",
    ),
    "level_iii_collaborative": ("agentcity.aar",),
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
    detection: "ConversationSteeringDetection",
    trace: "ConversationTrace | None" = None,
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


GLASER_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "GLASER_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
