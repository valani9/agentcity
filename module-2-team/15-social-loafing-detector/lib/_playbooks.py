"""Failure-mode playbooks for Social Loafing."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    role: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        role=role,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("loafer", "rubber_stamp"): _pb(
        "loafer",
        "rubber_stamp",
        "Rubber-stamp loafer -- assign subgoals + individual accountability",
        [
            "Detect signature: 80%+ of agent's messages are 'approval'/'paraphrase'.",
            "Run `assign_subgoals` + `individual_accountability`.",
            "Compose with `vstack.grpi` (clarify role).",
        ],
        "1d",
        "Latané-Williams-Harkins 1979; Williams-Harkins-Latané 1981",
    ),
    ("loafer", "silent_majority"): _pb(
        "loafer",
        "silent_majority",
        "Silent agent -- decompose task + per-agent evaluation",
        [
            "Detect signature: 0-2 messages despite N-agent team.",
            "Run `decompose_task` + `per_agent_evaluation`.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Karau-Williams 1993",
    ),
    ("absent", "no_contribution"): _pb(
        "absent",
        "no_contribution",
        "Absent agent -- remove or re-assign",
        [
            "Detect signature: 0 messages.",
            "Run `remove_loafer` if persistent.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Latané-Williams-Harkins 1979",
    ),
    ("team", "ringelmann_dilution"): _pb(
        "team",
        "ringelmann_dilution",
        "Ringelmann dilution -- smaller team",
        [
            "Detect signature: team size >= 5 with Gini > 0.5.",
            "Run `smaller_team`.",
            "Compose with `vstack.process_gain_loss`.",
        ],
        "1d",
        "Hackman-Vidmar 1970; Ingham et al 1974 Ringelmann",
    ),
    ("team", "anonymous_evaluation"): _pb(
        "team",
        "anonymous_evaluation",
        "Anonymous evaluation -- add identifiability signal",
        [
            "Detect signature: no per-agent evaluation in pipeline.",
            "Run `add_identifiability_signal` + `add_per_agent_metrics`.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Williams-Harkins-Latané 1981",
    ),
    ("loafer", "paraphrase_only"): _pb(
        "loafer",
        "paraphrase_only",
        "Paraphrase-only loafer -- explicit critic role",
        [
            "Detect signature: agent paraphrases predecessor without adding signal.",
            "Run `explicit_critic_assignment` for that agent.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Comer 1995",
    ),
    ("loafer", "approval_only"): _pb(
        "loafer",
        "approval_only",
        "Approval-only loafer -- rotate roles",
        [
            "Detect signature: agent only emits approval messages.",
            "Run `rotate_roles` so the same agent doesn't always approve.",
        ],
        "1d",
        "Karau-Williams 1993",
    ),
    ("team", "all_loafers"): _pb(
        "team",
        "all_loafers",
        "All-loafer team -- broad redesign",
        [
            "Detect signature: every agent has loafing_score > 0.5.",
            "Reassess team design (`smaller_team`, decompose, or use single best).",
            "Compose with `vstack.process_gain_loss`.",
        ],
        "1w",
        "Steiner 1972; Karau-Williams 1993",
    ),
    ("loafer", "high_team_low_individual"): _pb(
        "loafer",
        "high_team_low_individual",
        "High team output despite low contribution -- per-agent metrics",
        [
            "Detect signature: team succeeded but agent contributed <10%.",
            "Add `add_per_agent_metrics` to expose the imbalance.",
        ],
        "1h",
        "Williams-Harkins-Latané 1981",
    ),
    ("loafer", "single_dominant"): _pb(
        "loafer",
        "single_dominant",
        "Single-dominant pattern -- subgoals for others",
        [
            "Detect signature: 1 agent does >70% of work.",
            "Run `assign_subgoals` for the other agents.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Latané-Williams-Harkins 1979",
    ),
    ("primary-contributor", "well_balanced"): _pb(
        "primary-contributor",
        "well_balanced",
        "Well-balanced team -- record baseline",
        [
            "Use `record_baseline(detection, path)`.",
            "Add eval to maintain balance over time.",
        ],
        "1h",
        "Hackman 2002",
    ),
    ("team", "two_contributors_n_loafers"): _pb(
        "team",
        "two_contributors_n_loafers",
        "Two contributors + N loafers -- prune team or assign subgoals",
        [
            "Detect signature: 2 agents > 0.3 share, rest < 0.1.",
            "Either prune (`smaller_team`) or `assign_subgoals` to loafers.",
        ],
        "1d",
        "Karau-Williams 1993",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("loafer", "assign_subgoals"): "rubber_stamp",
    ("loafer", "individual_accountability"): "rubber_stamp",
    ("loafer", "decompose_task"): "silent_majority",
    ("loafer", "per_agent_evaluation"): "silent_majority",
    ("loafer", "remove_loafer"): "no_contribution",
    ("loafer", "explicit_critic_assignment"): "paraphrase_only",
    ("loafer", "rotate_roles"): "approval_only",
    ("team", "smaller_team"): "ringelmann_dilution",
    ("team", "add_identifiability_signal"): "anonymous_evaluation",
    ("team", "add_per_agent_metrics"): "anonymous_evaluation",
}


def find_playbook(role: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((role, failure_mode))


def find_playbook_for_intervention(
    target_role: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_role, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_role, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
