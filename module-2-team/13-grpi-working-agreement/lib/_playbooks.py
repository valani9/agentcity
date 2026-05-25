"""Failure-mode playbooks for the GRPI Working Agreement."""

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
    ("goals", "vague_primary_goal"): _pb(
        "goals",
        "vague_primary_goal",
        "Vague primary goal -- run SMART-rewrite",
        [
            "Identify the abstract verbs ('improve', 'optimize', 'support').",
            "Compose with `vstack.smart_goal` to rewrite as specific/measurable.",
            "Add at least 3 measurable success criteria.",
        ],
        "1d",
        "Beckhard 1972; Locke-Latham 1990",
    ),
    ("goals", "missing_kill_criteria"): _pb(
        "goals",
        "missing_kill_criteria",
        "Missing kill criteria -- add abandonment threshold",
        [
            "Define quantitative kill criteria (e.g. cost cap, time cap, defect threshold).",
            "Add explicit fallback action when kill criteria are hit.",
        ],
        "1h",
        "Hackman 2002",
    ),
    ("roles", "ambiguous_decision_rights"): _pb(
        "roles",
        "ambiguous_decision_rights",
        "Ambiguous decision rights -- disambiguate",
        [
            "Audit which decisions are owned by which agent.",
            "Use RACI: Responsible / Accountable / Consulted / Informed.",
            "Compose with `vstack.mcgregor` for orchestrator-mode review.",
        ],
        "1d",
        "Rubin-Plovnick-Fry 1977",
    ),
    ("roles", "overlapping_responsibilities"): _pb(
        "roles",
        "overlapping_responsibilities",
        "Overlapping responsibilities -- assign owners",
        [
            "Detect signature: same workstream owned by 2+ agents.",
            "Pick a single owner; the other agent becomes Consulted.",
            "Update RACI summary.",
        ],
        "1d",
        "Beckhard 1972; Hackman 2002",
    ),
    ("processes", "missing_escalation_path"): _pb(
        "processes",
        "missing_escalation_path",
        "Missing escalation path -- add explicit chain",
        [
            "Define 2-3 level escalation chain.",
            "Specify trigger conditions per level.",
            "Compose with `vstack.mcgregor` for human-elevation triggers.",
        ],
        "1h",
        "Hackman 2002",
    ),
    ("processes", "no_abandonment_criteria"): _pb(
        "processes",
        "no_abandonment_criteria",
        "No abandonment criteria -- add explicit cutoffs",
        [
            "Define quantitative cutoffs (time, cost, defect rate).",
            "Specify the fallback action when cutoffs are hit.",
        ],
        "1h",
        "Beckhard 1972; Salas et al 2018",
    ),
    ("interactions", "weak_disagreement_norms"): _pb(
        "interactions",
        "weak_disagreement_norms",
        "Weak disagreement norms -- codify productive disagreement",
        [
            "Add explicit disagreement protocol (e.g. devil's advocate; structured dissent).",
            "Compose with `vstack.devils_advocate`.",
            "Add psychological-safety commitments.",
        ],
        "1d",
        "Edmondson 1999; Lencioni 2002",
    ),
    ("interactions", "weak_psych_safety"): _pb(
        "interactions",
        "weak_psych_safety",
        "Weak psychological safety -- codify commitments",
        [
            "Add Edmondson-style safety commitments.",
            "Define feedback format (plus/delta / SBI).",
            "Compose with `vstack.psych_safety`.",
        ],
        "1d",
        "Edmondson 1999",
    ),
    ("goals", "no_measurable_criteria"): _pb(
        "goals",
        "no_measurable_criteria",
        "No measurable criteria -- add observable success metrics",
        [
            "Translate qualitative criteria into observable metrics.",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Beckhard 1972; Locke-Latham 1990",
    ),
    ("roles", "single_agent_overload"): _pb(
        "roles",
        "single_agent_overload",
        "Single-agent overload -- decompose role",
        [
            "Detect signature: one agent owns >50% of decision rights.",
            "Decompose into sub-roles assigned to other agents.",
            "Compose with `vstack.yerkes_dodson` (workload review).",
        ],
        "1w",
        "Hackman 2002; Yerkes-Dodson 1908",
    ),
    ("processes", "no_review_cadence"): _pb(
        "processes",
        "no_review_cadence",
        "No review cadence -- add periodic AAR",
        [
            "Specify review cadence (e.g. after every milestone).",
            "Compose with `vstack.aar`.",
        ],
        "1h",
        "Salas et al 2018",
    ),
    ("framework", "framework_misfit"): _pb(
        "framework",
        "framework_misfit",
        "Framework misfit -- align agreement with orchestration framework",
        [
            "Match decision protocol to framework (e.g. CrewAI hierarchical vs sequential).",
            "Align escalation path with framework's agent topology.",
            "Compose with `vstack.mcgregor`.",
        ],
        "1w",
        "Wang et al 2023 Cooperative LLM Agents",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("goals", "tighten_goals"): "vague_primary_goal",
    ("goals", "add_kill_criteria"): "missing_kill_criteria",
    ("roles", "clarify_roles"): "ambiguous_decision_rights",
    ("roles", "disambiguate_decision_rights"): "ambiguous_decision_rights",
    ("processes", "add_escalation_path"): "missing_escalation_path",
    ("processes", "tighten_processes"): "no_abandonment_criteria",
    ("interactions", "strengthen_interactions"): "weak_disagreement_norms",
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
