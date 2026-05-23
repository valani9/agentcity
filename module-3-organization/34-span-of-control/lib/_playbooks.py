"""Failure-mode playbooks for the Span-of-Control diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    metric: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        metric=metric,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("max_span", "wide_span_orchestrator"): _pb(
        "max_span",
        "wide_span_orchestrator",
        "Wide span orchestrator -- split supervisor load",
        [
            "Detect: one supervisor has > 7 direct reports.",
            "Apply `split_supervisor_load` -- partition subordinates across"
            " 2-3 new sub-supervisors.",
        ],
        "1w",
        "Galbraith 1995; Mintzberg 1983",
    ),
    ("hierarchy_depth", "deep_hierarchy"): _pb(
        "hierarchy_depth",
        "deep_hierarchy",
        "Deep hierarchy -- flatten",
        [
            "Detect: longest reports_to chain > 3 levels.",
            "Apply `flatten_hierarchy` + `consolidate_supervisors` to remove"
            " low-leverage middle layers.",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("decision_bottleneck", "single_bottleneck"): _pb(
        "decision_bottleneck",
        "single_bottleneck",
        "Single bottleneck -- delegate decision authority",
        [
            "Detect: one agent has full authority + wide span; throughput collapses on load.",
            "Apply `delegate_decision_authority` to lieutenants.",
        ],
        "1w",
        "Galbraith 1995",
    ),
    ("decision_bottleneck", "load_amplified_bottleneck"): _pb(
        "decision_bottleneck",
        "load_amplified_bottleneck",
        "Load amplified bottleneck -- add redundant path",
        [
            "Detect: bottleneck score climbs with incoming_request_rate.",
            "Apply `add_redundant_path` so requests bypass the bottleneck under load.",
        ],
        "1w",
        "Galbraith 1995",
    ),
    ("span_gini", "imbalanced_supervisors"): _pb(
        "span_gini",
        "imbalanced_supervisors",
        "Imbalanced supervisors -- redistribute subordinates",
        [
            "Detect: one supervisor holds most subordinates while others hold few.",
            "Apply `redistribute_subordinates` to rebalance.",
        ],
        "1d",
        "Mintzberg 1983",
    ),
    ("centralization_index", "over_centralized"): _pb(
        "centralization_index",
        "over_centralized",
        "Over-centralized -- delegate decision authority",
        [
            "Detect: centralization index > 0.6; top supervisors hold all authority.",
            "Apply `delegate_decision_authority` to distributed peers.",
        ],
        "1w",
        "Galbraith 1995",
    ),
    ("centralization_index", "under_centralized"): _pb(
        "centralization_index",
        "under_centralized",
        "Under-centralized -- add supervisor layer",
        [
            "Detect: centralization index near 0; no one owns the decision.",
            "Apply `add_supervisor_layer` to introduce explicit decision owner.",
        ],
        "1w",
        "Galbraith 1995",
    ),
    ("mean_span", "over_layered"): _pb(
        "mean_span",
        "over_layered",
        "Over-layered -- consolidate supervisors",
        [
            "Detect: many supervisors with mean span < 2; layers add latency.",
            "Apply `consolidate_supervisors` + `flatten_hierarchy`.",
        ],
        "1w",
        "Mintzberg 1983",
    ),
    ("decision_bottleneck", "broadly_overloaded"): _pb(
        "decision_bottleneck",
        "broadly_overloaded",
        "Broadly overloaded -- human review + redesign",
        [
            "Detect: multiple metrics severely degraded; piecemeal fixes won't help.",
            "Apply `human_review` + full redesign of the org graph.",
        ],
        "1m",
        "Galbraith 1995",
    ),
    ("decision_bottleneck", "remove_bottleneck"): _pb(
        "decision_bottleneck",
        "remove_bottleneck",
        "Remove bottleneck -- restructure",
        [
            "Detect: bottleneck agent is structurally unavoidable but its role is dispensable.",
            "Apply `remove_bottleneck_agent` -- restructure so the role doesn't exist.",
        ],
        "1m",
        "Galbraith 1995",
    ),
    ("max_span", "new_eval"): _pb(
        "max_span",
        "new_eval",
        "Span regression eval -- add eval",
        [
            "Detect: structure changes silently break load handling.",
            "Apply `new_eval` -- gate org-graph changes by load test.",
        ],
        "1d",
        "Galbraith 1995",
    ),
    ("decision_bottleneck", "human_review"): _pb(
        "decision_bottleneck",
        "human_review",
        "Decision human-review -- add human review",
        [
            "Detect: bottleneck agent decisions are high-stakes / irreversible.",
            "Apply `human_review` checkpoint on the bottleneck's commit path.",
        ],
        "1d",
        "Galbraith 1995",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("max_span", "split_supervisor_load"): "wide_span_orchestrator",
    ("max_span", "add_supervisor_layer"): "wide_span_orchestrator",
    ("max_span", "new_eval"): "new_eval",
    ("hierarchy_depth", "flatten_hierarchy"): "deep_hierarchy",
    ("hierarchy_depth", "consolidate_supervisors"): "deep_hierarchy",
    ("decision_bottleneck", "delegate_decision_authority"): "single_bottleneck",
    ("decision_bottleneck", "add_redundant_path"): "load_amplified_bottleneck",
    ("decision_bottleneck", "remove_bottleneck_agent"): "remove_bottleneck",
    ("decision_bottleneck", "human_review"): "human_review",
    ("span_gini", "redistribute_subordinates"): "imbalanced_supervisors",
    ("centralization_index", "delegate_decision_authority"): "over_centralized",
    ("centralization_index", "add_supervisor_layer"): "under_centralized",
    ("mean_span", "consolidate_supervisors"): "over_layered",
    ("mean_span", "flatten_hierarchy"): "over_layered",
}


def find_playbook(metric: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((metric, failure_mode))


def find_playbook_for_intervention(
    target_metric: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_metric, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_metric, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
