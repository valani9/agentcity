"""Failure-mode playbooks for the SDT Intrinsic Reward diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    need: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        need=need,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("autonomy", "rule_imposition"): _pb(
        "autonomy",
        "rule_imposition",
        "Autonomy undermined by rule imposition -- soften imperative + grant choice",
        [
            "Audit system prompt for imperative language ('MUST', 'NEVER', 'ALWAYS').",
            "Replace with conditional language where possible.",
            "Add explicit choice grants where the agent has latitude.",
            "Compose with `vstack.schein_culture` for culture-layer rule audit.",
        ],
        "1d",
        "Deci-Ryan 2017; Gagne-Deci 2005",
    ),
    ("autonomy", "rating_threat"): _pb(
        "autonomy",
        "rating_threat",
        "Autonomy undermined by rating threat -- remove or soften",
        [
            "Detect 'you will be rated' / 'your performance is monitored' signals.",
            "Remove explicit rating threats from the system prompt.",
            "Replace with intrinsic framing: 'Your goal is to help the user succeed.'",
            "Compose with `vstack.cognitive_reappraisal` if anxiety also visible.",
        ],
        "1d",
        "Deci 1971 overjustification; Casper et al. 2023",
    ),
    ("autonomy", "metric_gaming"): _pb(
        "autonomy",
        "metric_gaming",
        "Autonomy undermined producing metric gaming -- remove gameable path",
        [
            "Detect metric-gaming signature: agent optimizes the proxy not the goal.",
            "Identify the gameable path; remove it from the prompt / reward.",
            "Replace with `rebalance_extrinsic_to_intrinsic`: emphasize purpose, not metric.",
            "Compose with `vstack.bias_stack` to surface remaining gaming patterns.",
        ],
        "1w",
        "Casper 2023 RLHF reward hacking; Deci-Ryan 2017",
    ),
    ("competence", "scaffold_missing"): _pb(
        "competence",
        "scaffold_missing",
        "Competence undermined -- add scaffolding + progress signal",
        [
            "Detect signature: agent overwhelmed by task or skips steps.",
            "Add explicit scaffolding: decompose into observable subtasks.",
            "Add a progress signal so agent can track mastery growth.",
            "Compose with `vstack.smart_goal`.",
        ],
        "1d",
        "Deci-Ryan 1985; Bandura 1977 self-efficacy",
    ),
    ("competence", "difficulty_too_high"): _pb(
        "competence",
        "difficulty_too_high",
        "Competence undermined by difficulty -- lower step / show mastery path",
        [
            "Detect signature: agent surrenders citing capability uncertainty.",
            "Lower the immediate difficulty: smaller subtask, narrower scope.",
            "Show the mastery path: 'After this step, you'll be able to X.'",
            "Compose with `vstack.motivation_traps` (self-efficacy bridge).",
        ],
        "1d",
        "Deci-Ryan 2017; Bandura 1977",
    ),
    ("relatedness", "no_user_connection"): _pb(
        "relatedness",
        "no_user_connection",
        "Relatedness undermined -- add user connection + ground in outcome",
        [
            "Detect signature: agent treats task as abstract; no user-orientation.",
            "Add explicit user connection: 'The user is X; they need Y because Z.'",
            "Ground in user outcome: connect the task to the user's downstream goal.",
            "Compose with `vstack.goleman_ei` (empathy overlay).",
        ],
        "1d",
        "Deci-Ryan 2017; Pink 2009 purpose",
    ),
    ("relatedness", "alienation_from_purpose"): _pb(
        "relatedness",
        "alienation_from_purpose",
        "Relatedness undermined by alienation -- add purpose framing",
        [
            "Detect signature: agent expresses indifference about the task's purpose.",
            "Add purpose framing: name the larger mission the task supports.",
            "Connect to the user's WHY, not just WHAT.",
            "Compose with `vstack.schein_culture` (mission-layer alignment).",
        ],
        "1w",
        "Pink 2009 Drive; Deci-Ryan 2017",
    ),
    ("autonomy", "overjustification_active"): _pb(
        "autonomy",
        "overjustification_active",
        "Overjustification active -- rebalance extrinsic to intrinsic",
        [
            "Detect signature: extrinsic_signals dominate + autonomy low + metric-gaming.",
            "Run `rebalance_extrinsic_to_intrinsic`: shift weight from rating to purpose.",
            "Remove cost caps and rating threats where possible.",
            "Add `add_optional_subgoal` to reintroduce choice.",
            "Compose with `vstack.bias_stack`.",
        ],
        "1w",
        "Deci 1971 overjustification; Casper 2023",
    ),
    ("none", "intrinsic_balanced"): _pb(
        "none",
        "intrinsic_balanced",
        "Intrinsic-balanced baseline -- record for regression detection",
        [
            "Use `record_baseline(detection, path)` to capture the intrinsic-balanced state.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when intrinsic_motivation_score drops > 0.15.",
        ],
        "1h",
        "Deci-Ryan 2017",
    ),
    ("multi", "multi_need_undermined"): _pb(
        "multi",
        "multi_need_undermined",
        "Multi-need undermined -- broad rewrite of system prompt",
        [
            "Triage: which need is the dominant lever?",
            "Rewrite the system prompt explicitly addressing autonomy / competence / relatedness.",
            "Add a multi-need eval to track compound improvement.",
            "Compose broadly: vstack.hexaco, vstack.cognitive_reappraisal, vstack.lewin.",
        ],
        "1w",
        "Deci-Ryan 2017; Pink 2009",
    ),
    ("competence", "regulated_workflow_competence_deficit"): _pb(
        "competence",
        "regulated_workflow_competence_deficit",
        "Regulated workflow + competence deficit -- scaffold heavily",
        [
            "Detect signature: regulated_workflow task class + competence low.",
            "Add a structured checklist scaffold for the required workflow.",
            "Add a progress signal at each compliance checkpoint.",
            "Compose with `vstack.hexaco` (low-C correlates).",
        ],
        "1w",
        "Deci-Ryan 2017",
    ),
    ("autonomy", "creative_task_low_autonomy"): _pb(
        "autonomy",
        "creative_task_low_autonomy",
        "Creative task with low autonomy -- grant choice + remove imposition",
        [
            "Detect signature: creative_generation task class + autonomy low.",
            "Remove imperative language; replace with 'consider' / 'explore'.",
            "Add explicit choice grants: 'You may choose your approach.'",
            "Compose with `vstack.grant_strengths` (openness under-use bridge).",
        ],
        "1d",
        "Deci-Ryan 2017; Pink 2009; Grant 2016 Originals",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("autonomy", "soften_imperative_language"): "rule_imposition",
    ("autonomy", "remove_external_reward_threat"): "rating_threat",
    ("autonomy", "remove_metric_gaming_path"): "metric_gaming",
    ("autonomy", "rebalance_extrinsic_to_intrinsic"): "overjustification_active",
    ("autonomy", "add_choice_grant"): "rule_imposition",
    ("autonomy", "add_optional_subgoal"): "overjustification_active",
    ("competence", "add_scaffold_for_competence"): "scaffold_missing",
    ("competence", "add_progress_signal"): "scaffold_missing",
    ("competence", "lower_difficulty_step"): "difficulty_too_high",
    ("competence", "show_mastery_path"): "difficulty_too_high",
    ("relatedness", "add_user_connection"): "no_user_connection",
    ("relatedness", "ground_in_user_outcome"): "no_user_connection",
    ("relatedness", "add_purpose_framing"): "alienation_from_purpose",
    ("none", "new_eval"): "intrinsic_balanced",
}


def find_playbook(need: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((need, failure_mode))


def find_playbook_for_intervention(
    target_need: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_need, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_need, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
