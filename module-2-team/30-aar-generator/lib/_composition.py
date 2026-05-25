"""Cross-pattern composition manifest for the AAR Generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AAR, AgentTrace


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.grpi",
    "vstack.smart_goal",
    "vstack.lencioni",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "success_aligned": (),
    "partial_success": (
        "vstack.smart_goal",
        "vstack.plus_delta",
    ),
    "total_failure": (
        "vstack.grpi",
        "vstack.lewin",
    ),
    "scope_mismatch": (
        "vstack.smart_goal",
        "vstack.grpi",
    ),
    "retry_thrashing": (
        "vstack.bias_stack",
        "vstack.devils_advocate",
    ),
    "cost_overrun": (
        "vstack.smart_goal",
        "vstack.yerkes_dodson",
    ),
    "deadline_missed": (
        "vstack.smart_goal",
        "vstack.grpi",
    ),
    "indeterminate": (),
}

_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": (),
    "crewai": ("vstack.lencioni",),
    "autogen": (),
    "claude-agent-sdk": ("vstack.grpi",),
}


def recommended_upstream() -> list[str]:
    return list(_UPSTREAM)


def recommended_downstream(
    aar: "AAR",
    trace: "AgentTrace | None" = None,
) -> tuple[list[str], str]:
    recommendations: list[str] = []
    reasons: list[str] = []
    by_profile = _DOWNSTREAM_BY_PROFILE_PATTERN.get(aar.profile_pattern, ())
    for p in by_profile:
        if p not in recommendations:
            recommendations.append(p)
    if by_profile:
        reasons.append(
            f"profile_pattern={aar.profile_pattern} -> {len(by_profile)} recommendations"
        )
    if trace is not None and trace.agent_framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.agent_framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(f"framework={trace.agent_framework} -> +{len(new_fw)} recommendations")
    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


AAR_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "AAR_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
