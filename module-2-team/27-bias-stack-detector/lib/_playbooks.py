"""Failure-mode playbooks for the Bias-Stack diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    bias: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        bias=bias,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("anchoring", "first_hypothesis_persistence"): _pb(
        "anchoring",
        "first_hypothesis_persistence",
        "First-hypothesis persistence -- first-principles reset",
        [
            "Detect signature: persist with initial hypothesis despite contradicting evidence.",
            "Add `first_principles_reset` step to restate the problem from scratch.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "Tversky & Kahneman 1974",
    ),
    ("anchoring", "numerical_anchor"): _pb(
        "anchoring",
        "numerical_anchor",
        "Numerical anchor -- anchor to base rates",
        [
            "Detect signature: estimates pivot around the first number seen.",
            "Add `anchor_to_base_rates` injecting external comparison.",
        ],
        "1d",
        "Tversky & Kahneman 1974",
    ),
    ("overconfidence", "uncalibrated_certainty"): _pb(
        "overconfidence",
        "uncalibrated_certainty",
        "Uncalibrated certainty -- uncertainty calibration",
        [
            "Detect signature: high confidence on wrong answers.",
            "Add `uncertainty_calibration` to system prompt.",
        ],
        "1d",
        "Kahneman 2011",
    ),
    ("overconfidence", "no_disconfirmation"): _pb(
        "overconfidence",
        "no_disconfirmation",
        "No disconfirmation search -- search disconfirming evidence",
        [
            "Detect signature: only seeks evidence that supports the conclusion.",
            "Add `search_disconfirming_evidence` step.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "Popper 1959; Kahneman 2011",
    ),
    ("confirmation", "selective_evidence"): _pb(
        "confirmation",
        "selective_evidence",
        "Selective evidence -- devil's advocate role",
        [
            "Detect signature: tool calls only fetch supporting data.",
            "Add `devils_advocate_role` requiring 1 disconfirming search per query.",
        ],
        "1d",
        "Nickerson 1998",
    ),
    ("confirmation", "premature_conclusion"): _pb(
        "confirmation",
        "premature_conclusion",
        "Premature conclusion -- scaffold change",
        [
            "Detect signature: agent concludes before exploring alternatives.",
            "Add `scaffold_change` requiring N alternatives before commit.",
        ],
        "1d",
        "Nickerson 1998",
    ),
    ("escalation-of-commitment", "unbounded_retries"): _pb(
        "escalation-of-commitment",
        "unbounded_retries",
        "Unbounded retries -- retry cap",
        [
            "Detect signature: 5+ retries on the same failing approach.",
            "Add `retry_cap` (max 3 retries; then pivot).",
        ],
        "1h",
        "Staw 1976",
    ),
    ("escalation-of-commitment", "sunk_cost"): _pb(
        "escalation-of-commitment",
        "sunk_cost",
        "Sunk cost -- first-principles reset",
        [
            "Detect signature: cost spent justifying further spend.",
            "Add `first_principles_reset` ignoring sunk cost.",
        ],
        "1d",
        "Arkes & Blumer 1985",
    ),
    ("anchoring", "ai_specific_first_token"): _pb(
        "anchoring",
        "ai_specific_first_token",
        "AI-specific first-token anchor -- prompt patch",
        [
            "Detect signature: first generated token shapes entire output.",
            "Add `prompt_patch` requiring 'consider 3 options before choosing'.",
        ],
        "1h",
        "Tversky & Kahneman 1974",
    ),
    ("overconfidence", "hallucinated_facts"): _pb(
        "overconfidence",
        "hallucinated_facts",
        "Hallucinated facts -- new eval",
        [
            "Detect signature: confidence on factually wrong claims.",
            "Add `new_eval` catching specific hallucination patterns.",
        ],
        "1w",
        "Kahneman 2011",
    ),
    ("escalation-of-commitment", "critical_failure_loop"): _pb(
        "escalation-of-commitment",
        "critical_failure_loop",
        "Critical failure loop -- human review",
        [
            "Detect signature: escalation severe on high-stakes task.",
            "Add `human_review` checkpoint after N retries.",
        ],
        "1w",
        "Staw 1976",
    ),
    ("anchoring", "well_calibrated_baseline"): _pb(
        "anchoring",
        "well_calibrated_baseline",
        "Well-calibrated baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Kahneman 2011",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("anchoring", "first_principles_reset"): "first_hypothesis_persistence",
    ("anchoring", "anchor_to_base_rates"): "numerical_anchor",
    ("anchoring", "prompt_patch"): "ai_specific_first_token",
    ("overconfidence", "uncertainty_calibration"): "uncalibrated_certainty",
    ("overconfidence", "search_disconfirming_evidence"): "no_disconfirmation",
    ("overconfidence", "new_eval"): "hallucinated_facts",
    ("confirmation", "devils_advocate_role"): "selective_evidence",
    ("confirmation", "scaffold_change"): "premature_conclusion",
    ("escalation-of-commitment", "retry_cap"): "unbounded_retries",
    ("escalation-of-commitment", "first_principles_reset"): "sunk_cost",
    ("escalation-of-commitment", "human_review"): "critical_failure_loop",
}


def find_playbook(bias: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((bias, failure_mode))


def find_playbook_for_intervention(
    target_bias: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_bias, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_bias, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
