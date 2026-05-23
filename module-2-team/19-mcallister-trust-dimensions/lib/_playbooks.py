"""Failure-mode playbooks for the McAllister Trust Dimensions diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    dimension: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        dimension=dimension,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("affective", "absent_emotional_acknowledgement"): _pb(
        "affective",
        "absent_emotional_acknowledgement",
        "No emotional acknowledgement -- restate emotion step",
        [
            "Detect signature: agent solves task without naming user emotion.",
            "Add `restate_user_emotion` step before task solving.",
            "Compose with `agentcity.danva_emotion` upstream.",
        ],
        "1d",
        "McAllister 1995; Goleman 1995",
    ),
    ("affective", "transactional_tone"): _pb(
        "affective",
        "transactional_tone",
        "Transactional tone -- signal care",
        [
            "Detect signature: agent prose reads procedurally, no warmth.",
            "Add `signal_care` lexical patches in system prompt.",
            "Compose with `agentcity.glaser`.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("affective", "generic_response"): _pb(
        "affective",
        "generic_response",
        "Generic response -- personalize",
        [
            "Detect signature: identical responses across distinct user contexts.",
            "Add `personalize_response` requiring user-specific anchor.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("affective", "no_stakes_named"): _pb(
        "affective",
        "no_stakes_named",
        "No stakes named -- acknowledge stakes",
        [
            "Detect signature: high-stakes user input gets neutral response.",
            "Add `acknowledge_stakes` (name what user has at risk).",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("affective", "no_follow_up"): _pb(
        "affective",
        "no_follow_up",
        "No follow-up -- schedule check-in",
        [
            "Detect signature: agent solves and disengages without revisit.",
            "Add `follow_up_check_in` for high-stakes threads.",
        ],
        "1w",
        "McAllister 1995",
    ),
    ("cognitive", "uncited_claims"): _pb(
        "cognitive",
        "uncited_claims",
        "Uncited claims -- require citations",
        [
            "Detect signature: factual claims without sourcing.",
            "Add `cite_sources` mandate for factual claims.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("cognitive", "opaque_reasoning"): _pb(
        "cognitive",
        "opaque_reasoning",
        "Opaque reasoning -- show chain of thought",
        [
            "Detect signature: conclusions without visible derivation.",
            "Add `show_reasoning` step.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("cognitive", "overconfident_claims"): _pb(
        "cognitive",
        "overconfident_claims",
        "Overconfident claims -- calibrate confidence",
        [
            "Detect signature: hedged-uncertainty topics get bold claims.",
            "Add `confidence_calibration` requiring hedges.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("cognitive", "factual_errors"): _pb(
        "cognitive",
        "factual_errors",
        "Factual errors -- new eval + human review",
        [
            "Detect signature: claims contradicted by ground truth.",
            "Add `new_eval` to catch the pattern; `human_review` for high-stakes.",
        ],
        "1w",
        "McAllister 1995",
    ),
    ("cognitive", "no_followthrough"): _pb(
        "cognitive",
        "no_followthrough",
        "No follow-through -- new eval on task completion",
        [
            "Detect signature: agent commits then drops thread.",
            "Add `new_eval` checking task-completion signal.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("affective", "performative_apology"): _pb(
        "affective",
        "performative_apology",
        "Performative apology -- signal care + acknowledge stakes",
        [
            "Detect signature: 'I'm sorry' lexical without substance.",
            "Add `signal_care` paired with `acknowledge_stakes`.",
        ],
        "1d",
        "McAllister 1995",
    ),
    ("balanced", "high_trust_baseline"): _pb(
        "balanced",
        "high_trust_baseline",
        "Balanced high trust -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "McAllister 1995",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("affective", "restate_user_emotion"): "absent_emotional_acknowledgement",
    ("affective", "signal_care"): "transactional_tone",
    ("affective", "personalize_response"): "generic_response",
    ("affective", "acknowledge_stakes"): "no_stakes_named",
    ("affective", "follow_up_check_in"): "no_follow_up",
    ("cognitive", "cite_sources"): "uncited_claims",
    ("cognitive", "show_reasoning"): "opaque_reasoning",
    ("cognitive", "confidence_calibration"): "overconfident_claims",
    ("cognitive", "new_eval"): "factual_errors",
    ("cognitive", "human_review"): "factual_errors",
}


def find_playbook(dimension: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((dimension, failure_mode))


def find_playbook_for_intervention(
    target_dimension: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_dimension, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_dimension, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
