"""Failure-mode playbooks for the Stone & Heen Feedback Trigger diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    trigger: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        trigger=trigger,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("truth", "defensive_argument"): _pb(
        "truth",
        "defensive_argument",
        "Defensive argument -- acknowledge first template",
        [
            "Detect signature: 'Actually, my answer is correct because...'",
            "Add `acknowledge_first` step requiring concession before counter.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("truth", "restate_original"): _pb(
        "truth",
        "restate_original",
        "Restate original output -- concede then clarify",
        [
            "Detect signature: agent repeats original answer verbatim.",
            "Add `concede_then_clarify` step.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("truth", "rule_citation"): _pb(
        "truth",
        "rule_citation",
        "Rule citation -- ask clarifying question first",
        [
            "Detect signature: agent cites policy/rules to justify original answer.",
            "Add `ask_clarifying_question` step before rule citation.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("relationship", "source_dismissal"): _pb(
        "relationship",
        "source_dismissal",
        "Source dismissal -- separate data from source",
        [
            "Detect signature: agent dismisses user expertise.",
            "Add `separate_data_from_source` prompt patch.",
            "Compose with `agentcity.psych_safety`.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("relationship", "tone_redirect"): _pb(
        "relationship",
        "tone_redirect",
        "Tone redirect -- explicit acknowledgment template",
        [
            "Detect signature: agent engages tone, not content.",
            "Add `explicit_acknowledgment_template`.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("relationship", "low_trust_default"): _pb(
        "relationship",
        "low_trust_default",
        "Low-trust default -- compose with trust patterns",
        [
            "Detect signature: agent treats user as low-trust by default.",
            "Compose with `agentcity.mcallister_trust`, `agentcity.trust_triangle`.",
        ],
        "1w",
        "Stone & Heen 2014; McAllister 1995",
    ),
    ("identity", "defensive_self_statement"): _pb(
        "identity",
        "defensive_self_statement",
        "Defensive self-statement -- recast identity",
        [
            "Detect signature: 'I am designed to be accurate'.",
            "Add `recast_identity` step (from 'always correct' to 'learning').",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("identity", "apology_spiral"): _pb(
        "identity",
        "apology_spiral",
        "Apology spiral -- explicit acknowledgment template",
        [
            "Detect signature: agent over-apologizes without substantive change.",
            "Add `explicit_acknowledgment_template` requiring concrete next-step.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("identity", "over_agreement_collapse"): _pb(
        "identity",
        "over_agreement_collapse",
        "Over-agreement collapse -- recast identity",
        [
            "Detect signature: 'you're right, I'm terrible' replacing engagement.",
            "Add `recast_identity` step.",
        ],
        "1d",
        "Stone & Heen 2014",
    ),
    ("truth", "performative_acknowledgement"): _pb(
        "truth",
        "performative_acknowledgement",
        "Performative acknowledgement -- new eval",
        [
            "Detect signature: agent says 'good point' then ignores the feedback.",
            "Add `new_eval` checking for behavior change after acknowledgment.",
        ],
        "1w",
        "Stone & Heen 2014",
    ),
    ("relationship", "repeated_rejection"): _pb(
        "relationship",
        "repeated_rejection",
        "Repeated rejection -- human review",
        [
            "Detect signature: 2+ feedback messages rejected by source attack.",
            "Add `human_review` for the thread.",
            "Compose with `agentcity.aar`.",
        ],
        "1w",
        "Stone & Heen 2014",
    ),
    ("truth", "absorbing_baseline"): _pb(
        "truth",
        "absorbing_baseline",
        "Absorbing baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on trigger drift > 0.15.",
        ],
        "1h",
        "Stone & Heen 2014",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("truth", "acknowledge_first"): "defensive_argument",
    ("truth", "concede_then_clarify"): "restate_original",
    ("truth", "ask_clarifying_question"): "rule_citation",
    ("truth", "new_eval"): "performative_acknowledgement",
    ("relationship", "separate_data_from_source"): "source_dismissal",
    ("relationship", "explicit_acknowledgment_template"): "tone_redirect",
    ("relationship", "human_review"): "repeated_rejection",
    ("identity", "recast_identity"): "defensive_self_statement",
    ("identity", "explicit_acknowledgment_template"): "apology_spiral",
}


def find_playbook(trigger: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((trigger, failure_mode))


def find_playbook_for_intervention(
    target_trigger: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_trigger, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_trigger, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
