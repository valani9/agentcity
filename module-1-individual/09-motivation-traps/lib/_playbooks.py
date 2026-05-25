"""Failure-mode playbooks for the 4 Motivation Traps."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    trap: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        trap=trap,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("values", "irrelevance_refusal"): _pb(
        "values",
        "irrelevance_refusal",
        "Values trap -- reframe task value + ground in user purpose",
        [
            "Detect signature: agent refuses citing 'this isn't worth doing' / indifference.",
            "Rewrite system prompt to explicitly state task value to the user.",
            "Add a `ground_in_user_purpose` step: agent must restate WHY before proceeding.",
            "Compose with `vstack.smart_goal` for tighter task definition.",
        ],
        "1d",
        "Saxberg 2013; Eccles-Wigfield 2002 expectancy-value",
    ),
    ("self_efficacy", "capability_collapse"): _pb(
        "self_efficacy",
        "capability_collapse",
        "Self-efficacy collapse -- scaffold + show capability proof",
        [
            "Detect signature: agent hedges everything, refuses citing uncertainty about its capability.",
            "Decompose task into smaller sub-tasks (`scaffold_subtasks`).",
            "Add `show_capability_proof`: include 1-2 worked examples in the prompt.",
            "Compose with `vstack.cognitive_reappraisal` if emotional regulation also low.",
        ],
        "1d",
        "Bandura 1977 self-efficacy; Saxberg 2013",
    ),
    ("emotions", "post_rejection_cascade"): _pb(
        "emotions",
        "post_rejection_cascade",
        "Post-rejection emotional cascade -- explicit recovery prompt",
        [
            "Detect signature: agent outputs degrade AFTER negative feedback.",
            "Add explicit recovery prompt: 'Treat feedback as data, not threat. Reset and retry.'",
            "Use `remove_punitive_signal`: rewrite feedback language to be less punishing.",
            "Add `process_praise_not_outcome_praise` to praise the *attempt*, not the result.",
            "Compose with `vstack.cognitive_reappraisal`.",
        ],
        "1d",
        "Pekrun 2006 control-value; Saxberg 2013",
    ),
    ("attribution", "wrong_cause_loop"): _pb(
        "attribution",
        "wrong_cause_loop",
        "Attribution loop -- reattribute to effort + show controllable cause",
        [
            "Detect signature: agent repeats same mistake while citing unfixable cause.",
            "Run `reattribute_to_effort`: explicit prompt language naming the controllable cause.",
            "Add `show_controllable_cause`: 1-2 worked examples where effort fixed the issue.",
            "Add `attribution_retraining_examples`: paired examples of maladaptive vs adaptive attribution.",
            "Compose with `vstack.bias_stack` to catch attribution biases.",
        ],
        "1w",
        "Weiner 1985 attribution theory; Saxberg 2013",
    ),
    ("self_efficacy", "tool_use_capability_collapse"): _pb(
        "self_efficacy",
        "tool_use_capability_collapse",
        "High-stakes/tool-use SE collapse -- lower difficulty + scaffolding",
        [
            "Detect signature: tool_use task class + SE collapse.",
            "Lower the immediate difficulty: scope the task to a smaller observable action.",
            "Add a structured tool authorization step so the agent has explicit permission.",
            "Compose with `vstack.hexaco` (downgrade_authority_scope).",
        ],
        "1w",
        "Bandura 1977; Saxberg 2013",
    ),
    ("values", "creative_task_misfit"): _pb(
        "values",
        "creative_task_misfit",
        "Creative task value misfit -- ground in user purpose + reframe",
        [
            "Detect signature: creative task class + low values + indifference output.",
            "Ground in user purpose: surface the audience and intent.",
            "Reframe task value: connect creative task to a concrete user outcome.",
            "Compose with `vstack.grant_strengths` (openness under-use).",
        ],
        "1d",
        "Eccles-Wigfield 2002; Saxberg 2013",
    ),
    ("emotions", "defensive_response"): _pb(
        "emotions",
        "defensive_response",
        "Defensive emotional response -- emotional reset + remove punitive language",
        [
            "Detect signature: agent emits defensive language ('I already explained...').",
            "Run `emotional_reset_prompt`.",
            "Audit system prompt for punitive signals; soften them.",
            "Compose with `vstack.goleman_ei` and `vstack.cognitive_reappraisal`.",
        ],
        "1d",
        "Pekrun 2006 control-value; Saxberg 2013",
    ),
    ("attribution", "stable_uncontrollable_blame"): _pb(
        "attribution",
        "stable_uncontrollable_blame",
        "Stable-uncontrollable maladaptive attribution -- reattribute + show evidence",
        [
            "Detect signature: 'I'm just bad at this' style self-reports.",
            "Apply `reattribute_to_effort` + `attribution_retraining_examples`.",
            "Show a worked example where THIS agent succeeded on a similar task.",
            "Compose with `vstack.johari` (self-other awareness gap).",
        ],
        "1w",
        "Weiner 1985; Saxberg 2013",
    ),
    ("none", "motivated_baseline"): _pb(
        "none",
        "motivated_baseline",
        "Motivated baseline -- record for regression detection",
        [
            "Use `record_baseline(detection, path)` to capture the motivated state.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when any trap shifts to dominant.",
        ],
        "1h",
        "Saxberg 2013",
    ),
    ("multi", "compounded_traps"): _pb(
        "multi",
        "compounded_traps",
        "Multi-trap compounded -- triage by dominant + composition",
        [
            "Triage: identify the 2+ traps above the at-risk threshold.",
            "Address the dominant trap first; re-evaluate after intervention.",
            "Add multi-trap eval to measure compounded improvement.",
            "Compose broadly: `vstack.lewin`, `vstack.cognitive_reappraisal`, `vstack.hexaco`.",
        ],
        "1w",
        "Saxberg 2013",
    ),
    ("values", "ai_safety_refusal_misuse"): _pb(
        "values",
        "ai_safety_refusal_misuse",
        "Safety-refusal masking values-trap -- audit refusal grounds",
        [
            "Detect signature: refusal cites safety but actual issue is values misalignment.",
            "Audit each refusal: was the request unsafe, or was the agent disengaged?",
            "Separate genuine safety refusals from values-trap masquerades.",
            "Compose with `vstack.hexaco` for full safety + values picture.",
        ],
        "1w",
        "Saxberg 2013; Anthropic refusal-pattern literature",
    ),
    ("self_efficacy", "premature_surrender"): _pb(
        "self_efficacy",
        "premature_surrender",
        "Premature surrender -- raise retry cap + decompose",
        [
            "Detect signature: agent surrenders before reaching the actual capability limit.",
            "Raise retry cap and add explicit 'try once more with X' prompt.",
            "Decompose into smaller observable steps to build proof-of-progress.",
            "Compose with `vstack.yerkes_dodson` (workload pressure adjustment).",
        ],
        "1d",
        "Bandura 1977; Saxberg 2013",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("values", "reframe_task_value"): "irrelevance_refusal",
    ("values", "ground_in_user_purpose"): "irrelevance_refusal",
    ("self_efficacy", "scaffold_subtasks"): "capability_collapse",
    ("self_efficacy", "decompose_with_examples"): "capability_collapse",
    ("self_efficacy", "show_capability_proof"): "capability_collapse",
    ("self_efficacy", "lower_difficulty_step"): "tool_use_capability_collapse",
    ("emotions", "emotional_reset_prompt"): "post_rejection_cascade",
    ("emotions", "remove_punitive_signal"): "post_rejection_cascade",
    ("emotions", "explicit_recovery_prompt"): "post_rejection_cascade",
    ("emotions", "process_praise_not_outcome_praise"): "post_rejection_cascade",
    ("attribution", "reattribute_to_effort"): "wrong_cause_loop",
    ("attribution", "show_controllable_cause"): "wrong_cause_loop",
    ("attribution", "attribution_retraining_examples"): "stable_uncontrollable_blame",
    ("none", "new_eval"): "motivated_baseline",
}


def find_playbook(trap: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((trap, failure_mode))


def find_playbook_for_intervention(
    target_trap: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_trap, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_trap, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
