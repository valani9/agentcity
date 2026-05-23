"""Cross-pattern composition manifest for the Lewin diagnostic.

The Lewin pattern sits in the middle of the AgentCity dependency graph:
many patterns produce traces that should be diagnosed via Lewin first
(to redirect engineering effort), and Lewin's diagnosis points to
several downstream patterns based on the dominant locus.

This module declares the composition graph statically. The generator
consults it at the end of every run to produce a
:class:`ComposedPatternHandoff` recommendation.

Design notes
------------
The recommendations are conservative: only patterns that are
*operationally relevant* for the (locus, framework, intervention shape)
combination are surfaced. Padding the recommendation list with every
adjacent pattern would dilute the signal. The graph is hand-curated
based on the per-pattern READMEs in the repository.

For new patterns added after v0.1.0, contributors register their
upstream/downstream relationship by extending
``_DOWNSTREAM_BY_LOCUS`` / ``_UPSTREAM`` / ``_FRAMEWORK_OVERLAYS``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schema import AgentFailureTrace, LewinDetection

# Patterns that naturally produce a trace consumable by Lewin.
# An AAR (pattern #30) produces "lessons" — each lesson can be turned
# into an AgentFailureTrace and fed into Lewin for locus attribution.
_UPSTREAM: tuple[str, ...] = (
    "agentcity.aar",
    # Yerkes-Dodson workload diagnostic may surface a workload-driven
    # failure that you then want to attribute via Lewin to confirm.
    "agentcity.yerkes_dodson",
)

# Per-locus downstream recommendations. When dominant_locus == K, the
# generator surfaces _DOWNSTREAM_BY_LOCUS[K] as recommendations.
_DOWNSTREAM_BY_LOCUS: dict[str, tuple[str, ...]] = {
    "internal": (
        # If the locus is internal, the failure is in the model itself.
        # Bias-Stack diagnoses the specific reasoning bias; HEXACO
        # characterizes the model's "personality" against the task fit;
        # Goleman EI tests emotional-recognition competency.
        "agentcity.bias_stack",
        "agentcity.hexaco",
        "agentcity.goleman_ei",
    ),
    "environmental": (
        # If the locus is environmental, the failure is in the
        # scaffolding. SMART goals fix vague task framing; GRPI fixes
        # the working agreement in multi-agent settings; Lencioni
        # diagnoses the team-level dysfunction (multi-agent only);
        # Schein iceberg surfaces the system-prompt-encoded "culture";
        # Edmondson psych-safety checks whether the orchestration
        # punishes dissent (relevant in critic/critique loops).
        "agentcity.smart_goal",
        "agentcity.grpi",
        "agentcity.lencioni",
        "agentcity.schein_culture",
        "agentcity.psych_safety",
    ),
    "interactional": (
        # If the locus is interactional, a full postmortem via AAR is
        # the right next step; trust-triangle and Vroom expectancy can
        # also help (the agent may have given up early due to low
        # expectancy in the specific environment it's in).
        "agentcity.aar",
        "agentcity.trust_triangle",
        "agentcity.vroom_expectancy",
    ),
    "indeterminate": (
        # When the diagnostic is inconclusive, route to AAR for a
        # human-led postmortem rather than guessing.
        "agentcity.aar",
    ),
}

# Framework-conditional overlays. When a trace comes from a known
# multi-agent framework, we add patterns that specifically diagnose
# multi-agent failure modes — even if the dominant locus would not
# otherwise surface them.
_FRAMEWORK_OVERLAYS: dict[str, tuple[str, ...]] = {
    "langgraph": (
        "agentcity.devils_advocate",
        "agentcity.group_decision",
    ),
    "crewai": (
        "agentcity.grpi",
        "agentcity.social_loafing",
        "agentcity.devils_advocate",
    ),
    "autogen": (
        "agentcity.group_decision",
        "agentcity.devils_advocate",
        "agentcity.social_loafing",
    ),
    "openai-agents-sdk": ("agentcity.process_gain_loss",),
    "mastra": ("agentcity.grpi",),
    "claude-agent-sdk": ("agentcity.process_gain_loss",),
    "strands": ("agentcity.grpi",),
}

# Intervention-type-conditional overlays. Some intervention types
# point so directly at another pattern that we should always surface
# it as a downstream.
_INTERVENTION_OVERLAYS: dict[str, str] = {
    "change_prompt": "agentcity.schein_culture",
    "add_verification_step": "agentcity.devils_advocate",
    "change_topology": "agentcity.grpi",
    "change_memory": "agentcity.johari",
    "new_eval": "agentcity.smart_goal",
    "human_review": "agentcity.plus_delta",
}


def recommended_upstream() -> list[str]:
    """Return the patterns whose output Lewin can ingest."""
    return list(_UPSTREAM)


def recommended_downstream(
    detection: "LewinDetection", trace: "AgentFailureTrace | None" = None
) -> tuple[list[str], str]:
    """Return (downstream_pattern_list, rationale).

    Rules, in order:
      1. Add the per-locus downstream patterns for ``detection.dominant_locus``.
      2. If ``trace.framework`` is known, add the framework overlay.
      3. For each intervention, add the intervention-type overlay.
      4. Deduplicate while preserving order (the first occurrence wins).
    """
    recommendations: list[str] = []
    reasons: list[str] = []

    by_locus = _DOWNSTREAM_BY_LOCUS.get(detection.dominant_locus, ())
    for p in by_locus:
        if p not in recommendations:
            recommendations.append(p)
    if by_locus:
        reasons.append(
            f"dominant locus = {detection.dominant_locus} "
            f"⇒ {len(by_locus)} per-locus recommendations"
        )

    if trace is not None and trace.framework:
        overlay = _FRAMEWORK_OVERLAYS.get(trace.framework, ())
        new_overlays = [p for p in overlay if p not in recommendations]
        for p in new_overlays:
            recommendations.append(p)
        if new_overlays:
            reasons.append(
                f"framework = {trace.framework} ⇒ "
                f"+{len(new_overlays)} multi-agent-pattern recommendations"
            )

    iv_overlays_added: list[str] = []
    for iv in detection.interventions:
        target = _INTERVENTION_OVERLAYS.get(iv.intervention_type)
        if target and target not in recommendations:
            recommendations.append(target)
            iv_overlays_added.append(target)
    if iv_overlays_added:
        reasons.append(f"intervention overlays ⇒ +{len(iv_overlays_added)} pattern(s)")

    rationale = "; ".join(reasons) if reasons else "no specific recommendations"
    return recommendations, rationale


# The composition manifest as a public read-only dict (handy for
# documentation generators and the CLI's `agentcity lewin compose` view).
LEWIN_COMPOSITION: dict[str, object] = {
    "upstream": _UPSTREAM,
    "downstream_by_locus": _DOWNSTREAM_BY_LOCUS,
    "framework_overlays": _FRAMEWORK_OVERLAYS,
    "intervention_overlays": _INTERVENTION_OVERLAYS,
}


__all__ = [
    "LEWIN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
]
