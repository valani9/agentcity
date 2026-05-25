"""Cross-pattern composition manifest for Stone & Heen Feedback Triggers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import FeedbackInteractionTrace, FeedbackTriggerDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.psych_safety",
    "vstack.glaser_conversation",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "absorbing_baseline": ("vstack.aar",),
    "truth_triggered_defensive": (
        "vstack.devils_advocate",
        "vstack.plus_delta",
    ),
    "relationship_triggered_rejection": (
        "vstack.mcallister_trust",
        "vstack.trust_triangle",
        "vstack.psych_safety",
    ),
    "identity_triggered_collapse": (
        "vstack.hexaco",
        "vstack.psych_safety",
    ),
    "multi_triggered_resistant": (
        "vstack.aar",
        "vstack.psych_safety",
        "vstack.glaser_conversation",
    ),
    "deflection_pattern": (
        "vstack.aar",
        "vstack.glaser_conversation",
    ),
    "performative_acknowledgement": (
        "vstack.aar",
        "vstack.plus_delta",
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
    detection: "FeedbackTriggerDetection",
    trace: "FeedbackInteractionTrace | None" = None,
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


FEEDBACK_TRIGGERS_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "FEEDBACK_TRIGGERS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
