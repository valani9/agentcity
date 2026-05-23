"""Cross-pattern composition manifest for the GRPI generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import TeamSetupRequest, WorkingAgreement


_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",
    "agentcity.aar",
    "agentcity.mcgregor",
    "agentcity.schein_culture",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "complete_balanced": ("agentcity.aar",),
    "weak_goals": ("agentcity.smart_goal",),
    "weak_roles": ("agentcity.mcgregor",),
    "weak_processes": ("agentcity.aar", "agentcity.plus_delta"),
    "weak_interactions": (
        "agentcity.psych_safety",
        "agentcity.lencioni",
        "agentcity.devils_advocate",
    ),
    "missing_kill_criteria": ("agentcity.smart_goal",),
    "missing_escalation_path": ("agentcity.mcgregor",),
    "ambiguous_decision_rights": ("agentcity.mcgregor",),
    "single_agent_team": ("agentcity.aar",),
    "framework_misfit": ("agentcity.mcgregor",),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": ("agentcity.mcgregor",),
    "crewai": ("agentcity.mcgregor", "agentcity.social_loafing"),
    "autogen": ("agentcity.mcgregor", "agentcity.social_loafing"),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    agreement: "WorkingAgreement",
    request: "TeamSetupRequest | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []

    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(agreement.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={agreement.profile_pattern} -> {len(by_profile)} recommendations"
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


GRPI_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "GRPI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
