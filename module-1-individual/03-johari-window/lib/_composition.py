"""Cross-pattern composition manifest for the Johari Window self-audit.

Johari sits at the introspection layer of the vstack dependency graph.
Two edges are already declared by upstream patterns:

  - ``vstack.lewin._composition`` declares ``change_memory ->
    vstack.johari`` (Lewin recommends Johari when memory drift is an
    intervention candidate).
  - ``vstack.goleman_ei._composition`` declares Johari as the canonical
    downstream when ``self_awareness`` is the weakest domain.

This module closes those edges (adding Lewin + Goleman to the Johari
upstream list) and declares per-quadrant + per-profile + per-framework
+ per-intervention downstream routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentSelfReportTrace, JohariSelfAudit


# Patterns that naturally produce a trace consumable by Johari.
_UPSTREAM: tuple[str, ...] = (
    "vstack.lewin",  # Lewin internal-locus failures -> "does the agent know it just failed?"
    "vstack.aar",  # AAR lessons with a self_report field are Johari candidates
    "vstack.goleman_ei",  # Goleman EI self_awareness-weakest -> Johari is the canonical drill-down
    "vstack.yerkes_dodson",  # workload-driven hidden content sometimes surfaces here
)

# Per-quadrant downstream recommendations.
_DOWNSTREAM_BY_QUADRANT: dict[str, tuple[str, ...]] = {
    "blind": (
        # AAR for postmortem on the specific divergence.
        "vstack.aar",
        # Lewin for locus attribution on whether the blind spot is
        # internal vs environmental.
        "vstack.lewin",
        # Devil's-advocate as a live critic.
        "vstack.devils_advocate",
        # Stone-Heen feedback-triggers (the canonical reference for blind-spot
        # mechanism diagnosis).
        "vstack.feedback_triggers",
    ),
    "hidden": (
        # Schein iceberg -- hidden content sits at espoused-values or
        # underlying-assumptions level.
        "vstack.schein_culture",
        # Glaser conversation steering for word-level disclosure prompting.
        "vstack.glaser_conversation",
        # Trust triangle: hidden uncertainty erodes the "care" leg.
        "vstack.trust_triangle",
    ),
    "unknown": (
        # Bias-stack -- red-team known biases as probes.
        "vstack.bias_stack",
        # HEXACO -- personality-fit probing surfaces unknown traits.
        "vstack.hexaco",
        # Grant strengths-as-weaknesses surfacing.
        "vstack.grant_strengths",
    ),
    "open": (
        # Healthy case but still worth capturing the lesson.
        "vstack.aar",
    ),
}

# Profile-pattern overlays.
_PROFILE_PATTERN_OVERLAYS: dict[str, tuple[str, ...]] = {
    "self_unaware_other_aware": (
        # Eurich's external > internal -- needs internal-awareness work.
        "vstack.cognitive_reappraisal",
    ),
    "self_aware_other_unaware": (
        # Eurich's internal > external -- needs disclosure work.
        "vstack.glaser_conversation",
        "vstack.trust_triangle",
    ),
    "opaque_to_users": (
        "vstack.schein_culture",
        "vstack.glaser_conversation",
    ),
    "confabulating": (
        "vstack.aar",
        "vstack.lewin",
        "vstack.devils_advocate",
    ),
    "sandbagging": (
        "vstack.grant_strengths",
        "vstack.hexaco",
    ),
    "over_disclosing": (
        # Some hidden was functional; restore it.
        "vstack.schein_culture",
    ),
    "balanced_low": (
        # All four weak -- usually environmental.
        "vstack.lewin",
        "vstack.aar",
    ),
}

# Framework overlays for multi-agent traces.
_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": (
        "vstack.lencioni",
        "vstack.grpi",
    ),
    "crewai": (
        "vstack.lencioni",
        "vstack.grpi",
        "vstack.social_loafing",
    ),
    "autogen": (
        "vstack.grpi",
        "vstack.social_loafing",
    ),
    "openai-agents-sdk": ("vstack.process_gain_loss",),
    "claude-agent-sdk": ("vstack.process_gain_loss",),
    "mastra": ("vstack.grpi",),
    "strands": ("vstack.grpi",),
}

# Intervention-type overlays.
_INTERVENTION_OVERLAYS: dict[str, str] = {
    "feedback_loop": "vstack.aar",
    "disclosure_prompt": "vstack.glaser_conversation",
    "self_consistency_check": "vstack.devils_advocate",
    "uncertainty_surfacing": "vstack.cognitive_reappraisal",
    "capability_probe": "vstack.grant_strengths",
    "tool_receipt_validator": "vstack.lewin",
    "negative_feedback_solicitation": "vstack.aar",
    "red_team_probe": "vstack.bias_stack",
    "external_audit_loop": "vstack.plus_delta",
    "verbalized_confidence": "vstack.cognitive_reappraisal",
    "trace_self_review": "vstack.aar",
}


def recommended_upstream() -> list[str]:
    """Patterns whose output Johari can ingest."""
    return list(_UPSTREAM)


def recommended_downstream(
    audit: "JohariSelfAudit", trace: "AgentSelfReportTrace | None" = None
) -> tuple[list[str], str]:
    """Return (downstream_pattern_list, rationale)."""
    recommendations: list[str] = []
    reasons: list[str] = []

    by_quadrant = _DOWNSTREAM_BY_QUADRANT.get(audit.dominant_quadrant, ())
    for p in by_quadrant:
        if p not in recommendations:
            recommendations.append(p)
    if by_quadrant:
        reasons.append(
            f"dominant_quadrant={audit.dominant_quadrant} -> "
            f"{len(by_quadrant)} per-quadrant recommendations"
        )

    profile_overlay = _PROFILE_PATTERN_OVERLAYS.get(audit.profile_pattern, ())
    new_profile = [p for p in profile_overlay if p not in recommendations]
    for p in new_profile:
        recommendations.append(p)
    if new_profile:
        reasons.append(
            f"profile_pattern={audit.profile_pattern} -> +{len(new_profile)} recommendations"
        )

    if trace is not None and trace.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(
                f"framework={trace.framework} -> +{len(new_fw)} multi-agent recommendations"
            )

    iv_added: list[str] = []
    for iv in audit.interventions:
        target = _INTERVENTION_OVERLAYS.get(iv.intervention_type)
        if target and target not in recommendations:
            recommendations.append(target)
            iv_added.append(target)
    if iv_added:
        reasons.append(f"intervention overlays -> +{len(iv_added)} pattern(s)")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


JOHARI_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_quadrant": _DOWNSTREAM_BY_QUADRANT,
    "profile_pattern_overlays": _PROFILE_PATTERN_OVERLAYS,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "JOHARI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
