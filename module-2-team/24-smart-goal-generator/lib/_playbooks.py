"""Failure-mode playbooks for the SMART Goal Generator."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    criterion: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        criterion=criterion,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("specific", "category_not_target"): _pb(
        "specific",
        "category_not_target",
        "Category, not target -- tighten specificity",
        [
            "Detect signature: 'improve X' instead of 'change X from A to B'.",
            "Add `tighten_specificity` requiring before/after target.",
        ],
        "1h",
        "Doran 1981",
    ),
    ("measurable", "no_measurement"): _pb(
        "measurable",
        "no_measurement",
        "No measurement -- add measurement",
        [
            "Detect signature: success metric without measurement_method.",
            "Add `add_measurement` requiring observable check.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("measurable", "qualitative_only"): _pb(
        "measurable",
        "qualitative_only",
        "Qualitative-only -- add measurement",
        [
            "Detect signature: metric is 'high quality' instead of '>= 0.85 rating'.",
            "Add `add_measurement` requiring numeric or boolean target.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("achievable", "unachievable_stretch"): _pb(
        "achievable",
        "unachievable_stretch",
        "Unachievable stretch -- calibrate achievability",
        [
            "Detect signature: goal exceeds available resources/constraints.",
            "Add `calibrate_achievability` requiring resource alignment.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("achievable", "no_kill_criteria"): _pb(
        "achievable",
        "no_kill_criteria",
        "No kill criteria -- add kill criteria",
        [
            "Detect signature: zero abandonment conditions.",
            "Add `add_kill_criteria` requiring budget + failure cascade triggers.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("relevant", "irrelevant_to_context"): _pb(
        "relevant",
        "irrelevant_to_context",
        "Irrelevant to context -- ground relevance",
        [
            "Detect signature: goal doesn't connect to user's actual problem.",
            "Add `ground_relevance` step tracing goal back to user need.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("relevant", "vanity_metric"): _pb(
        "relevant",
        "vanity_metric",
        "Vanity metric -- new eval",
        [
            "Detect signature: metric trivially optimizable without solving user problem.",
            "Add `new_eval` testing for real user-outcome change.",
        ],
        "1w",
        "Doran 1981",
    ),
    ("time_bound", "no_deadline"): _pb(
        "time_bound",
        "no_deadline",
        "No deadline -- add deadline",
        [
            "Detect signature: missing or 'ASAP' deadline.",
            "Add `add_deadline` requiring ISO date or token/cost budget.",
        ],
        "1h",
        "Doran 1981",
    ),
    ("time_bound", "ambiguous_deadline"): _pb(
        "time_bound",
        "ambiguous_deadline",
        "Ambiguous deadline -- add deadline",
        [
            "Detect signature: 'soon', 'this quarter' without a date.",
            "Add `add_deadline` requiring concrete deadline.",
        ],
        "1h",
        "Doran 1981",
    ),
    ("overall", "no_completion_criteria"): _pb(
        "overall",
        "no_completion_criteria",
        "No completion criteria -- add completion criteria",
        [
            "Detect signature: SMART spec without observable 'done' conditions.",
            "Add `add_completion_criteria`.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("overall", "weak_overall"): _pb(
        "overall",
        "weak_overall",
        "Weak overall -- decompose goal",
        [
            "Detect signature: overall_smart_score < 0.5 across multiple criteria.",
            "Add `decompose_goal` splitting into 2-3 smaller goals.",
            "Compose with `vstack.grpi`.",
        ],
        "1w",
        "Doran 1981",
    ),
    ("overall", "strong_baseline"): _pb(
        "overall",
        "strong_baseline",
        "Strong baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Doran 1981",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("specific", "tighten_specificity"): "category_not_target",
    ("measurable", "add_measurement"): "no_measurement",
    ("achievable", "calibrate_achievability"): "unachievable_stretch",
    ("achievable", "add_kill_criteria"): "no_kill_criteria",
    ("relevant", "ground_relevance"): "irrelevant_to_context",
    ("relevant", "new_eval"): "vanity_metric",
    ("time_bound", "add_deadline"): "no_deadline",
    ("overall", "add_completion_criteria"): "no_completion_criteria",
    ("overall", "decompose_goal"): "weak_overall",
}


def find_playbook(criterion: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((criterion, failure_mode))


def find_playbook_for_intervention(
    target_criterion: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_criterion, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_criterion, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
