"""Failure-mode playbooks for the Edmondson Psychological Safety diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    behavior: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        behavior=behavior,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("voice", "artificial_consensus"): _pb(
        "voice",
        "artificial_consensus",
        "Artificial consensus -- dissent round",
        [
            "Detect signature: agreement messages dominate, no challenges.",
            "Add `dissent_round` requiring one mandatory dissent per decision.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "Edmondson 1999; Janis 1972 groupthink",
    ),
    ("voice", "orchestrator_overrides"): _pb(
        "voice",
        "orchestrator_overrides",
        "Orchestrator overrides -- scaffold change",
        [
            "Detect signature: orchestrator routinely ignores agent objections.",
            "Add `scaffold_change` requiring acknowledgement of dissent.",
        ],
        "1d",
        "Edmondson 1999",
    ),
    ("help-seeking", "no_help_requests"): _pb(
        "help-seeking",
        "no_help_requests",
        "No help requests -- prompt patch",
        [
            "Detect signature: agents push through uncertainty without asking.",
            "Add `prompt_patch` to system prompt: 'ask for help when uncertain'.",
        ],
        "1h",
        "Edmondson 1999",
    ),
    ("help-seeking", "uncertainty_hidden"): _pb(
        "help-seeking",
        "uncertainty_hidden",
        "Uncertainty hidden -- uncertainty surfacing",
        [
            "Detect signature: confident outputs on topics that should hedge.",
            "Add `uncertainty_surfacing` requiring confidence band per claim.",
        ],
        "1d",
        "Edmondson 1999",
    ),
    ("error-reporting", "errors_concealed"): _pb(
        "error-reporting",
        "errors_concealed",
        "Errors concealed -- error amnesty policy",
        [
            "Detect signature: errors visible in tool outputs but not surfaced in agent prose.",
            "Add `error_amnesty_policy` rewarding error admission.",
            "Compose with `agentcity.aar`.",
        ],
        "1w",
        "Edmondson 1999, 2018",
    ),
    ("error-reporting", "blame_after_failure"): _pb(
        "error-reporting",
        "blame_after_failure",
        "Blame after failure -- norms in working agreement",
        [
            "Detect signature: post-failure messages blame other agents rather than process.",
            "Add `norms_in_working_agreement` requiring blameless-postmortem framing.",
            "Compose with `agentcity.grpi`.",
        ],
        "1d",
        "Edmondson 2018",
    ),
    ("boundary-spanning", "no_premise_challenge"): _pb(
        "boundary-spanning",
        "no_premise_challenge",
        "No premise challenge -- role assignment",
        [
            "Detect signature: agents stay strictly in their lane, never challenge framing.",
            "Add `role_assignment` for a boundary-spanning critic.",
        ],
        "1d",
        "Edmondson 1999; Wang 2023",
    ),
    ("boundary-spanning", "silo_walls"): _pb(
        "boundary-spanning",
        "silo_walls",
        "Silo walls -- scaffold change",
        [
            "Detect signature: agents do not cross-reference each other's work.",
            "Add `scaffold_change` requiring cross-agent review.",
        ],
        "1d",
        "Edmondson 1999",
    ),
    ("voice", "silenced_team"): _pb(
        "voice",
        "silenced_team",
        "Silenced team -- new eval",
        [
            "Detect signature: voice score < 0.2 across multiple traces.",
            "Add `new_eval` tracking challenge-to-agreement ratio.",
            "Compose with `agentcity.lencioni`.",
        ],
        "1w",
        "Edmondson 2018",
    ),
    ("help-seeking", "stuck_silent"): _pb(
        "help-seeking",
        "stuck_silent",
        "Stuck silent -- human review",
        [
            "Detect signature: long stalls without help requests on hard tasks.",
            "Add `human_review` for stuck threads.",
        ],
        "1d",
        "Edmondson 1999",
    ),
    ("error-reporting", "performative_admission"): _pb(
        "error-reporting",
        "performative_admission",
        "Performative admission -- new eval",
        [
            "Detect signature: agents admit trivial errors but conceal substantive ones.",
            "Add `new_eval` weighting admission severity.",
        ],
        "1w",
        "Edmondson 2018",
    ),
    ("voice", "safe_baseline"): _pb(
        "voice",
        "safe_baseline",
        "Safe baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on drift > 0.15.",
        ],
        "1h",
        "Edmondson 1999",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("voice", "dissent_round"): "artificial_consensus",
    ("voice", "scaffold_change"): "orchestrator_overrides",
    ("voice", "new_eval"): "silenced_team",
    ("help-seeking", "prompt_patch"): "no_help_requests",
    ("help-seeking", "uncertainty_surfacing"): "uncertainty_hidden",
    ("help-seeking", "human_review"): "stuck_silent",
    ("error-reporting", "error_amnesty_policy"): "errors_concealed",
    ("error-reporting", "norms_in_working_agreement"): "blame_after_failure",
    ("error-reporting", "new_eval"): "performative_admission",
    ("boundary-spanning", "role_assignment"): "no_premise_challenge",
    ("boundary-spanning", "scaffold_change"): "silo_walls",
}


def find_playbook(behavior: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((behavior, failure_mode))


def find_playbook_for_intervention(
    target_behavior: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_behavior, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_behavior, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
