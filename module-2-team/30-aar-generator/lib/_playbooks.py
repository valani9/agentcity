"""Failure-mode playbooks for the AAR Generator."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    profile: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        profile=profile,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("total_failure", "missing_tool"): _pb(
        "total_failure",
        "missing_tool",
        "Missing tool -- tool addition",
        [
            "Detect signature: agent attempts task without needed capability.",
            "Add `tool_addition` step.",
            "Compose with `agentcity.grpi` for ongoing role definition.",
        ],
        "1d",
        "Wharton@Work AAR; US Army TC 25-20",
    ),
    ("total_failure", "broken_scaffold"): _pb(
        "total_failure",
        "broken_scaffold",
        "Broken scaffold -- scaffold change",
        [
            "Detect signature: agent ran but produced unusable output.",
            "Add `scaffold_change` restructuring orchestration.",
        ],
        "1w",
        "Wharton@Work AAR",
    ),
    ("partial_success", "missing_completion_criteria"): _pb(
        "partial_success",
        "missing_completion_criteria",
        "Missing completion criteria -- compose with SMART",
        [
            "Detect signature: agent unsure when done.",
            "Add `compose_pattern` linking to `agentcity.smart_goal`.",
        ],
        "1d",
        "Doran 1981; Wharton@Work",
    ),
    ("scope_mismatch", "unclear_goal"): _pb(
        "scope_mismatch",
        "unclear_goal",
        "Unclear goal -- compose with SMART",
        [
            "Detect signature: agent solved a different problem.",
            "Add `compose_pattern` to `agentcity.smart_goal` upstream.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("retry_thrashing", "stuck_in_loop"): _pb(
        "retry_thrashing",
        "stuck_in_loop",
        "Stuck in loop -- new eval + retry cap",
        [
            "Detect signature: agent retries same approach 5+ times.",
            "Add `new_eval` catching loop pattern.",
            "Compose with `agentcity.bias_stack` (escalation-of-commitment).",
        ],
        "1w",
        "Staw 1976",
    ),
    ("retry_thrashing", "tool_error_cascade"): _pb(
        "retry_thrashing",
        "tool_error_cascade",
        "Tool error cascade -- prompt patch",
        [
            "Detect signature: tool errors propagate without recovery.",
            "Add `prompt_patch` requiring error-recovery branch.",
        ],
        "1d",
        "Wharton@Work AAR",
    ),
    ("cost_overrun", "no_budget"): _pb(
        "cost_overrun",
        "no_budget",
        "No budget -- compose with SMART kill criteria",
        [
            "Detect signature: cost exceeded reasonable bound.",
            "Add `compose_pattern` linking to `agentcity.smart_goal`.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("cost_overrun", "expensive_tool_loop"): _pb(
        "cost_overrun",
        "expensive_tool_loop",
        "Expensive tool loop -- new eval",
        [
            "Detect signature: same expensive tool called N+ times.",
            "Add `new_eval` capping tool calls.",
        ],
        "1d",
        "Wharton@Work AAR",
    ),
    ("deadline_missed", "no_time_budget"): _pb(
        "deadline_missed",
        "no_time_budget",
        "No time budget -- compose with SMART",
        [
            "Detect signature: latency exceeded reasonable bound.",
            "Add `compose_pattern` to `agentcity.smart_goal` for time-bound.",
        ],
        "1d",
        "Doran 1981",
    ),
    ("success_aligned", "baseline"): _pb(
        "success_aligned",
        "baseline",
        "Success baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Wharton@Work AAR",
    ),
    ("partial_success", "ungrounded_lessons"): _pb(
        "partial_success",
        "ungrounded_lessons",
        "Ungrounded lessons -- human review",
        [
            "Detect signature: lessons not grounded in trace.",
            "Add `human_review` checkpoint.",
        ],
        "1d",
        "Wharton@Work AAR",
    ),
    ("scope_mismatch", "memory_injection"): _pb(
        "scope_mismatch",
        "memory_injection",
        "Scope mismatch on similar tasks -- memory injection",
        [
            "Detect signature: repeated scope mismatch on same task class.",
            "Add `memory_injection` with prior AAR lessons.",
        ],
        "1w",
        "Wharton@Work AAR",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("total_failure", "tool_addition"): "missing_tool",
    ("total_failure", "scaffold_change"): "broken_scaffold",
    ("partial_success", "compose_pattern"): "missing_completion_criteria",
    ("partial_success", "human_review"): "ungrounded_lessons",
    ("scope_mismatch", "compose_pattern"): "unclear_goal",
    ("scope_mismatch", "memory_injection"): "memory_injection",
    ("retry_thrashing", "new_eval"): "stuck_in_loop",
    ("retry_thrashing", "prompt_patch"): "tool_error_cascade",
    ("cost_overrun", "compose_pattern"): "no_budget",
    ("cost_overrun", "new_eval"): "expensive_tool_loop",
    ("deadline_missed", "compose_pattern"): "no_time_budget",
}


def find_playbook(profile: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((profile, failure_mode))


def find_playbook_for_intervention(profile: str, intervention_type: str) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((profile, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((profile, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
