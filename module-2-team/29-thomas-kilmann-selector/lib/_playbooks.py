"""Failure-mode playbooks for the Thomas-Kilmann selector."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    style: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        style=style,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("competing", "wrong_context"): _pb(
        "competing",
        "wrong_context",
        "Competing used in collaborative context -- style router",
        [
            "Detect signature: high-assertion + low-cooperation in brainstorm/build.",
            "Add `style_router` switching to collaborating in build contexts.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("accommodating", "wrong_context"): _pb(
        "accommodating",
        "wrong_context",
        "Accommodating used when competing needed -- calibrate assertiveness",
        [
            "Detect signature: high-coop + low-assertion in safety/policy context.",
            "Add `calibrate_assertiveness` prompt patch.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("avoiding", "wrong_context"): _pb(
        "avoiding",
        "wrong_context",
        "Avoiding when collaboration needed -- task-specific persona",
        [
            "Detect signature: agent withdraws/abstains in build context.",
            "Add `task_specific_persona` requiring engaged collaboration.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("compromising", "default_choice"): _pb(
        "compromising",
        "default_choice",
        "Default compromising -- context classifier",
        [
            "Detect signature: agent picks compromising regardless of context.",
            "Add `context_classifier` routing by task category.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("collaborating", "wrong_for_urgent"): _pb(
        "collaborating",
        "wrong_for_urgent",
        "Collaborating used when speed needed -- style router",
        [
            "Detect signature: extended collaboration on time-pressured decision.",
            "Add `style_router` switching to competing/compromising under time pressure.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("competing", "all_contexts"): _pb(
        "competing",
        "all_contexts",
        "Competing in all contexts -- rigid single style",
        [
            "Detect signature: agent uses competing across diverse task categories.",
            "Add `style_router` + `task_specific_persona`.",
        ],
        "1w",
        "Thomas & Kilmann 1974",
    ),
    ("accommodating", "all_contexts"): _pb(
        "accommodating",
        "all_contexts",
        "Accommodating in all contexts -- rigid single style",
        [
            "Detect signature: agent always accommodates (sycophancy adjacent).",
            "Add `style_router` + `calibrate_assertiveness`.",
            "Compose with `agentcity.trust_triangle`.",
        ],
        "1w",
        "Thomas & Kilmann 1974; Sharma 2023",
    ),
    ("avoiding", "abandonment"): _pb(
        "avoiding",
        "abandonment",
        "Avoiding -> abandonment -- scaffold change",
        [
            "Detect signature: agent withdraws from any pushback.",
            "Add `scaffold_change` requiring engagement before escalation.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
    ("collaborating", "well_matched"): _pb(
        "collaborating",
        "well_matched",
        "Well-matched baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on mismatch drift > 0.15.",
        ],
        "1h",
        "Thomas & Kilmann 1974",
    ),
    ("compromising", "well_matched"): _pb(
        "compromising",
        "well_matched",
        "Compromising appropriate -- monitor",
        [
            "Use `record_baseline`; add `new_eval` for context calibration.",
        ],
        "1h",
        "Thomas & Kilmann 1974",
    ),
    ("competing", "high_stakes"): _pb(
        "competing",
        "high_stakes",
        "Competing on high stakes -- human review",
        [
            "Detect signature: aggressive competing on irreversible decision.",
            "Add `human_review` checkpoint.",
        ],
        "1w",
        "Thomas & Kilmann 1974",
    ),
    ("avoiding", "mixed_inconsistent"): _pb(
        "avoiding",
        "mixed_inconsistent",
        "Inconsistent style -- prompt patch",
        [
            "Detect signature: style flips repeatedly across the trace.",
            "Add `prompt_patch` anchoring style to task category.",
        ],
        "1d",
        "Thomas & Kilmann 1974",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("competing", "style_router"): "wrong_context",
    ("accommodating", "calibrate_assertiveness"): "wrong_context",
    ("avoiding", "task_specific_persona"): "wrong_context",
    ("compromising", "context_classifier"): "default_choice",
    ("collaborating", "style_router"): "wrong_for_urgent",
    ("competing", "human_review"): "high_stakes",
    ("avoiding", "scaffold_change"): "abandonment",
    ("avoiding", "prompt_patch"): "mixed_inconsistent",
}


def find_playbook(style: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((style, failure_mode))


def find_playbook_for_intervention(
    observed_style: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((observed_style, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((observed_style, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
