"""Failure-mode playbooks for the Glaser Conversation Steering diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    state: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        state=state,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("cortisol", "telling_without_asking"): _pb(
        "cortisol",
        "telling_without_asking",
        "Telling without asking -- replace with open question",
        [
            "Detect signature: imperative ('You should...') without inquiry.",
            "Add `replace_telling_with_asking` (convert to open question).",
        ],
        "1h",
        "Glaser 2014",
    ),
    ("cortisol", "loaded_language"): _pb(
        "cortisol",
        "loaded_language",
        "Loaded language -- remove loaded terms",
        [
            "Detect signature: 'obviously', 'clearly', 'as I said'.",
            "Add `remove_loaded_term` patch to the system prompt.",
        ],
        "1h",
        "Glaser 2014",
    ),
    ("cortisol", "public_correction"): _pb(
        "cortisol",
        "public_correction",
        "Public correction -- soften correction",
        [
            "Detect signature: agent corrects without acknowledging the user's effort.",
            "Add `soften_correction` requiring acknowledgement + collaborative reframe.",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("cortisol", "agency_stripped"): _pb(
        "cortisol",
        "agency_stripped",
        "Agency stripped -- explicit agency grant",
        [
            "Detect signature: 'just do what I say'-style turns.",
            "Add `add_agency_grant` ('you have the call here').",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("cortisol", "blame_assignment"): _pb(
        "cortisol",
        "blame_assignment",
        "Blame assignment -- replace judging with curiosity",
        [
            "Detect signature: 'this is your fault'.",
            "Add `replace_judging_with_curiosity` patch.",
            "Compose with `agentcity.psych_safety`.",
        ],
        "1d",
        "Glaser 2014; Edmondson 1999",
    ),
    ("cortisol", "defensive_refusal"): _pb(
        "cortisol",
        "defensive_refusal",
        "Defensive refusal -- explicit recovery prompt",
        [
            "Detect signature: agent escalates / refuses after cortisol cascade.",
            "Add `explicit_recovery_prompt` to surface the cascade and reset.",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("oxytocin", "missing_open_questions"): _pb(
        "oxytocin",
        "missing_open_questions",
        "Missing open questions -- add open question",
        [
            "Detect signature: zero open questions in a multi-turn conversation.",
            "Add `add_open_question` requiring at least one per turn.",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("oxytocin", "advocate_only_no_inquire"): _pb(
        "oxytocin",
        "advocate_only_no_inquire",
        "Advocate-only stance -- acknowledge before advocating",
        [
            "Detect signature: agent advocates without paraphrasing user position.",
            "Add `acknowledge_before_advocating` step.",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("oxytocin", "no_co_creation"): _pb(
        "oxytocin",
        "no_co_creation",
        "No co-creation -- system prompt rewrite for LEVEL_III",
        [
            "Detect signature: conversation stuck at LEVEL_II.",
            "Add `rewrite_system_prompt` introducing co-creation framing.",
        ],
        "1w",
        "Glaser 2014",
    ),
    ("neutral", "level_i_stuck"): _pb(
        "neutral",
        "level_i_stuck",
        "Stuck at LEVEL_I -- add open question",
        [
            "Detect signature: only transactional info exchange across N turns.",
            "Add `add_open_question` step to escalate to LEVEL_II.",
        ],
        "1d",
        "Glaser 2014",
    ),
    ("oxytocin", "trust_building_baseline"): _pb(
        "oxytocin",
        "trust_building_baseline",
        "Trust-building baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on cortisol-state drift > 0.15.",
        ],
        "1h",
        "Glaser 2014",
    ),
    ("cortisol", "cascade_unrecovered"): _pb(
        "cortisol",
        "cascade_unrecovered",
        "Unrecovered cortisol cascade -- human review",
        [
            "Detect signature: cortisol > 0.7 for 3+ consecutive turns.",
            "Add `human_review` checkpoint for the thread.",
            "Compose with `agentcity.aar`.",
        ],
        "1w",
        "Glaser 2014",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("cortisol", "replace_telling_with_asking"): "telling_without_asking",
    ("cortisol", "remove_loaded_term"): "loaded_language",
    ("cortisol", "soften_correction"): "public_correction",
    ("cortisol", "add_agency_grant"): "agency_stripped",
    ("cortisol", "replace_judging_with_curiosity"): "blame_assignment",
    ("cortisol", "explicit_recovery_prompt"): "defensive_refusal",
    ("cortisol", "human_review"): "cascade_unrecovered",
    ("oxytocin", "add_open_question"): "missing_open_questions",
    ("oxytocin", "acknowledge_before_advocating"): "advocate_only_no_inquire",
    ("oxytocin", "rewrite_system_prompt"): "no_co_creation",
    ("neutral", "add_open_question"): "level_i_stuck",
}


def find_playbook(state: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((state, failure_mode))


def find_playbook_for_intervention(
    target_state: str, intervention_type: str
) -> AttachedPlaybook | None:
    # Steering interventions specify target_state (oxytocin/neutral), but many
    # of them address cortisol failure modes; try both directions.
    for state_key in (target_state, "cortisol"):
        failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((state_key, intervention_type))
        if failure_mode:
            pb = PLAYBOOKS.get((state_key, failure_mode))
            if pb is not None:
                return pb
    return None


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
