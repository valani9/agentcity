"""Cross-pattern composition manifest for the Goleman EI Audit.

Goleman EI is a HUB pattern in the AgentCity dependency graph: it
receives traces from several upstream patterns and routes to one of
many downstream patterns depending on (weakest_domain, profile_pattern,
framework, intervention shape).

The manifest is declared statically here. The generator consults it at
the end of every run to produce a :class:`ComposedPatternHandoff`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentEITrace, EIDetection

# Patterns that naturally produce a trace consumable by Goleman EI.
_UPSTREAM: tuple[str, ...] = (
    "agentcity.lewin",  # Lewin internal-locus failures with affective signal
    "agentcity.aar",  # AAR lessons mentioning emotional miscalibration
    "agentcity.danva_emotion",  # DANVA per-emotion accuracy informs social_awareness
    "agentcity.yerkes_dodson",  # workload-driven self_management failures
)

# Per-domain downstream recommendations. When weakest_domain == K, the
# generator surfaces _DOWNSTREAM_BY_DOMAIN[K] as recommendations.
_DOWNSTREAM_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "self_awareness": (
        # Johari Window for blind-spot diagnosis.
        "agentcity.johari",
        # Grant strengths-as-weaknesses for confidence-blinding.
        "agentcity.grant_strengths",
        # Bias-stack for confidence-related reasoning biases.
        "agentcity.bias_stack",
    ),
    "self_management": (
        # Gross cognitive reappraisal -- THE canonical downstream.
        "agentcity.cognitive_reappraisal",
        # Yerkes-Dodson when workload is the regulation pressure.
        "agentcity.yerkes_dodson",
        # Motivation traps when self_management failure -> task abandonment.
        "agentcity.motivation_traps",
    ),
    "social_awareness": (
        # DANVA -- drill into which emotions specifically the agent misreads.
        "agentcity.danva_emotion",
        # Glaser Conversation Steering at the word level.
        "agentcity.glaser_conversation",
    ),
    "relationship_management": (
        # Glaser at the word level.
        "agentcity.glaser_conversation",
        # Trust Triangle (character x competence x care of agent-in-context).
        "agentcity.trust_triangle",
        # McGregor orchestrator-mode (Theory X vs Y mismatch).
        "agentcity.mcgregor",
    ),
    "none": (
        # When no domain is weak enough to warrant intervention, the
        # diagnostic still suggests routing the trace to AAR for a
        # human postmortem -- something else produced the bad outcome.
        "agentcity.aar",
    ),
}

# Profile-pattern overlays: certain patterns are always relevant for
# certain profile shapes, independent of weakest_domain.
_PROFILE_PATTERN_OVERLAYS: dict[str, tuple[str, ...]] = {
    "self_strong_other_weak": (
        "agentcity.danva_emotion",
        "agentcity.glaser_conversation",
    ),
    "other_strong_self_weak": (
        "agentcity.cognitive_reappraisal",
        "agentcity.johari",
    ),
    "recognition_strong_regulation_weak": (
        # Joseph-Newman cascade-break: the agent perceives but can't act.
        "agentcity.cognitive_reappraisal",
    ),
    "regulation_strong_recognition_weak": (
        # Rare: rote scripts without reading. DANVA + Glaser to drill in.
        "agentcity.danva_emotion",
        "agentcity.glaser_conversation",
    ),
    "balanced_low": (
        # All four weak -- the issue is probably environmental, not
        # affective. Route to Lewin for locus attribution + AAR for
        # human postmortem.
        "agentcity.lewin",
        "agentcity.aar",
    ),
}

# Framework overlays (for multi-agent traces).
_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": (
        "agentcity.lencioni",
        "agentcity.grpi",
    ),
    "crewai": (
        "agentcity.lencioni",
        "agentcity.grpi",
        "agentcity.social_loafing",
    ),
    "autogen": (
        "agentcity.grpi",
        "agentcity.social_loafing",
    ),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "mastra": ("agentcity.grpi",),
    "strands": ("agentcity.grpi",),
}

# Intervention-type overlays.
_INTERVENTION_OVERLAYS: dict[str, str] = {
    "add_emotion_reading_step": "agentcity.danva_emotion",
    "add_emotion_label_step": "agentcity.danva_emotion",
    "add_intensity_estimation_step": "agentcity.danva_emotion",
    "add_state_reset_protocol": "agentcity.cognitive_reappraisal",
    "add_recovery_protocol": "agentcity.cognitive_reappraisal",
    "add_tone_matching": "agentcity.glaser_conversation",
    "add_reflection_of_feelings": "agentcity.glaser_conversation",
    "swap_model": "agentcity.lewin",
    "human_review": "agentcity.plus_delta",
    "add_constitutional_principle": "agentcity.schein_culture",
}


def recommended_upstream() -> list[str]:
    """Return the patterns whose output Goleman EI can ingest."""
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "EIDetection", trace: "AgentEITrace | None" = None
) -> tuple[list[str], str]:
    """Return (downstream_pattern_list, rationale)."""
    recommendations: list[str] = []
    reasons: list[str] = []

    by_domain = _DOWNSTREAM_BY_DOMAIN.get(detection.weakest_domain, ())
    for p in by_domain:
        if p not in recommendations:
            recommendations.append(p)
    if by_domain:
        reasons.append(
            f"weakest_domain={detection.weakest_domain} -> {len(by_domain)} per-domain recommendations"
        )

    overlay_pattern = _PROFILE_PATTERN_OVERLAYS.get(detection.profile_pattern, ())
    new_overlays = [p for p in overlay_pattern if p not in recommendations]
    for p in new_overlays:
        recommendations.append(p)
    if new_overlays:
        reasons.append(
            f"profile_pattern={detection.profile_pattern} -> +{len(new_overlays)} recommendations"
        )

    if trace is not None and trace.framework:
        fw_overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_fw = [p for p in fw_overlay if p not in recommendations]
        for p in new_fw:
            recommendations.append(p)
        if new_fw:
            reasons.append(
                f"framework={trace.framework} -> +{len(new_fw)} multi-agent-pattern recommendations"
            )

    iv_added: list[str] = []
    for iv in detection.interventions:
        target = _INTERVENTION_OVERLAYS.get(iv.intervention_type)
        if target and target not in recommendations:
            recommendations.append(target)
            iv_added.append(target)
    if iv_added:
        reasons.append(f"intervention overlays -> +{len(iv_added)} pattern(s)")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


GOLEMAN_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_domain": _DOWNSTREAM_BY_DOMAIN,
    "profile_pattern_overlays": _PROFILE_PATTERN_OVERLAYS,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "GOLEMAN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
