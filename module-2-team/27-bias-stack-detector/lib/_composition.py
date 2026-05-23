"""Cross-pattern composition manifest for the Bias-Stack diagnostic."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentReasoningTrace, BiasStackDetection


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.devils_advocate",
    "agentcity.debate_pathology",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "well_calibrated": ("agentcity.aar",),
    "anchoring_dominant": (
        "agentcity.devils_advocate",
        "agentcity.aar",
    ),
    "overconfidence_dominant": (
        "agentcity.trust_triangle",
        "agentcity.devils_advocate",
    ),
    "confirmation_dominant": (
        "agentcity.devils_advocate",
        "agentcity.debate_pathology",
    ),
    "escalation_dominant": (
        "agentcity.aar",
        "agentcity.grpi",
    ),
    "full_stack_severe": (
        "agentcity.aar",
        "agentcity.devils_advocate",
        "agentcity.lencioni",
    ),
    "anchoring_overconfidence_pair": (
        "agentcity.devils_advocate",
        "agentcity.trust_triangle",
    ),
    "confirmation_escalation_pair": (
        "agentcity.aar",
        "agentcity.devils_advocate",
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
    detection: "BiasStackDetection",
    trace: "AgentReasoningTrace | None" = None,
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


BIAS_STACK_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "BIAS_STACK_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
