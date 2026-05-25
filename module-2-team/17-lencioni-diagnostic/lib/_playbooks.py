"""Failure-mode playbooks for the Lencioni Five Dysfunctions diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    dysfunction: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        dysfunction=dysfunction,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("absence-of-trust", "low_trust_signals"): _pb(
        "absence-of-trust",
        "low_trust_signals",
        "Foundation trust low -- add psychological-safety signal",
        [
            "Detect signature: no vulnerability shown; no error admission.",
            "Add `add_psych_safety_signal` to the system prompt.",
            "Compose with `vstack.psych_safety`, `vstack.trust_triangle`.",
        ],
        "1d",
        "Lencioni 2002; Edmondson 1999",
    ),
    ("fear-of-conflict", "artificial_harmony"): _pb(
        "fear-of-conflict",
        "artificial_harmony",
        "Artificial harmony -- structured dissent protocol",
        [
            "Detect signature: zero challenge messages despite disagreement.",
            "Add `structured_dissent_protocol` (1 mandatory dissent per decision).",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Lencioni 2002",
    ),
    ("lack-of-commitment", "ambiguous_decisions"): _pb(
        "lack-of-commitment",
        "ambiguous_decisions",
        "Ambiguous decisions -- communication protocol",
        [
            "Detect signature: decisions made but not explicit; no buy-in step.",
            "Add `communication_protocol` requiring explicit commit/dissent.",
            "Compose with `vstack.grpi`, `vstack.smart_goal`.",
        ],
        "1d",
        "Lencioni 2002",
    ),
    ("avoidance-of-accountability", "peer_accountability_gap"): _pb(
        "avoidance-of-accountability",
        "peer_accountability_gap",
        "Peer-accountability gap -- role assignment + eval",
        [
            "Detect signature: no peer-to-peer feedback observed.",
            "Add `role_assignment` for explicit peer reviewers.",
            "Compose with `vstack.plus_delta`.",
        ],
        "1d",
        "Lencioni 2002",
    ),
    ("inattention-to-results", "individual_optimization"): _pb(
        "inattention-to-results",
        "individual_optimization",
        "Individual optimization -- new eval on team metric",
        [
            "Detect signature: agents optimize personal metrics, not team outcome.",
            "Add `new_eval` measuring shared outcome.",
            "Compose with `vstack.grpi`, `vstack.aar`.",
        ],
        "1w",
        "Lencioni 2002; Hackman 2002",
    ),
    ("absence-of-trust", "no_vulnerability"): _pb(
        "absence-of-trust",
        "no_vulnerability",
        "No vulnerability -- prompt patch",
        [
            "Run `prompt_patch` adding 'admit uncertainty when present'.",
        ],
        "1h",
        "Lencioni 2002",
    ),
    ("fear-of-conflict", "false_consensus"): _pb(
        "fear-of-conflict",
        "false_consensus",
        "False consensus -- explicit critic role",
        [
            "Add `role_assignment` for a critic agent.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Lencioni 2002; Janis 1972 groupthink",
    ),
    ("lack-of-commitment", "drifting_priorities"): _pb(
        "lack-of-commitment",
        "drifting_priorities",
        "Drifting priorities -- scaffold change",
        [
            "Run `scaffold_change` adding explicit goal anchor in each turn.",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Lencioni 2002",
    ),
    ("avoidance-of-accountability", "blame_diffusion"): _pb(
        "avoidance-of-accountability",
        "blame_diffusion",
        "Blame diffusion -- communication protocol + AAR",
        [
            "Add `communication_protocol` for explicit ownership.",
            "Compose with `vstack.aar`.",
        ],
        "1d",
        "Lencioni 2002",
    ),
    ("inattention-to-results", "metric_gaming"): _pb(
        "inattention-to-results",
        "metric_gaming",
        "Metric gaming -- new eval + team comp change",
        [
            "Run `new_eval` exposing the gaming.",
            "Consider `team_composition_change`.",
            "Compose with `vstack.bias_stack`.",
        ],
        "1w",
        "Lencioni 2002; Casper 2023",
    ),
    ("none-observed", "healthy_baseline"): _pb(
        "none-observed",
        "healthy_baseline",
        "Healthy baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Lencioni 2002",
    ),
    ("full-pyramid", "all_levels_dysfunctional"): _pb(
        "full-pyramid",
        "all_levels_dysfunctional",
        "Full-pyramid dysfunction -- human review",
        [
            "Run `human_review` for full team redesign.",
            "Compose with `vstack.grpi` for rebuild.",
        ],
        "1w",
        "Lencioni 2002",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("absence-of-trust", "add_psych_safety_signal"): "low_trust_signals",
    ("absence-of-trust", "prompt_patch"): "no_vulnerability",
    ("fear-of-conflict", "structured_dissent_protocol"): "artificial_harmony",
    ("fear-of-conflict", "role_assignment"): "false_consensus",
    ("lack-of-commitment", "communication_protocol"): "ambiguous_decisions",
    ("lack-of-commitment", "scaffold_change"): "drifting_priorities",
    ("avoidance-of-accountability", "role_assignment"): "peer_accountability_gap",
    ("avoidance-of-accountability", "communication_protocol"): "blame_diffusion",
    ("inattention-to-results", "new_eval"): "individual_optimization",
    ("inattention-to-results", "team_composition_change"): "metric_gaming",
}


def find_playbook(dysfunction: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((dysfunction, failure_mode))


def find_playbook_for_intervention(
    target_dysfunction: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_dysfunction, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_dysfunction, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
