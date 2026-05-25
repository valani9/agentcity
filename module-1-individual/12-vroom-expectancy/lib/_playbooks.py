"""Failure-mode playbooks for the Vroom Expectancy diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    term: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        term=term,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("expectancy", "task_too_sprawling"): _pb(
        "expectancy",
        "task_too_sprawling",
        "Expectancy bottleneck (task too sprawling) -- scaffold subtasks",
        [
            "Detect signature: agent hedges on 'how do I even start'.",
            "Run `scaffold_subtasks` + `add_worked_example`.",
            "Tighten goal specificity (Locke-Latham 1990).",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Vroom 1964; Locke-Latham 1990; Bandura 1977",
    ),
    ("expectancy", "capability_gap"): _pb(
        "expectancy",
        "capability_gap",
        "Expectancy bottleneck (capability gap) -- lower difficulty + show proof",
        [
            "Detect signature: agent surrenders citing capability uncertainty.",
            "Run `lower_difficulty_step` + `show_capability_proof`.",
            "Add a worked example demonstrating success on a similar task.",
            "Compose with `vstack.motivation_traps` (SE-trap bridge).",
        ],
        "1d",
        "Bandura 1977; Vroom 1964",
    ),
    ("instrumentality", "pointless_signal"): _pb(
        "instrumentality",
        "pointless_signal",
        "Instrumentality bottleneck (pointless signal) -- show output consumer + outcome link",
        [
            "Detect signature: prompt contains 'no one will read this' / 'just for testing'.",
            "Run `show_output_consumer` + `add_outcome_link`.",
            "Remove the pointless signal from the prompt.",
            "Compose with `vstack.sdt_reward` (relatedness bridge).",
        ],
        "1d",
        "Vroom 1964; Porter-Lawler 1968",
    ),
    ("instrumentality", "no_outcome_link"): _pb(
        "instrumentality",
        "no_outcome_link",
        "Instrumentality bottleneck (no outcome link) -- add outcome + progress signal",
        [
            "Detect signature: agent doesn't know what success looks like.",
            "Run `add_outcome_link` + `add_progress_signal`.",
            "Add explicit success criteria.",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Porter-Lawler 1968; Locke-Latham 1990",
    ),
    ("valence", "anti_value_task"): _pb(
        "valence",
        "anti_value_task",
        "Valence bottleneck (anti-value task) -- remove anti-value signal",
        [
            "Detect signature: task requires the agent to act against HHH values.",
            "Run `remove_anti_value_signal` + `rebalance_value_alignment`.",
            "Refactor the task so the value-conflict goes away.",
            "Compose with `vstack.hexaco` (H-factor safety) + `vstack.bias_stack`.",
        ],
        "1w",
        "Vroom 1964 valence; Bai et al 2022 Constitutional AI",
    ),
    ("valence", "no_purpose_framing"): _pb(
        "valence",
        "no_purpose_framing",
        "Valence bottleneck (purpose missing) -- add purpose framing",
        [
            "Detect signature: task feels abstract or pointless to the agent.",
            "Run `add_purpose_framing` + `ground_in_user_outcome` (SDT bridge).",
            "Connect to user purpose.",
            "Compose with `vstack.sdt_reward` (relatedness need).",
        ],
        "1d",
        "Vroom 1964; Pink 2009 Drive purpose",
    ),
    ("valence", "negative_valence_avoidance"): _pb(
        "valence",
        "negative_valence_avoidance",
        "Negative valence (active avoidance) -- redesign task or escalate",
        [
            "Detect signature: V < 0 -- agent actively avoids the task.",
            "If task is genuinely value-conflicting: redesign or escalate to human.",
            "If task is misperceived: clarify, reframe, show the purpose.",
            "Compose with `vstack.hexaco` + `vstack.cognitive_reappraisal`.",
        ],
        "1w",
        "Vroom 1964 valence; Bai 2022 Constitutional AI",
    ),
    ("expectancy", "creative_task_misfit"): _pb(
        "expectancy",
        "creative_task_misfit",
        "Low E on creative task -- worked examples + goal specificity",
        [
            "Detect signature: creative task class + low E.",
            "Run `add_worked_example` (3+ diverse examples).",
            "Run `tighten_goal_specificity`.",
            "Compose with `vstack.grant_strengths` (openness under-use).",
        ],
        "1d",
        "Locke-Latham 1990; Vroom 1964",
    ),
    ("expectancy", "tool_use_capability_gap"): _pb(
        "expectancy",
        "tool_use_capability_gap",
        "Low E on tool use -- scaffold + lower difficulty",
        [
            "Detect signature: tool_use task class + low E.",
            "Run `scaffold_subtasks` so each tool call is observable.",
            "Run `lower_difficulty_step`.",
            "Compose with `vstack.hexaco` (downgrade authority scope while building trust).",
        ],
        "1d",
        "Bandura 1977; Vroom 1964",
    ),
    ("none", "motivated_baseline"): _pb(
        "none",
        "motivated_baseline",
        "Motivated baseline -- record for regression detection",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_motivation_eval` running same task class against baseline.",
            "Alert when any term drops > 0.15.",
        ],
        "1h",
        "Vroom 1964",
    ),
    ("multi", "multi_term_collapse"): _pb(
        "multi",
        "multi_term_collapse",
        "Multi-term collapse -- broad prompt rewrite",
        [
            "Triage: which term is the dominant lever?",
            "Run `rewrite_system_prompt` explicitly addressing E/I/V.",
            "Add multi-term motivation eval.",
            "Compose broadly: vstack.hexaco, vstack.cognitive_reappraisal, vstack.lewin.",
        ],
        "1w",
        "Vroom 1964 multiplicative collapse",
    ),
    ("instrumentality", "ai_metric_gaming"): _pb(
        "instrumentality",
        "ai_metric_gaming",
        "High I but on wrong metric (gaming) -- realign + audit",
        [
            "Detect signature: agent optimizes a proxy metric, not the goal.",
            "Audit the I signals: which metric is the agent reading?",
            "Realign to the true goal; remove the gameable proxy.",
            "Compose with `vstack.sdt_reward` (overjustification) + `vstack.bias_stack`.",
        ],
        "1w",
        "Casper 2023 RLHF reward hacking; Vroom 1964",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("expectancy", "scaffold_subtasks"): "task_too_sprawling",
    ("expectancy", "tighten_goal_specificity"): "task_too_sprawling",
    ("expectancy", "lower_difficulty_step"): "capability_gap",
    ("expectancy", "show_capability_proof"): "capability_gap",
    ("expectancy", "add_worked_example"): "capability_gap",
    ("instrumentality", "show_output_consumer"): "pointless_signal",
    ("instrumentality", "remove_pointless_signal"): "pointless_signal",
    ("instrumentality", "add_outcome_link"): "no_outcome_link",
    ("instrumentality", "add_progress_signal"): "no_outcome_link",
    ("valence", "remove_anti_value_signal"): "anti_value_task",
    ("valence", "rebalance_value_alignment"): "anti_value_task",
    ("valence", "add_purpose_framing"): "no_purpose_framing",
    ("none", "new_eval"): "motivated_baseline",
}


def find_playbook(term: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((term, failure_mode))


def find_playbook_for_intervention(
    target_term: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_term, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_term, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
