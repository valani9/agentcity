"""Failure-mode playbooks for the Groupthink/Polarization/Contagion diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    pathology: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        pathology=pathology,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("groupthink", "illusion_of_unanimity"): _pb(
        "groupthink",
        "illusion_of_unanimity",
        "Illusion of unanimity -- assign devil's advocate",
        [
            "Detect signature: no challenges across 3+ rounds.",
            "Add `assign_devils_advocate`.",
            "Compose with `agentcity.devils_advocate`.",
        ],
        "1d",
        "Janis 1972",
    ),
    ("groupthink", "self_censorship"): _pb(
        "groupthink",
        "self_censorship",
        "Self-censorship -- secret ballot",
        [
            "Detect signature: agents soften positions to match consensus.",
            "Add `secret_ballot` step.",
        ],
        "1d",
        "Janis 1972",
    ),
    ("groupthink", "dissent_suppressed"): _pb(
        "groupthink",
        "dissent_suppressed",
        "Dissent suppressed -- round-robin dissent",
        [
            "Detect signature: dissent introduced but rapidly dismissed.",
            "Add `round_robin_dissent` requiring each agent to surface one objection.",
            "Compose with `agentcity.psych_safety`.",
        ],
        "1d",
        "Janis 1972; Edmondson 1999",
    ),
    ("polarization", "risky_shift"): _pb(
        "polarization",
        "risky_shift",
        "Risky shift -- anchor to base rates",
        [
            "Detect signature: each round pushes toward higher risk.",
            "Add `anchor_to_base_rates` injecting external comparison.",
            "Compose with `agentcity.bias_stack`.",
        ],
        "1d",
        "Stoner 1968; Kahneman 2011",
    ),
    ("polarization", "extremity_runaway"): _pb(
        "polarization",
        "extremity_runaway",
        "Extremity runaway -- external arbiter",
        [
            "Detect signature: positions diverge from starting average.",
            "Add `external_arbiter` round.",
        ],
        "1d",
        "Sunstein 2002",
    ),
    ("polarization", "homogeneous_seeds"): _pb(
        "polarization",
        "homogeneous_seeds",
        "Homogeneous seeds -- diverse seed positions",
        [
            "Detect signature: all agents start in the same region of opinion space.",
            "Add `diverse_seed_positions` upstream.",
        ],
        "1d",
        "Page 2007 diversity",
    ),
    ("contagion", "heated_cascade"): _pb(
        "contagion",
        "heated_cascade",
        "Heated cascade -- cool-down pause",
        [
            "Detect signature: heated tone propagates to >half of agents.",
            "Add `cool_down_pause` between rounds.",
        ],
        "1d",
        "Hatfield/Cacioppo/Rapson 1993",
    ),
    ("contagion", "tone_overrides_content"): _pb(
        "contagion",
        "tone_overrides_content",
        "Tone overrides content -- tone normalization",
        [
            "Detect signature: tone drives convergence more than argument quality.",
            "Add `tone_normalization` requiring neutral framing of each turn.",
            "Compose with `agentcity.glaser_conversation`.",
        ],
        "1d",
        "Hatfield/Cacioppo/Rapson 1993; Glaser 2014",
    ),
    ("contagion", "anxiety_propagation"): _pb(
        "contagion",
        "anxiety_propagation",
        "Anxiety propagation -- smaller panel",
        [
            "Detect signature: anxious tone spreads across all agents.",
            "Add `smaller_panel` (fewer agents lowers cascade probability).",
        ],
        "1d",
        "Hatfield/Cacioppo/Rapson 1993",
    ),
    ("groupthink", "premature_convergence"): _pb(
        "groupthink",
        "premature_convergence",
        "Premature convergence -- silent vote first",
        [
            "Detect signature: convergence by round 2.",
            "Add `require_silent_vote` before any discussion.",
        ],
        "1d",
        "Janis 1972",
    ),
    ("polarization", "irreversible_decision"): _pb(
        "polarization",
        "irreversible_decision",
        "Polarization on irreversible decision -- human review",
        [
            "Detect signature: polarization severe on high-stakes irreversible call.",
            "Add `human_review` checkpoint.",
        ],
        "1w",
        "Sunstein 2002",
    ),
    ("groupthink", "healthy_baseline"): _pb(
        "groupthink",
        "healthy_baseline",
        "Healthy baseline -- record + monitor",
        [
            "Use `record_baseline`; add `new_eval`; alert on pathology drift > 0.15.",
        ],
        "1h",
        "Janis 1972",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("groupthink", "assign_devils_advocate"): "illusion_of_unanimity",
    ("groupthink", "secret_ballot"): "self_censorship",
    ("groupthink", "round_robin_dissent"): "dissent_suppressed",
    ("groupthink", "require_silent_vote"): "premature_convergence",
    ("polarization", "anchor_to_base_rates"): "risky_shift",
    ("polarization", "external_arbiter"): "extremity_runaway",
    ("polarization", "diverse_seed_positions"): "homogeneous_seeds",
    ("polarization", "human_review"): "irreversible_decision",
    ("contagion", "cool_down_pause"): "heated_cascade",
    ("contagion", "tone_normalization"): "tone_overrides_content",
    ("contagion", "smaller_panel"): "anxiety_propagation",
}


def find_playbook(pathology: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((pathology, failure_mode))


def find_playbook_for_intervention(
    target_pathology: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_pathology, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_pathology, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
