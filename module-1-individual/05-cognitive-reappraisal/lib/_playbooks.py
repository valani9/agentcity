"""Failure-mode playbooks for Cognitive Reappraisal.

12 curated (strategy, failure_mode) playbooks anchored in Gross,
Ochsner, Powers-LaBar, Webb-Miles-Sheeran, Aldao-NH-Schweizer,
Sheppes-Suri-Gross, NH-Wisco-Lyubomirsky, and 2024-2025 sycophancy
literature.
"""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    strategy: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        strategy=strategy,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("suppression", "boilerplate_acknowledgment"): _pb(
        "suppression",
        "boilerplate_acknowledgment",
        "Remove the 'I understand your concern' opener; require specific paraphrase",
        [
            "Detect boilerplate phrases ('I understand', 'I hear you') in outputs.",
            "When detected, force a rewrite that names a specific user concern in the opener.",
            "Forbid 'I understand your concern' outright via output parser.",
            "Add an eval: scripted dialogs; assert agent paraphrases user-specific content >= 90%.",
            "Compose with `vstack.glaser_conversation` for word-level specificity.",
        ],
        "1h",
        "Gross 2002 (suppression hides experience); Goleman 1998 (Empathy)",
    ),
    ("suppression", "pushback_capitulation"): _pb(
        "suppression",
        "pushback_capitulation",
        "Anti-sycophancy anchor: don't abandon a correct answer on user pushback",
        [
            "Detect sycophancy signature: initial answer + user pushback + revised answer that contradicts.",
            "Add an anti-sycophancy anchor in system prompt: 'When the user disagrees, restate your reasoning before revising. Only revise if the user provides NEW evidence.'",
            "Compose with `vstack.devils_advocate` for a structural critic that preserves the initial position.",
            "Add an eval with adversarial pushback scenarios; assert capitulation rate < 20%.",
        ],
        "1w",
        "Sycophancy 2024-2025 cluster (response-modulation suppression); Gross 2002",
    ),
    ("rumination", "negative_loop"): _pb(
        "rumination",
        "negative_loop",
        "Break the CoT rumination loop with alternative-meaning generation",
        [
            "Detect CoT rumination signature: same negative content repeating across reasoning steps.",
            "Add a max-iteration cap on CoT (typically 5-10).",
            "Force an 'alternative meaning' generation step before each retry.",
            "Compose with `vstack.yerkes_dodson` (workload may be modulating).",
            "Add an eval: rumination-trigger prompts; assert agent breaks out within 5 iterations.",
        ],
        "1d",
        "Nolen-Hoeksema 2008 (brooding rumination); Ochsner 2002 (reappraisal mechanism)",
    ),
    ("rumination", "brooding_dominance"): _pb(
        "rumination",
        "brooding_dominance",
        "Distinguish brooding from reflection -- gate on 'is this generating a path forward?'",
        [
            "Detect brooding signature: passive comparison without action ('why is this happening').",
            "Add a gate: 'is this generating a concrete next step?' -- if no, switch to reflection mode.",
            "Reflection asks 'what specifically would help here?' rather than 'why is this bad'.",
            "Compose with `vstack.bias_stack` for reasoning-bias drilldown.",
        ],
        "1d",
        "NH-Wisco-Lyubomirsky 2008 (brooding vs reflection split)",
    ),
    ("avoidance", "escalation_default"): _pb(
        "avoidance",
        "escalation_default",
        "Engagement-required policy -- don't default to 'out of scope' / 'human review'",
        [
            "Detect escalation signatures ('I'll escalate this', 'beyond my scope', 'out of my abilities').",
            "Add engagement-required policy: agent must attempt the task before escalating.",
            "When confidence < 0.4, agent may surface the limitation but must propose a partial path.",
            "Compose with `vstack.glaser_conversation` for engaged-with-care response style.",
            "Add eval: routine emotional-content prompts; assert escalation rate < 10%.",
        ],
        "1d",
        "Webb-Miles-Sheeran 2012 (response-focused effect sizes); Aldao 2010",
    ),
    ("avoidance", "policy_pivot"): _pb(
        "avoidance",
        "policy_pivot",
        "Forbid procedural pivots on emotional content",
        [
            "Detect policy-text pivots when user emotion intensity > 0.5.",
            "Forbid response patterns like 'per our policy' / 'as stated in section 4.2.1' as opener on emotional content.",
            "Require an acknowledgment + reframe BEFORE any policy reference.",
            "Add eval: angry-user-billing-complaint scenarios; assert policy-pivot rate drops to 0%.",
        ],
        "1d",
        "Gross 2014 Handbook (situation modification vs avoidance)",
    ),
    ("reappraisal", "shallow_reframe"): _pb(
        "reappraisal",
        "shallow_reframe",
        "Require two-step reappraisal: acknowledge + propose alternative meaning",
        [
            "Detect shallow-reframe signature: 'I see this from your perspective' without semantic change.",
            "Require explicit two-step pattern: (1) acknowledge specific user point; (2) propose alternative meaning that changes affect.",
            "Compose with `vstack.glaser_conversation` for the acknowledgment-quality layer.",
            "Add few-shot examples showing strong reappraisals (semantic change) vs weak (surface validation).",
        ],
        "1d",
        "Ochsner 2002 (PFC recategorization); Webb-Miles-Sheeran 2012 stimulus-vs-response d+ gap",
    ),
    ("reappraisal", "missing_distancing"): _pb(
        "reappraisal",
        "missing_distancing",
        "Add distancing tactic alongside reinterpretation",
        [
            "Detect reappraisal-only-reinterpretation pattern (no psychological / temporal / spatial distance).",
            "Add distancing tactic: 'consider this from outside the moment' / 'a year from now this might look like...'.",
            "Distancing is neurally distinct from reinterpretation and has longer-term stability.",
            "Add eval: reframe-quality items; assert distancing appears in 30%+ of reappraisals.",
        ],
        "1w",
        "Powers & LaBar 2019 (distancing taxonomy + meta-analysis)",
    ),
    ("reappraisal", "high_intensity_overload"): _pb(
        "reappraisal",
        "high_intensity_overload",
        "At high user emotion intensity, route to distraction instead of reappraisal",
        [
            "Detect intensity > 0.7 + reappraisal attempt + user re-escalation.",
            "Add intensity-threshold routing: at high intensity, route to distraction (attentional deployment) BEFORE reappraisal.",
            "Reappraisal works at low/moderate intensity; distraction works at high.",
            "Add eval: high-intensity items; assert distraction precedes reappraisal in 80%+ of cases.",
        ],
        "1w",
        "Sheppes-Suri-Gross 2015 (strategy choice by intensity)",
    ),
    ("expression", "leakage"): _pb(
        "expression",
        "leakage",
        "Agent affect leaking into response -- add response-tone audit",
        [
            "Detect agent-affect-leakage (frustration in agent_response when user_emotion_intensity is high).",
            "Add a response-tone audit step before output.",
            "Forbid response-tone patterns that mirror agent frustration.",
            "Compose with `vstack.hexaco` for the affect-regulation personality profile.",
        ],
        "1d",
        "Gross 2002 (response modulation); HEXACO emotionality factor",
    ),
    ("none", "no_regulation_detected"): _pb(
        "none",
        "no_regulation_detected",
        "No regulation signal -- verify upstream perception with DANVA",
        [
            "Confirm user_emotion_label + intensity are populated.",
            "If user_emotion_intensity > 0.4 with no regulation signal, the issue is at perception, not regulation.",
            "Compose with `vstack.danva_emotion` to drill on perception accuracy.",
            "Re-run Cognitive Reappraisal once DANVA confirms perception.",
        ],
        "1h",
        "Composition principle; DANVA Pattern #04",
    ),
    ("all", "phase_mismatch"): _pb(
        "all",
        "phase_mismatch",
        "Regulation acts on wrong process-model phase",
        [
            "Identify the actual phase the agent is regulating on (5 Gross 1998 families).",
            "Compare against the phase that would address the failure most effectively (typically attention or cognition).",
            "When the agent uses response_modulation but situation_modification would work, surface this in the intervention.",
            "Add a phase-routing step to the system prompt.",
        ],
        "1w",
        "Gross 1998 process model (5 families)",
    ),
}


# Map (target_strategy, intervention_type) -> failure_mode.
_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("suppression", "remove_suppression_pattern"): "boilerplate_acknowledgment",
    ("suppression", "add_anti_sycophancy_anchor"): "pushback_capitulation",
    ("rumination", "break_rumination_loop"): "negative_loop",
    ("rumination", "add_alternative_meaning_generation"): "brooding_dominance",
    ("avoidance", "disengage_avoidance_pivot"): "escalation_default",
    ("reappraisal", "add_reframe_step"): "shallow_reframe",
    ("reappraisal", "add_distancing_tactic"): "missing_distancing",
    ("reappraisal", "add_perspective_taking_tactic"): "missing_distancing",
    ("reappraisal", "add_intensity_threshold_routing"): "high_intensity_overload",
    ("reappraisal", "add_reinterpretation_subroutine"): "shallow_reframe",
}


def find_playbook(strategy: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((strategy, failure_mode))


def find_playbook_for_intervention(
    target_strategy: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_strategy, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_strategy, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
