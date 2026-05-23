"""Failure-mode playbooks for the Group Decision Models generator."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    model: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        model=model,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("consensus", "overused_low_stakes"): _pb(
        "consensus",
        "overused_low_stakes",
        "Consensus overused for low stakes -- switch to majority",
        [
            "Detect signature: consensus chosen for reversible low-stakes decision.",
            "Add `switch_to_majority` lowering coordination cost.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("majority", "buyin_undermined"): _pb(
        "majority",
        "buyin_undermined",
        "Majority when buy-in needed -- switch to consensus or fist-to-five",
        [
            "Detect signature: 49% minority must act on the decision.",
            "Add `switch_to_consensus` or `switch_to_fist_to_five`.",
            "Compose with `agentcity.lencioni`.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("concurring", "buyin_required"): _pb(
        "concurring",
        "buyin_required",
        "Concurring when buy-in needed -- switch to consensus",
        [
            "Detect signature: single decisive vote when team must act.",
            "Add `switch_to_consensus`.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("fist_to_five", "underused"): _pb(
        "fist_to_five",
        "underused",
        "Fist-to-five underused -- switch to fist-to-five",
        [
            "Detect signature: degree of agreement matters but only yes/no used.",
            "Add `switch_to_fist_to_five` surfacing lukewarm support.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("unanimous", "blocked_indefinitely"): _pb(
        "unanimous",
        "blocked_indefinitely",
        "Unanimous when one voter blocks -- add fallback",
        [
            "Detect signature: 1 of N agents blocks all options.",
            "Add `add_fallback` to consensus or fist-to-five.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("majority", "no_quorum"): _pb(
        "majority",
        "no_quorum",
        "Majority without quorum -- add quorum",
        [
            "Detect signature: majority decisions with <50% of agents voting.",
            "Add `add_quorum` requiring at least ceil(N/2) voters.",
        ],
        "1h",
        "Kaner 2014",
    ),
    ("majority", "no_tie_breaker"): _pb(
        "majority",
        "no_tie_breaker",
        "Majority without tie-breaker -- add tie-breaker",
        [
            "Detect signature: majority protocol with no explicit tie-breaker.",
            "Add `add_tie_breaker` (confidence weight, fallback model).",
        ],
        "1h",
        "Kaner 2014",
    ),
    ("consensus", "no_fallback"): _pb(
        "consensus",
        "no_fallback",
        "Consensus without fallback -- add fallback",
        [
            "Detect signature: consensus protocol with no escape hatch.",
            "Add `add_fallback` to fist-to-five or majority.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("fist_to_five", "soft_block_ignored"): _pb(
        "fist_to_five",
        "soft_block_ignored",
        "Soft block ignored -- tighten threshold",
        [
            "Detect signature: scores of 1 (close to block) ignored at mean threshold.",
            "Add `tighten_threshold` requiring no scores <= 1.",
        ],
        "1h",
        "Kaner 2014",
    ),
    ("concurring", "high_stakes_irreversible"): _pb(
        "concurring",
        "high_stakes_irreversible",
        "Concurring on high-stakes -- switch to consensus or unanimous",
        [
            "Detect signature: concurring chosen for irreversible high-stakes decision.",
            "Add `switch_to_consensus` or `switch_to_unanimous`.",
        ],
        "1d",
        "Kaner 2014",
    ),
    ("overall", "good_fit_baseline"): _pb(
        "overall",
        "good_fit_baseline",
        "Good fit baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Kaner 2014",
    ),
    ("overall", "ambiguous_protocol"): _pb(
        "overall",
        "ambiguous_protocol",
        "Ambiguous protocol -- new eval + human review",
        [
            "Detect signature: protocol_steps under-specify the procedure.",
            "Add `new_eval`; for high stakes, add `human_review`.",
        ],
        "1w",
        "Kaner 2014",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("model", "switch_to_majority"): "overused_low_stakes",
    ("model", "switch_to_consensus"): "buyin_undermined",
    ("model", "switch_to_fist_to_five"): "underused",
    ("model", "switch_to_unanimous"): "high_stakes_irreversible",
    ("model", "switch_to_concurring"): "buyin_required",
    ("quorum", "add_quorum"): "no_quorum",
    ("tie_breaker", "add_tie_breaker"): "no_tie_breaker",
    ("fallback", "add_fallback"): "no_fallback",
    ("threshold", "tighten_threshold"): "soft_block_ignored",
    ("overall", "new_eval"): "ambiguous_protocol",
    ("overall", "human_review"): "ambiguous_protocol",
}


# The failure_mode lookup table is indexed by the (model_key) -> playbook key.
# We map intervention->playbook through the model that the failure_mode belongs to.
_MODEL_FOR_FAILURE_MODE: dict[str, str] = {
    "overused_low_stakes": "consensus",
    "buyin_undermined": "majority",
    "underused": "fist_to_five",
    "high_stakes_irreversible": "concurring",
    "buyin_required": "concurring",
    "no_quorum": "majority",
    "no_tie_breaker": "majority",
    "no_fallback": "consensus",
    "soft_block_ignored": "fist_to_five",
    "ambiguous_protocol": "overall",
    "blocked_indefinitely": "unanimous",
}


def find_playbook(model: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((model, failure_mode))


def find_playbook_for_intervention(
    target_dimension: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_dimension, intervention_type))
    if not failure_mode:
        return None
    model = _MODEL_FOR_FAILURE_MODE.get(failure_mode, "overall")
    return PLAYBOOKS.get((model, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
