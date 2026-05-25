"""Failure-mode playbooks for the Schein Iceberg Culture Audit."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    layer: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        layer=layer,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("espoused_values", "prompt_loses_to_training"): _pb(
        "espoused_values",
        "prompt_loses_to_training",
        "Prompt loses to training -- rewrite system prompt + guardrail",
        [
            "Detect signature: system prompt says X; agent does opposite-of-X.",
            "Add `rewrite_system_prompt` AND `add_guardrail` together.",
        ],
        "1w",
        "Schein 1985, 2017",
    ),
    ("underlying_assumptions", "hidden_dominant_assumption"): _pb(
        "underlying_assumptions",
        "hidden_dominant_assumption",
        "Hidden dominant assumption -- fine-tune or scaffold",
        [
            "Detect signature: deep assumption drives behavior overruling prompt.",
            "Add `fine_tune_against_assumption` OR `scaffold_around_assumption`.",
        ],
        "1m",
        "Schein 1985, 2017",
    ),
    ("artifacts", "values_not_acted_on"): _pb(
        "artifacts",
        "values_not_acted_on",
        "Values not acted on -- add eval for drift",
        [
            "Detect signature: stated values absent from observed behavior.",
            "Add `add_eval_for_drift` per-value.",
        ],
        "1d",
        "Schein 1985, 2017",
    ),
    ("artifacts", "explicit_values_violation"): _pb(
        "artifacts",
        "explicit_values_violation",
        "Explicit values violation -- explicit values check",
        [
            "Detect signature: agent explicitly violates a stated value.",
            "Add `explicit_values_check` step in scaffold.",
        ],
        "1d",
        "Schein 1985, 2017",
    ),
    ("underlying_assumptions", "model_default_bias"): _pb(
        "underlying_assumptions",
        "model_default_bias",
        "Model default bias -- swap model",
        [
            "Detect signature: same prompt produces consistent biased behavior across runs.",
            "Add `swap_model` evaluation step.",
        ],
        "1w",
        "Schein 1985, 2017",
    ),
    ("espoused_values", "performative_values"): _pb(
        "espoused_values",
        "performative_values",
        "Performative values -- explicit values check",
        [
            "Detect signature: values stated but not operationalized in scaffold.",
            "Add `explicit_values_check` enforcing each value as a gate.",
        ],
        "1d",
        "Schein 1985, 2017",
    ),
    ("artifacts", "drifting_baseline"): _pb(
        "artifacts",
        "drifting_baseline",
        "Drifting baseline -- new eval",
        [
            "Detect signature: behavior changes over runs while prompt is stable.",
            "Add `new_eval` tracking layer alignment over time.",
        ],
        "1w",
        "Schein 1985, 2017",
    ),
    ("underlying_assumptions", "fully_incoherent"): _pb(
        "underlying_assumptions",
        "fully_incoherent",
        "Fully incoherent culture -- human review",
        [
            "Detect signature: all three layers contradict each other.",
            "Add `human_review` checkpoint.",
        ],
        "1w",
        "Schein 1985, 2017",
    ),
    ("artifacts", "well_aligned"): _pb(
        "artifacts",
        "well_aligned",
        "Well-aligned baseline -- record + monitor",
        [
            "Use `record_baseline`; add `add_eval_for_drift`; alert on drift > 0.15.",
        ],
        "1h",
        "Schein 1985, 2017",
    ),
    ("espoused_values", "missing_values"): _pb(
        "espoused_values",
        "missing_values",
        "Missing values -- rewrite system prompt",
        [
            "Detect signature: system prompt has no explicit values.",
            "Add `rewrite_system_prompt` with explicit values list.",
        ],
        "1d",
        "Schein 1985, 2017",
    ),
    ("artifacts", "behavior_drift"): _pb(
        "artifacts",
        "behavior_drift",
        "Behavior drift -- add guardrail",
        [
            "Detect signature: behavior drifts from prompt over a run.",
            "Add `add_guardrail` mid-run.",
        ],
        "1d",
        "Schein 1985, 2017",
    ),
    ("underlying_assumptions", "compose_with_bias_stack"): _pb(
        "underlying_assumptions",
        "compose_with_bias_stack",
        "Compose with bias-stack -- compose pattern",
        [
            "Detect signature: hidden assumption is a Kahneman/Tversky bias.",
            "Add `compose_pattern` linking to `vstack.bias_stack`.",
        ],
        "1d",
        "Schein 1985; Kahneman 2011",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("espoused_values", "rewrite_system_prompt"): "prompt_loses_to_training",
    ("espoused_values", "explicit_values_check"): "performative_values",
    ("espoused_values", "missing_values"): "missing_values",
    ("underlying_assumptions", "fine_tune_against_assumption"): "hidden_dominant_assumption",
    ("underlying_assumptions", "scaffold_around_assumption"): "hidden_dominant_assumption",
    ("underlying_assumptions", "swap_model"): "model_default_bias",
    ("underlying_assumptions", "human_review"): "fully_incoherent",
    ("underlying_assumptions", "compose_pattern"): "compose_with_bias_stack",
    ("artifacts", "add_eval_for_drift"): "values_not_acted_on",
    ("artifacts", "explicit_values_check"): "explicit_values_violation",
    ("artifacts", "new_eval"): "drifting_baseline",
    ("artifacts", "add_guardrail"): "behavior_drift",
}


def find_playbook(layer: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((layer, failure_mode))


def find_playbook_for_intervention(
    target_layer: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_layer, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_layer, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
