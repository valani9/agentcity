"""Failure-mode playbooks for the Org-Structure Matrix diagnostic."""

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
    ("hierarchy", "too_flat_for_critical_task"): _pb(
        "hierarchy",
        "too_flat_for_critical_task",
        "Too flat for critical task -- add supervisor layer",
        [
            "Detect: incident-response or regulated-workflow crew has no clear escalation path.",
            "Apply `add_supervisor_layer` (e.g. incident commander role) +"
            " `shift_decision_authority`.",
        ],
        "1w",
        "Galbraith Star Model; Mintzberg 1983",
    ),
    ("hierarchy", "too_hierarchical_for_creative"): _pb(
        "hierarchy",
        "too_hierarchical_for_creative",
        "Too hierarchical for creative -- flatten hierarchy",
        [
            "Detect: creative_brainstorm or research_exploration crew has steep"
            " escalation that blocks divergent thinking.",
            "Apply `flatten_hierarchy` + `shift_decision_authority` to peers.",
        ],
        "1w",
        "Galbraith Star Model; Mintzberg 1983",
    ),
    ("centralization", "decision_bottleneck"): _pb(
        "centralization",
        "decision_bottleneck",
        "Decision bottleneck -- shift decision authority",
        [
            "Detect: single agent gates >50% of decisions; throughput collapses.",
            "Apply `shift_decision_authority` to grant peer decision rights in their domains.",
        ],
        "1w",
        "Galbraith Star Model",
    ),
    ("centralization", "no_clear_authority"): _pb(
        "centralization",
        "no_clear_authority",
        "No clear authority -- add routing layer",
        [
            "Detect: crew has no clear owner for critical decisions; thrash.",
            "Apply `add_routing_layer` + `shift_decision_authority` toward an explicit owner.",
        ],
        "1w",
        "Galbraith Star Model",
    ),
    ("specialization", "over_specialized"): _pb(
        "specialization",
        "over_specialized",
        "Over-specialized -- consolidate roles",
        [
            "Detect: many narrow specialists with high handoff overhead.",
            "Apply `consolidate_roles` to merge narrow specialists into full-stack generalists.",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("specialization", "under_specialized"): _pb(
        "specialization",
        "under_specialized",
        "Under-specialized -- split roles",
        [
            "Detect: same agents asked to do contradictory things (e.g. propose +"
            " judge); quality collapses.",
            "Apply `split_roles` to separate proposer from judge.",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("formalization", "under_formalized"): _pb(
        "formalization",
        "under_formalized",
        "Under-formalized -- add eval + new SOP",
        [
            "Detect: regulated_workflow crew freelancing without checklist.",
            "Apply `new_eval` + new SOP doc per task class.",
        ],
        "1d",
        "Mintzberg 1983",
    ),
    ("formalization", "over_formalized"): _pb(
        "formalization",
        "over_formalized",
        "Over-formalized -- remove routing layer",
        [
            "Detect: creative crew bogged down in handoffs.",
            "Apply `remove_routing_layer` + relax checklist for divergent tasks.",
        ],
        "1d",
        "Mintzberg 1983",
    ),
    ("departmentalization", "matrix_overhead"): _pb(
        "departmentalization",
        "matrix_overhead",
        "Matrix overhead -- regroup by product",
        [
            "Detect: matrix structure on small crew where dual reporting is confusion theatre.",
            "Apply `regroup_by_product` -- pick one primary grouping.",
        ],
        "1w",
        "Galbraith Star Model",
    ),
    ("span_of_control", "span_too_narrow"): _pb(
        "span_of_control",
        "span_too_narrow",
        "Span too narrow -- flatten hierarchy",
        [
            "Detect: every supervisor has 1-2 reports; tall thin tree.",
            "Apply `flatten_hierarchy` to widen spans.",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("span_of_control", "span_too_wide"): _pb(
        "span_of_control",
        "span_too_wide",
        "Span too wide -- add supervisor layer",
        [
            "Detect: one orchestrator managing 8+ direct reports; loses signal.",
            "Apply `add_supervisor_layer` (sub-team leads).",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("hierarchy", "broadly_misfit"): _pb(
        "hierarchy",
        "broadly_misfit",
        "Broadly misfit -- redesign + human review",
        [
            "Detect: 4+ dimensions misaligned; piecemeal fixes won't help.",
            "Apply `introduce_matrix` OR full redesign + `human_review`"
            " checkpoint before more changes.",
        ],
        "1m",
        "Galbraith Star Model",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str, str], str] = {
    ("hierarchy", "add_supervisor_layer", "increase"): "too_flat_for_critical_task",
    ("hierarchy", "flatten_hierarchy", "decrease"): "too_hierarchical_for_creative",
    ("centralization", "shift_decision_authority", "decrease"): "decision_bottleneck",
    ("centralization", "add_routing_layer", "increase"): "no_clear_authority",
    ("centralization", "shift_decision_authority", "increase"): "no_clear_authority",
    ("specialization", "consolidate_roles", "decrease"): "over_specialized",
    ("specialization", "split_roles", "increase"): "under_specialized",
    ("formalization", "new_eval", "increase"): "under_formalized",
    ("formalization", "remove_routing_layer", "decrease"): "over_formalized",
    ("departmentalization", "regroup_by_product", "redesign"): "matrix_overhead",
    ("departmentalization", "regroup_by_function", "redesign"): "matrix_overhead",
    ("departmentalization", "introduce_matrix", "redesign"): "broadly_misfit",
    ("span_of_control", "flatten_hierarchy", "increase"): "span_too_narrow",
    ("span_of_control", "add_supervisor_layer", "decrease"): "span_too_wide",
    ("hierarchy", "human_review", "redesign"): "broadly_misfit",
}


def find_playbook(dimension: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((dimension, failure_mode))


def find_playbook_for_intervention(
    target_dimension: str, intervention_type: str, direction: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get(
        (target_dimension, intervention_type, direction)
    )
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
