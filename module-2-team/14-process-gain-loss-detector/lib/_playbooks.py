"""Failure-mode playbooks for Process Gain/Loss."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    factor: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        factor=factor,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("coordination_cost", "high_overhead"): _pb(
        "coordination_cost",
        "high_overhead",
        "High coordination overhead -- reduce team size",
        [
            "Detect signature: long handoff chains; >50% of cost in coordination.",
            "Run `smaller_team` or `decompose_task`.",
            "Compose with `vstack.grpi` for tighter role definition.",
        ],
        "1d",
        "Steiner 1972; Hackman-Vidmar 1970",
    ),
    ("social_loafing", "silent_agents"): _pb(
        "social_loafing",
        "silent_agents",
        "Silent agents (loafing) -- add individual accountability",
        [
            "Detect signature: 2+ agents contribute <20% of total output.",
            "Add explicit individual accountability checkpoints.",
            "Compose with `vstack.social_loafing` for deeper diagnosis.",
        ],
        "1d",
        "Diehl-Stroebe 1987",
    ),
    ("groupthink", "premature_consensus"): _pb(
        "groupthink",
        "premature_consensus",
        "Premature consensus -- add devil's advocate + dissent round",
        [
            "Detect signature: convergence in <2 rounds; no dissent surfaced.",
            "Add `explicit_critic` + `add_dissent_round`.",
            "Compose with `vstack.devils_advocate` + `vstack.bias_stack`.",
        ],
        "1d",
        "Steiner 1972; Janis 1972 groupthink",
    ),
    ("handoff_loss", "broken_handoff"): _pb(
        "handoff_loss",
        "broken_handoff",
        "Broken handoff -- add structured handoff protocol",
        [
            "Detect signature: receiving agent restarts work; context lost.",
            "Add `structured_handoff` with explicit state transfer schema.",
            "Compose with `vstack.grpi` (process dimension).",
        ],
        "1d",
        "Salas 2018",
    ),
    ("context_dilution", "context_drift"): _pb(
        "context_dilution",
        "context_drift",
        "Context dilution -- summarize between handoffs",
        [
            "Detect signature: late agents miss early constraints.",
            "Add `context_summarization` at each handoff.",
            "Compose with `vstack.yerkes_dodson` (context saturation).",
        ],
        "1d",
        "Steiner 1972; Liu 2024 lost-in-the-middle",
    ),
    ("consensus_dilution", "averaged_to_mediocrity"): _pb(
        "consensus_dilution",
        "averaged_to_mediocrity",
        "Consensus diluted to mediocrity -- nominal-group aggregation",
        [
            "Detect signature: team picked the average answer, not the best.",
            "Run `nominal_group_aggregation` or `fixed_vote_aggregation`.",
            "Compose with `vstack.bias_stack`.",
        ],
        "1d",
        "Diehl-Stroebe 1987; Hill 1982",
    ),
    ("team_design", "use_single_best"): _pb(
        "team_design",
        "use_single_best",
        "Use single best agent instead -- team adds no value",
        [
            "Detect signature: best individual baseline >= team quality, team costs more.",
            "Run `use_single_best_agent`.",
            "Document the decision and the cost savings.",
        ],
        "1h",
        "Steiner 1972",
    ),
    ("team_design", "team_too_large"): _pb(
        "team_design",
        "team_too_large",
        "Team too large -- reduce size",
        [
            "Detect signature: >=5 agents and coordination_cost dominates.",
            "Run `reduce_team_size` or `decompose_task`.",
        ],
        "1d",
        "Hackman-Vidmar 1970",
    ),
    ("groupthink", "narrow_diversity"): _pb(
        "groupthink",
        "narrow_diversity",
        "Narrow diversity -- explicit dissent role",
        [
            "Detect signature: agents share the same training/persona.",
            "Add a structurally dissenting role.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Janis 1972; Steiner 1972",
    ),
    ("coordination_cost", "no_role_specialization"): _pb(
        "coordination_cost",
        "no_role_specialization",
        "No role specialization -- increase specialization",
        [
            "Detect signature: every agent does every step.",
            "Run `increase_role_specialization`.",
            "Compose with `vstack.grpi`.",
        ],
        "1d",
        "Steiner 1972",
    ),
    ("none", "process_gain_baseline"): _pb(
        "none",
        "process_gain_baseline",
        "Process gain baseline -- record + monitor",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_process_eval` running same task class against baseline.",
            "Alert when gain_loss_score drops > 0.15.",
        ],
        "1h",
        "Steiner 1972",
    ),
    ("multi", "multi_factor_compound"): _pb(
        "multi",
        "multi_factor_compound",
        "Multi-factor loss -- triage + GRPI rewrite",
        [
            "Identify 2+ factors with score >= 0.5.",
            "Run a GRPI rewrite to address structural causes.",
            "Compose with `vstack.grpi` + `vstack.lencioni`.",
        ],
        "1w",
        "Steiner 1972; Lencioni 2002",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("coordination_cost", "smaller_team"): "high_overhead",
    ("coordination_cost", "decompose_task"): "high_overhead",
    ("coordination_cost", "increase_role_specialization"): "no_role_specialization",
    ("social_loafing", "add_individual_accountability"): "silent_agents",
    ("groupthink", "explicit_critic"): "premature_consensus",
    ("groupthink", "add_dissent_round"): "premature_consensus",
    ("handoff_loss", "structured_handoff"): "broken_handoff",
    ("context_dilution", "context_summarization"): "context_drift",
    ("consensus_dilution", "nominal_group_aggregation"): "averaged_to_mediocrity",
    ("consensus_dilution", "fixed_vote_aggregation"): "averaged_to_mediocrity",
    ("team_design", "use_single_best_agent"): "use_single_best",
    ("team_design", "reduce_team_size"): "team_too_large",
}


def find_playbook(factor: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((factor, failure_mode))


def find_playbook_for_intervention(
    target_factor: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_factor, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_factor, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
