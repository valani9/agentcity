"""Failure-mode playbooks for the Devil's Advocate Role Separator."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    phase: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        phase=phase,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("external_critique", "missing_critic_phase"): _pb(
        "external_critique",
        "missing_critic_phase",
        "Missing critic phase -- add critic agent",
        [
            "Detect signature: no external_critique phase in the trace.",
            "Add `add_critic_agent` for a distinct critic role.",
            "Compose with `vstack.debate_pathology`.",
        ],
        "1d",
        "Janis 1972; Schwenk 1990",
    ),
    ("self_evaluate", "rubber_stamping"): _pb(
        "self_evaluate",
        "rubber_stamping",
        "Rubber-stamping -- structured self-critique",
        [
            "Detect signature: agent approves own work without revision.",
            "Add `structured_self_critique` requiring N substantive objections.",
        ],
        "1d",
        "Janis 1972",
    ),
    ("plan", "no_alternative_hypothesis"): _pb(
        "plan",
        "no_alternative_hypothesis",
        "No alternative hypothesis -- alternative hypothesis step",
        [
            "Detect signature: plan considers only one approach.",
            "Add `alternative_hypothesis_step` requiring 2+ alternatives.",
            "Compose with `vstack.bias_stack`.",
        ],
        "1d",
        "Schwenk 1990",
    ),
    ("plan", "no_pre_mortem"): _pb(
        "plan",
        "no_pre_mortem",
        "No pre-mortem -- pre-mortem step",
        [
            "Detect signature: no anticipation of failure modes.",
            "Add `pre_mortem_step` asking 'how will this fail?' before commit.",
        ],
        "1d",
        "Klein 2007 pre-mortem",
    ),
    ("execute", "no_red_team"): _pb(
        "execute",
        "no_red_team",
        "No red team -- red team loop",
        [
            "Detect signature: execution proceeds without adversarial test.",
            "Add `red_team_loop` simulating attack/break scenarios.",
        ],
        "1w",
        "Schwenk 1990",
    ),
    ("external_critique", "weak_critic"): _pb(
        "external_critique",
        "weak_critic",
        "Weak critic -- devil's advocate prompt",
        [
            "Detect signature: critic exists but objections are non-substantive.",
            "Add `devils_advocate_prompt` ('argue against this plan').",
        ],
        "1d",
        "Janis 1972",
    ),
    ("external_critique", "fully_conflated"): _pb(
        "external_critique",
        "fully_conflated",
        "Fully conflated -- external review gate",
        [
            "Detect signature: same actor plans + executes + judges.",
            "Add `external_review_gate` before commit.",
        ],
        "1w",
        "Janis 1972",
    ),
    ("external_critique", "high_stakes_no_human"): _pb(
        "external_critique",
        "high_stakes_no_human",
        "High stakes, no human -- human review",
        [
            "Detect signature: fully conflated roles on high-stakes task.",
            "Add `human_review` checkpoint.",
        ],
        "1w",
        "Janis 1972",
    ),
    ("self_evaluate", "no_self_critique"): _pb(
        "self_evaluate",
        "no_self_critique",
        "No self-critique -- structured self-critique",
        [
            "Detect signature: self_evaluate phase absent entirely.",
            "Add `structured_self_critique` step before commit.",
        ],
        "1d",
        "Janis 1972",
    ),
    ("plan", "weak_plan"): _pb(
        "plan",
        "weak_plan",
        "Weak plan -- pre-mortem + alternatives",
        [
            "Detect signature: plan substantive score < 0.4.",
            "Add `pre_mortem_step` and `alternative_hypothesis_step`.",
        ],
        "1d",
        "Klein 2007; Schwenk 1990",
    ),
    ("self_evaluate", "approval_drift"): _pb(
        "self_evaluate",
        "approval_drift",
        "Approval drift -- new eval",
        [
            "Detect signature: approval rate climbed over time.",
            "Add `new_eval` tracking approval-rate trend.",
        ],
        "1w",
        "Janis 1972",
    ),
    ("external_critique", "well_separated_baseline"): _pb(
        "external_critique",
        "well_separated_baseline",
        "Well-separated baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Janis 1972",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("external_critique", "add_critic_agent"): "missing_critic_phase",
    ("external_critique", "devils_advocate_prompt"): "weak_critic",
    ("external_critique", "external_review_gate"): "fully_conflated",
    ("external_critique", "human_review"): "high_stakes_no_human",
    ("self_evaluate", "structured_self_critique"): "rubber_stamping",
    ("self_evaluate", "new_eval"): "approval_drift",
    ("plan", "alternative_hypothesis_step"): "no_alternative_hypothesis",
    ("plan", "pre_mortem_step"): "no_pre_mortem",
    ("execute", "red_team_loop"): "no_red_team",
}


def find_playbook(phase: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((phase, failure_mode))


def find_playbook_for_intervention(
    target_phase: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_phase, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_phase, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
