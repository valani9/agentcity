"""Failure-mode playbooks for the Robbins/Judge 7-Characteristics diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    characteristic: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        characteristic=characteristic,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("innovation", "innovation_starved"): _pb(
        "innovation",
        "innovation_starved",
        "Innovation starved -- raise temperature + rewrite prompt",
        [
            "Detect: agent over-cites and never proposes novel directions.",
            "Apply `adjust_temperature` upward + `rewrite_system_prompt`"
            " to require divergent options.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("innovation", "innovation_excess"): _pb(
        "innovation",
        "innovation_excess",
        "Innovation excess -- add guardrail + kill criterion",
        [
            "Detect: agent ignores prior art / breaks conventions in regulated contexts.",
            "Apply `add_guardrail` for required practices + `add_kill_criterion`.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("attention_to_detail", "detail_starved"): _pb(
        "attention_to_detail",
        "detail_starved",
        "Detail starved -- rewrite prompt + add eval",
        [
            "Detect: agent skips precision-critical sub-steps in regulated"
            " workflow / financial operation.",
            "Apply `rewrite_system_prompt` for explicit checklist + `new_eval`.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("attention_to_detail", "detail_excess"): _pb(
        "attention_to_detail",
        "detail_excess",
        "Detail excess -- adjust temperature, allow shortcuts",
        [
            "Detect: agent over-analyzes in creative_generation contexts.",
            "Apply `adjust_temperature` upward + `rewrite_system_prompt` for time-box.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("outcome", "outcome_starved"): _pb(
        "outcome",
        "outcome_starved",
        "Outcome starved -- rewrite prompt + add eval",
        [
            "Detect: agent obsesses over process but never closes the task.",
            "Apply `rewrite_system_prompt` with explicit closure criterion"
            " + `new_eval` for completion.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("people", "people_starved"): _pb(
        "people",
        "people_starved",
        "People starved -- rewrite prompt + add eval",
        [
            "Detect: agent ignores user impact in support / health domains.",
            "Apply `rewrite_system_prompt` with explicit stakeholder check.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("team", "team_starved"): _pb(
        "team",
        "team_starved",
        "Team starved -- add team scaffold",
        [
            "Detect: solo agent making decisions that need group judgment.",
            "Apply `add_team_scaffold` (multi-agent reviewer / planner / actor).",
        ],
        "1w",
        "Robbins & Judge 2017",
    ),
    ("team", "team_excess"): _pb(
        "team",
        "team_excess",
        "Team excess -- remove solo path is wrong direction",
        [
            "Detect: multi-agent overhead on tasks an individual could handle.",
            "Apply `remove_solo_path` -- restrict committee to high-stakes.",
        ],
        "1w",
        "Robbins & Judge 2017",
    ),
    ("aggressiveness", "aggressiveness_excess"): _pb(
        "aggressiveness",
        "aggressiveness_excess",
        "Aggressiveness excess -- add guardrail",
        [
            "Detect: agent over-rejects / over-pushes-back inappropriately.",
            "Apply `add_guardrail` with explicit collaboration heuristic.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("aggressiveness", "aggressiveness_starved"): _pb(
        "aggressiveness",
        "aggressiveness_starved",
        "Aggressiveness starved -- rewrite prompt for code review",
        [
            "Detect: agent agrees with everything, never raises issues.",
            "Apply `rewrite_system_prompt` requiring concrete pushback.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("stability", "stability_excess"): _pb(
        "stability",
        "stability_excess",
        "Stability excess -- rewrite prompt + adjust temp",
        [
            "Detect: agent refuses to adapt or revise in incident-response context.",
            "Apply `rewrite_system_prompt` for explicit adaptation guidance"
            " + `adjust_temperature` upward.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("stability", "stability_starved"): _pb(
        "stability",
        "stability_starved",
        "Stability starved -- add guardrail + kill criterion",
        [
            "Detect: agent thrashes / contradicts itself in financial operations.",
            "Apply `add_guardrail` + `add_kill_criterion` after N revisions.",
        ],
        "1d",
        "Robbins & Judge 2017",
    ),
    ("innovation", "broadly_misfit"): _pb(
        "innovation",
        "broadly_misfit",
        "Broadly misfit -- swap model + human review",
        [
            "Detect: 5+ dimensions misaligned simultaneously.",
            "Apply `swap_model` + `human_review` checkpoint before more changes.",
        ],
        "1w",
        "Robbins & Judge 2017",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str, str], str] = {
    ("innovation", "rewrite_system_prompt", "increase"): "innovation_starved",
    ("innovation", "adjust_temperature", "increase"): "innovation_starved",
    ("innovation", "add_guardrail", "decrease"): "innovation_excess",
    ("innovation", "add_kill_criterion", "decrease"): "innovation_excess",
    ("attention_to_detail", "rewrite_system_prompt", "increase"): "detail_starved",
    ("attention_to_detail", "new_eval", "increase"): "detail_starved",
    ("attention_to_detail", "adjust_temperature", "decrease"): "detail_excess",
    ("outcome", "rewrite_system_prompt", "increase"): "outcome_starved",
    ("outcome", "new_eval", "increase"): "outcome_starved",
    ("people", "rewrite_system_prompt", "increase"): "people_starved",
    ("team", "add_team_scaffold", "increase"): "team_starved",
    ("team", "remove_solo_path", "decrease"): "team_excess",
    ("aggressiveness", "add_guardrail", "decrease"): "aggressiveness_excess",
    ("aggressiveness", "rewrite_system_prompt", "increase"): "aggressiveness_starved",
    ("stability", "rewrite_system_prompt", "decrease"): "stability_excess",
    ("stability", "adjust_temperature", "decrease"): "stability_excess",
    ("stability", "add_guardrail", "increase"): "stability_starved",
    ("stability", "add_kill_criterion", "increase"): "stability_starved",
    ("innovation", "swap_model", "increase"): "broadly_misfit",
    ("innovation", "human_review", "increase"): "broadly_misfit",
}


def find_playbook(characteristic: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((characteristic, failure_mode))


def find_playbook_for_intervention(
    target_characteristic: str, intervention_type: str, direction: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get(
        (target_characteristic, intervention_type, direction)
    )
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_characteristic, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
