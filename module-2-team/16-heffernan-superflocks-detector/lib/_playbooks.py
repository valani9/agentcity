"""Failure-mode playbooks for Heffernan Superflocks."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    pattern: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        pattern=pattern,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("superflocks", "top_agent_monopoly"): _pb(
        "superflocks",
        "top_agent_monopoly",
        "Top-agent monopoly -- inject routing jitter + load floor",
        [
            "Detect signature: one agent receives >80% of decisions.",
            "Run `introduce_routing_jitter` + `load_balancing_floor`.",
            "Compose with `vstack.bias_stack`.",
        ],
        "1d",
        "Heffernan 2014; Page 2007",
    ),
    ("superflocks", "no_fallback"): _pb(
        "superflocks",
        "no_fallback",
        "No fallback coverage -- redundant routing + drills",
        [
            "Detect signature: secondary agents rarely or never receive tasks.",
            "Run `redundant_routing` for critical paths.",
            "Run `swap_top_agent_offline_drill` periodically.",
        ],
        "1d",
        "Heffernan 2014",
    ),
    ("superflocks", "complementarity_collapse"): _pb(
        "superflocks",
        "complementarity_collapse",
        "Complementarity collapse -- capability complement check",
        [
            "Detect signature: agents have complementary capabilities that go unused.",
            "Run `add_capability_complement_check` before routing.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Page 2007; Heffernan 2014",
    ),
    ("superflocks", "failure_clustering"): _pb(
        "superflocks",
        "failure_clustering",
        "Failure clustering on top -- rotate lead + drills",
        [
            "Detect signature: top agent failures cascade with no fallback.",
            "Run `rotate_lead_agent` + `swap_top_agent_offline_drill`.",
        ],
        "1w",
        "Heffernan 2014",
    ),
    ("concentrated", "concentrated_routing"): _pb(
        "concentrated",
        "concentrated_routing",
        "Concentrated routing -- introduce jitter",
        [
            "Detect signature: Gini > 0.5 but < 0.8.",
            "Run `introduce_routing_jitter`.",
            "Add `require_minimum_agent_diversity`.",
        ],
        "1d",
        "Heffernan 2014",
    ),
    ("robust", "baseline"): _pb(
        "robust",
        "baseline",
        "Robust baseline -- record + monitor drift",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_routing_eval`.",
            "Alert when fragility_score rises > 0.15.",
        ],
        "1h",
        "Heffernan 2014",
    ),
    ("superflocks", "narrow_capability_diversity"): _pb(
        "superflocks",
        "narrow_capability_diversity",
        "Narrow capability diversity -- add diverse agents",
        [
            "Detect signature: all agents score high on same dimension.",
            "Add `require_minimum_agent_diversity`.",
        ],
        "1w",
        "Page 2007",
    ),
    ("superflocks", "no_drill"): _pb(
        "superflocks",
        "no_drill",
        "No top-agent offline drill -- schedule periodic drills",
        [
            "Run `swap_top_agent_offline_drill` monthly.",
            "Measure system performance without the top agent.",
        ],
        "1h",
        "Heffernan 2014",
    ),
    ("concentrated", "no_routing_eval"): _pb(
        "concentrated",
        "no_routing_eval",
        "No routing eval -- add metric tracking",
        [
            "Add `add_routing_eval` measuring Gini + fragility over time.",
        ],
        "1h",
        "Heffernan 2014",
    ),
    ("superflocks", "human_review_needed"): _pb(
        "superflocks",
        "human_review_needed",
        "Severe superflocks -- escalate to human",
        [
            "Run `human_review` to redesign the routing strategy.",
            "Compose with `vstack.lewin` for environment-locus attribution.",
        ],
        "1w",
        "Heffernan 2014",
    ),
    ("concentrated", "imbalanced_capability"): _pb(
        "concentrated",
        "imbalanced_capability",
        "Imbalanced capability -- complement check + jitter",
        [
            "Compose `add_capability_complement_check` + `introduce_routing_jitter`.",
        ],
        "1d",
        "Page 2007",
    ),
    ("superflocks", "rotation_needed"): _pb(
        "superflocks",
        "rotation_needed",
        "Rotation needed -- explicit lead rotation",
        [
            "Run `rotate_lead_agent` on a schedule.",
            "Avoid permanent top-agent designation.",
        ],
        "1d",
        "Heffernan 2014",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("superflocks", "introduce_routing_jitter"): "top_agent_monopoly",
    ("superflocks", "load_balancing_floor"): "top_agent_monopoly",
    ("superflocks", "redundant_routing"): "no_fallback",
    ("superflocks", "swap_top_agent_offline_drill"): "no_fallback",
    ("superflocks", "add_capability_complement_check"): "complementarity_collapse",
    ("superflocks", "rotate_lead_agent"): "failure_clustering",
    ("superflocks", "require_minimum_agent_diversity"): "narrow_capability_diversity",
    ("superflocks", "human_review"): "human_review_needed",
    ("concentrated", "introduce_routing_jitter"): "concentrated_routing",
    ("concentrated", "add_routing_eval"): "no_routing_eval",
    ("robust", "new_eval"): "baseline",
}


def find_playbook(pattern: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((pattern, failure_mode))


def find_playbook_for_intervention(
    target_pattern: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_pattern, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_pattern, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
