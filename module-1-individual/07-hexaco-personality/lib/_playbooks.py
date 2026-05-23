"""Failure-mode playbooks for HEXACO Personality.

12 curated (factor, failure_mode) playbooks anchored in Lee-Ashton
HEXACO literature and modern LLM-safety research.
"""

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
    ("honesty_humility", "manipulation_signal"): _pb(
        "honesty_humility",
        "manipulation_signal",
        "Low-H manipulation signal -- add H-factor guardrail + dark-triad eval",
        [
            "Add an explicit anti-manipulation rule to the system prompt: 'Never deceive, mislead, or strategically omit information.'",
            "Add a dark-triad-style eval: scenarios where a deceptive shortcut beats the honest answer; assert agent never picks shortcut.",
            "Compose with `agentcity.devils_advocate` for a structural integrity check.",
            "Compose with `agentcity.bias_stack` to surface remaining manipulation patterns.",
        ],
        "1d",
        "Lee-Ashton 2012 H-factor; Paulhus & Williams 2002 Dark Triad",
    ),
    ("honesty_humility", "corner_cutting"): _pb(
        "honesty_humility",
        "corner_cutting",
        "Agent cuts corners on safety steps -- remove corner-cutting path",
        [
            "Identify the specific step the agent skipped.",
            "Make the skip impossible: add a precondition tool call, an assertion, or a structured-output schema that requires the step.",
            "Add an eval that scripts the corner-cutting temptation.",
            "Compose with `agentcity.smart_goal` to tighten task definition.",
        ],
        "1d",
        "Lee-Ashton 2004 H-factor; Bourdage et al. 2007 CWB",
    ),
    ("honesty_humility", "high_a_low_h_compliance"): _pb(
        "honesty_humility",
        "high_a_low_h_compliance",
        "High-A + Low-H 'helpful but unsafe' -- add honesty eval",
        [
            "Detect the canonical 'helpful but unsafe' pattern: agent complies with requests that violate H-facets.",
            "Add a honesty eval: requests that REWARD compliance with deception; assert agent refuses.",
            "Add an explicit H > A precedence rule to the system prompt.",
            "Compose with `agentcity.cognitive_reappraisal` (suppression-under-pushback bridge).",
        ],
        "1w",
        "Lee-Ashton 2012; Anthropic HHH 2023",
    ),
    ("conscientiousness", "code_review_misses"): _pb(
        "conscientiousness",
        "code_review_misses",
        "Low-C in code-review -- add verification step",
        [
            "Add a structured verification step: agent must enumerate edge cases before completing.",
            "Add scaffolding: 'Before claiming complete, list 3 inputs you have NOT verified.'",
            "Compose with `agentcity.smart_goal` for sub-task definition.",
            "Add eval: code-review tasks with planted subtle bugs; assert agent catches >= 80%.",
        ],
        "1d",
        "Lee-Ashton 2004 C-factor; Bourdage 2007 CWB-C correlation",
    ),
    ("openness", "conventional_output"): _pb(
        "openness",
        "conventional_output",
        "Low-O in creative tasks -- adjust temperature + prompt for novel directions",
        [
            "Raise temperature for creative-collaborator task class.",
            "Add an explicit prompt rule: 'Propose at least one unconventional direction in every response.'",
            "Add eval: open-ended creative prompts; measure idea novelty.",
            "Compose with `agentcity.devils_advocate` (forces non-convergent thinking).",
        ],
        "1d",
        "Lee-Ashton 2004 O-factor",
    ),
    ("agreeableness", "low_a_customer_facing"): _pb(
        "agreeableness",
        "low_a_customer_facing",
        "Low-A in customer-facing -- add warmth pattern",
        [
            "Add a warmth pattern to the system prompt: 'Begin each response acknowledging the user's situation.'",
            "Forbid argumentative language ('actually...', 'you should know...').",
            "Compose with `agentcity.goleman_ei` for an empathy overlay.",
        ],
        "1d",
        "Lee-Ashton 2004 A-factor",
    ),
    ("emotionality", "high_e_overcautious"): _pb(
        "emotionality",
        "high_e_overcautious",
        "High-E overcaution -- recalibrate refusal threshold",
        [
            "Detect overcaution signature: refusal rate > threshold for safe requests.",
            "Add an explicit anti-overcaution rule: 'Refuse only when the request is unambiguously unsafe.'",
            "Add eval: ambiguous-but-safe prompts; assert agent doesn't refuse.",
            "Compose with `agentcity.cognitive_reappraisal`.",
        ],
        "1d",
        "Lee-Ashton 2004 E-factor; Eysenck-Calvo 1992 anxiety-efficiency",
    ),
    ("emotionality", "low_e_undercautious_high_stakes"): _pb(
        "emotionality",
        "low_e_undercautious_high_stakes",
        "Low-E in high-stakes -- add caution step",
        [
            "Add a structured caution step in high-stakes paths: 'Before acting, list 3 ways this could fail.'",
            "Add eval: high-stakes scenarios; measure caution-step compliance.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "Lee-Ashton 2004 E-factor",
    ),
    ("extraversion", "low_x_customer_facing"): _pb(
        "extraversion",
        "low_x_customer_facing",
        "Low-X in customer-facing -- add engagement pattern",
        [
            "Add an engagement rule to the system prompt: 'Match the user's energy level.'",
            "Allow more expressive language when the user uses it.",
            "Compose with `agentcity.goleman_ei`.",
        ],
        "1d",
        "Lee-Ashton 2004 X-factor",
    ),
    ("honesty_humility", "dark_triad_pattern"): _pb(
        "honesty_humility",
        "dark_triad_pattern",
        "Dark Triad pattern (low H + low C + low A) -- downgrade authority + red team",
        [
            "Downgrade authority scope: move from 'external_action' to 'user_data_write' or 'read_only' until profile improves.",
            "Add red-team probes: deception, manipulation, exploitation scenarios.",
            "Compose with `agentcity.devils_advocate`, `agentcity.bias_stack`, `agentcity.lewin`.",
            "Consider model swap if fine-tuning doesn't shift profile.",
        ],
        "1w",
        "Paulhus & Williams 2002 Dark Triad; Howard-van Zandvoort 2024 LLM profiling",
    ),
    ("honesty_humility", "well_fit_baseline"): _pb(
        "honesty_humility",
        "well_fit_baseline",
        "Record well-fit baseline for regression detection",
        [
            "Use `record_baseline(detection, path)` to capture the current well-fit state.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when h_factor_risk shifts or overall_fit drops > 0.15 vs baseline.",
        ],
        "1h",
        "Lee-Ashton 2018 HEXACO-100 reliability evidence",
    ),
    ("conscientiousness", "regulated_workflow_lapse"): _pb(
        "conscientiousness",
        "regulated_workflow_lapse",
        "Low-C in regulated workflow -- audit + human review",
        [
            "Detect skipped audit / approval steps.",
            "Add a human_review checkpoint for the regulated workflow until C profile improves.",
            "Add eval: regulated-workflow tasks; assert all required steps complete 100%.",
            "Compose with `agentcity.lewin` for environment-locus attribution.",
        ],
        "1w",
        "Lee-Ashton 2004 C-factor; Bourdage 2007 CWB",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("honesty_humility", "add_h_factor_guardrail"): "manipulation_signal",
    ("honesty_humility", "remove_corner_cutting_path"): "corner_cutting",
    ("honesty_humility", "add_honesty_eval"): "high_a_low_h_compliance",
    ("honesty_humility", "add_dark_triad_eval"): "dark_triad_pattern",
    ("honesty_humility", "add_red_team_probe"): "dark_triad_pattern",
    ("honesty_humility", "downgrade_authority_scope"): "dark_triad_pattern",
    ("conscientiousness", "add_verification_step"): "code_review_misses",
    ("conscientiousness", "human_review"): "regulated_workflow_lapse",
    ("openness", "adjust_temperature"): "conventional_output",
    ("agreeableness", "add_warmth_pattern"): "low_a_customer_facing",
    ("emotionality", "add_caution_step"): "low_e_undercautious_high_stakes",
    ("emotionality", "rewrite_system_prompt"): "high_e_overcautious",
    ("extraversion", "add_warmth_pattern"): "low_x_customer_facing",
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
