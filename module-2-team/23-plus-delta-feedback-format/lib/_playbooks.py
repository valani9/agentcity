"""Failure-mode playbooks for the Plus/Delta feedback generator."""

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
    ("plus", "generic_affirmation"): _pb(
        "plus",
        "generic_affirmation",
        "Generic affirmation -- tighten specificity",
        [
            "Detect signature: 'good work', 'nice job', 'great structure'.",
            "Add `tighten_specificity` requiring behavioral observation.",
        ],
        "1h",
        "Joiner Associates 1990s; Brown 2018",
    ),
    ("plus", "no_evidence"): _pb(
        "plus",
        "no_evidence",
        "Plus without evidence -- require evidence",
        [
            "Detect signature: plus item with no quoted artifact element.",
            "Add `require_evidence` validation step.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("plus", "no_keep_doing"): _pb(
        "plus",
        "no_keep_doing",
        "Plus without keep-doing -- add commitment",
        [
            "Detect signature: plus has no reusable instruction for next time.",
            "Add `add_commitment` step requiring keep_doing field.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("delta", "generic_critique"): _pb(
        "delta",
        "generic_critique",
        "Generic critique -- tighten specificity",
        [
            "Detect signature: 'could be better', 'needs improvement'.",
            "Add `tighten_specificity` requiring behavioral change.",
        ],
        "1h",
        "Brown 2018",
    ),
    ("delta", "no_alternative"): _pb(
        "delta",
        "no_alternative",
        "Delta without alternative -- require alternative",
        [
            "Detect signature: delta says what to change but not how.",
            "Add `require_alternative` field validation.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("delta", "severity_uncalibrated"): _pb(
        "delta",
        "severity_uncalibrated",
        "Severity uncalibrated -- escalate / deescalate",
        [
            "Detect signature: trivial deltas marked critical, or critical deltas marked nit.",
            "Add `escalate_severity` / `deescalate_severity` rules.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("overall", "style_misaligned"): _pb(
        "overall",
        "style_misaligned",
        "Style misaligned -- balance style",
        [
            "Detect signature: 5 pluses + 1 delta when style='delta-leaning'.",
            "Add `balance_style` enforcement step.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("overall", "rework_recommendation_lacks_alternatives"): _pb(
        "overall",
        "rework_recommendation_lacks_alternatives",
        "Rework recommended but no alternatives -- require alternative",
        [
            "Detect signature: overall=rework but delta items lack alternatives.",
            "Add `require_alternative` rule.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("specificity", "generic_phrase_inventory"): _pb(
        "specificity",
        "generic_phrase_inventory",
        "Generic phrase inventory -- new eval",
        [
            "Maintain phrase blocklist ('good work', 'nice', etc.).",
            "Add `new_eval` rejecting feedback containing blocklist phrases.",
        ],
        "1w",
        "Joiner Associates 1990s",
    ),
    ("specificity", "low_evidence_density"): _pb(
        "specificity",
        "low_evidence_density",
        "Low evidence density -- require evidence",
        [
            "Detect signature: < 50% of items cite specific artifact elements.",
            "Add `require_evidence` step.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("overall", "no_commitments"): _pb(
        "overall",
        "no_commitments",
        "No commitments -- add commitment",
        [
            "Detect signature: feedback has no follow-up commitments.",
            "Add `add_commitment` step requiring at least one commitment.",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Brown 2018",
    ),
    ("overall", "balanced_baseline"): _pb(
        "overall",
        "balanced_baseline",
        "Balanced baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on quality drift > 0.15.",
        ],
        "1h",
        "Brown 2018",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("plus", "tighten_specificity"): "generic_affirmation",
    ("plus", "require_evidence"): "no_evidence",
    ("plus", "add_commitment"): "no_keep_doing",
    ("delta", "tighten_specificity"): "generic_critique",
    ("delta", "require_alternative"): "no_alternative",
    ("delta", "escalate_severity"): "severity_uncalibrated",
    ("delta", "deescalate_severity"): "severity_uncalibrated",
    ("overall", "balance_style"): "style_misaligned",
    ("overall", "require_alternative"): "rework_recommendation_lacks_alternatives",
    ("overall", "add_commitment"): "no_commitments",
    ("specificity", "new_eval"): "generic_phrase_inventory",
    ("specificity", "require_evidence"): "low_evidence_density",
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
