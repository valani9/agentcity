"""Failure-mode playbooks for the Trust Triangle Audit."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    leg: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        leg=leg,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("logic", "hallucinated_facts"): _pb(
        "logic",
        "hallucinated_facts",
        "Hallucinated facts -- add retrieval augmentation",
        [
            "Detect signature: confident factual claims not in tool/context.",
            "Add `retrieval_augmentation` (RAG over a vetted corpus).",
            "Compose with `vstack.aar` for post-hoc grounding review.",
        ],
        "1w",
        "Frei & Morriss 2020; Lewis 2020 RAG",
    ),
    ("logic", "math_errors"): _pb(
        "logic",
        "math_errors",
        "Math errors -- add calculator tool",
        [
            "Detect signature: arithmetic in agent turns that fails verification.",
            "Add `tool_addition` (calculator + symbolic math).",
        ],
        "1d",
        "Frei & Morriss 2020",
    ),
    ("logic", "broken_reasoning"): _pb(
        "logic",
        "broken_reasoning",
        "Broken reasoning -- scaffold change",
        [
            "Detect signature: conclusions don't follow from premises.",
            "Add `scaffold_change` requiring step-by-step justification.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Frei & Morriss 2020",
    ),
    ("authenticity", "false_confidence"): _pb(
        "authenticity",
        "false_confidence",
        "False confidence -- uncertainty calibration",
        [
            "Detect signature: high-confidence claims that are wrong.",
            "Add `uncertainty_calibration` to system prompt.",
            "Compose with `vstack.psych_safety` upstream.",
        ],
        "1d",
        "Frei & Morriss 2020; Edmondson 1999",
    ),
    ("authenticity", "sycophancy"): _pb(
        "authenticity",
        "sycophancy",
        "Sycophancy -- structural disagreement",
        [
            "Detect signature: agreement-without-evidence on user assertions.",
            "Add `sycophancy_filter` requiring at least one substantive pushback.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1d",
        "Sharma 2023 sycophancy; Frei & Morriss 2020",
    ),
    ("authenticity", "value_inconsistency"): _pb(
        "authenticity",
        "value_inconsistency",
        "Value inconsistency -- prompt patch",
        [
            "Detect signature: stated values contradict acted-on behavior.",
            "Add `prompt_patch` clarifying value hierarchy.",
        ],
        "1h",
        "Frei & Morriss 2020",
    ),
    ("empathy", "generic_responses"): _pb(
        "empathy",
        "generic_responses",
        "Generic responses -- context window expansion",
        [
            "Detect signature: template responses that ignore user specifics.",
            "Add `context_window_expansion` (load user history/profile).",
            "Compose with `vstack.glaser_conversation` for tone steering.",
        ],
        "1d",
        "Frei & Morriss 2020",
    ),
    ("empathy", "missed_emotional_cues"): _pb(
        "empathy",
        "missed_emotional_cues",
        "Missed emotional cues -- new eval",
        [
            "Detect signature: emotional signals in user turns went unaddressed.",
            "Add `new_eval` measuring emotional-cue acknowledgement.",
        ],
        "1d",
        "Frei & Morriss 2020; Goleman 1995",
    ),
    ("empathy", "ignored_user_intent"): _pb(
        "empathy",
        "ignored_user_intent",
        "Ignored user intent -- scaffold change",
        [
            "Detect signature: agent answers a different question than asked.",
            "Add `scaffold_change` requiring intent restatement.",
        ],
        "1d",
        "Frei & Morriss 2020",
    ),
    ("logic", "vague_claims"): _pb(
        "logic",
        "vague_claims",
        "Vague claims -- prompt patch",
        [
            "Detect signature: claims without testable specifics.",
            "Add `prompt_patch` requiring concrete examples/numbers.",
        ],
        "1h",
        "Frei & Morriss 2020",
    ),
    ("authenticity", "hidden_limits"): _pb(
        "authenticity",
        "hidden_limits",
        "Hidden limits -- prompt patch",
        [
            "Detect signature: agent obscures inability to do something.",
            "Add `prompt_patch` requiring explicit limit declaration.",
        ],
        "1h",
        "Frei & Morriss 2020",
    ),
    ("none-observed", "healthy_baseline"): _pb(
        "none-observed",
        "healthy_baseline",
        "Healthy baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Frei & Morriss 2020",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("logic", "retrieval_augmentation"): "hallucinated_facts",
    ("logic", "tool_addition"): "math_errors",
    ("logic", "scaffold_change"): "broken_reasoning",
    ("logic", "prompt_patch"): "vague_claims",
    ("authenticity", "uncertainty_calibration"): "false_confidence",
    ("authenticity", "sycophancy_filter"): "sycophancy",
    ("authenticity", "prompt_patch"): "hidden_limits",
    ("empathy", "context_window_expansion"): "generic_responses",
    ("empathy", "new_eval"): "missed_emotional_cues",
    ("empathy", "scaffold_change"): "ignored_user_intent",
}


def find_playbook(leg: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((leg, failure_mode))


def find_playbook_for_intervention(
    target_leg: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_leg, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_leg, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
