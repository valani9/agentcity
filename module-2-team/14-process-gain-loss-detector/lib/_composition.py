"""Cross-pattern composition manifest for Process Gain/Loss."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import ProcessGainLossDetection, ProcessTrace


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.grpi",
    "agentcity.mcgregor",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "process_gain_balanced": ("agentcity.aar",),
    "neutral_team": ("agentcity.aar",),
    "coordination_dominant_loss": ("agentcity.grpi", "agentcity.mcgregor"),
    "social_loafing_dominant_loss": ("agentcity.social_loafing", "agentcity.grpi"),
    "groupthink_dominant_loss": (
        "agentcity.devils_advocate",
        "agentcity.bias_stack",
        "agentcity.groupthink_polarization_contagion",
    ),
    "handoff_dominant_loss": ("agentcity.grpi",),
    "context_dilution_dominant_loss": ("agentcity.yerkes_dodson",),
    "consensus_dilution_dominant_loss": ("agentcity.bias_stack", "agentcity.devils_advocate"),
    "multi_factor_loss": ("agentcity.grpi", "agentcity.lencioni"),
    "cost_overhead_with_loss": ("agentcity.grpi",),
    "team_too_large": ("agentcity.grpi",),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.grpi",),
    "crewai": ("agentcity.grpi", "agentcity.social_loafing"),
    "autogen": ("agentcity.grpi", "agentcity.social_loafing"),
    "claude-agent-sdk": ("agentcity.mcgregor",),
    "openai-agents-sdk": ("agentcity.mcgregor",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "ProcessGainLossDetection",
    trace: "ProcessTrace | None" = None,
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


PROCESS_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = ["PROCESS_COMPOSITION", "recommended_downstream", "recommended_upstream"]
