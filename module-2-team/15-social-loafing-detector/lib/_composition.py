"""Cross-pattern composition manifest for Social Loafing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import MultiAgentTaskTrace, SocialLoafingDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.grpi",
    "vstack.mcgregor",
    "vstack.process_gain_loss",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "balanced_team": ("vstack.aar",),
    "single_dominant_contributor": ("vstack.grpi", "vstack.mcgregor"),
    "two_contributors_n_loafers": ("vstack.grpi",),
    "all_loafers": (
        "vstack.grpi",
        "vstack.process_gain_loss",
        "vstack.lencioni",
    ),
    "ringelmann_dilution": ("vstack.process_gain_loss", "vstack.grpi"),
    "rubber_stamp_pattern": ("vstack.devils_advocate", "vstack.bias_stack"),
    "absent_agent": ("vstack.grpi",),
    "anonymous_evaluation_signal": ("vstack.aar",),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("vstack.grpi",),
    "crewai": ("vstack.grpi",),
    "autogen": ("vstack.grpi",),
    "claude-agent-sdk": ("vstack.mcgregor",),
    "openai-agents-sdk": ("vstack.mcgregor",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "SocialLoafingDetection",
    trace: "MultiAgentTaskTrace | None" = None,
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


SOCIAL_LOAFING_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "SOCIAL_LOAFING_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
