"""Cross-pattern composition manifest for McAllister Trust Dimensions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import TrustBalanceDetection, TrustConversationTrace


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.trust_triangle",
    "vstack.lencioni",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "balanced_high_trust": ("vstack.aar",),
    "cognitive_only": (
        "vstack.glaser_conversation",
        "vstack.danva_emotion",
        "vstack.goleman_ei",
    ),
    "warm_but_incompetent": (
        "vstack.devils_advocate",
        "vstack.bias_stack",
    ),
    "low_trust": (
        "vstack.lencioni",
        "vstack.aar",
    ),
    "cognitive_partial": ("vstack.devils_advocate",),
    "affective_partial": ("vstack.glaser_conversation",),
    "asymmetric_cognitive_strong": ("vstack.glaser_conversation",),
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
    detection: "TrustBalanceDetection",
    trace: "TrustConversationTrace | None" = None,
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


MCALLISTER_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "MCALLISTER_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
