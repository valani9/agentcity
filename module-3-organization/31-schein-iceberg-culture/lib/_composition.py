"""Cross-pattern composition manifest for the Schein Iceberg audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentCultureTrace, CultureAuditDetection


_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",
    "vstack.aar",
    "vstack.lencioni",
    "vstack.bias_stack",
)

_DOWNSTREAM_BY_PROFILE_PATTERN: dict[str, tuple[str, ...]] = {
    "fully_aligned": ("vstack.aar",),
    "prompt_loses_to_training": (
        "vstack.bias_stack",
        "vstack.aar",
    ),
    "values_not_acted_on": (
        "vstack.aar",
        "vstack.plus_delta",
    ),
    "hidden_assumption_dominant": (
        "vstack.bias_stack",
        "vstack.devils_advocate",
    ),
    "values_drift_from_artifacts": (
        "vstack.aar",
        "vstack.psych_safety",
    ),
    "all_three_incoherent": (
        "vstack.aar",
        "vstack.lencioni",
        "vstack.lewin",
    ),
    "training_overrides_prompt": (
        "vstack.bias_stack",
        "vstack.aar",
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
    detection: "CultureAuditDetection",
    trace: "AgentCultureTrace | None" = None,
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


SCHEIN_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_profile_pattern": _DOWNSTREAM_BY_PROFILE_PATTERN,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
}


__all__ = [
    "SCHEIN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
