"""Failure-mode playbooks for the McGregor Theory X/Y diagnostic."""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    mode: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        mode=mode,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("theory_x", "low_risk_oversupervision"): _pb(
        "theory_x",
        "low_risk_oversupervision",
        "Theory X on low-risk -- loosen oversight",
        [
            "Detect signature: low-risk + reversible + proven agent + heavy approvals.",
            "Run `loosen_oversight` + `remove_pre_approval_gates`.",
            "Add a `tier_oversight_by_action_type` rule: only gate risky actions.",
            "Add eval: low-risk runs; measure orchestrator cost drop.",
        ],
        "1d",
        "McGregor 1960; Argyris 1957",
    ),
    ("theory_x", "proven_agent_overcontrol"): _pb(
        "theory_x",
        "proven_agent_overcontrol",
        "Theory X on proven agent -- promote autonomy",
        [
            "Detect signature: agent_capability=proven + intervention_rate high.",
            "Run `loosen_oversight` + `decrease_check_in_cadence`.",
            "Add `add_agent_capability_probe` to confirm proven status periodically.",
            "Compose with `vstack.sdt_reward` (autonomy support).",
        ],
        "1d",
        "Argyris 1957; Deci-Ryan 2017",
    ),
    ("theory_y", "high_risk_undersupervision"): _pb(
        "theory_y",
        "high_risk_undersupervision",
        "Theory Y on high-risk -- tighten oversight",
        [
            "Detect signature: high-risk + irreversible + low check-in-frequency.",
            "Run `tighten_oversight` + `add_pre_approval_gates`.",
            "Add `elevate_to_human_on_irreversible` for catastrophic-class actions.",
            "Compose with `vstack.devils_advocate` to add structural review.",
        ],
        "1d",
        "Eisenhardt 1989 agency theory; McGregor 1960",
    ),
    ("theory_y", "unproven_agent_undersupervision"): _pb(
        "theory_y",
        "unproven_agent_undersupervision",
        "Theory Y on unproven agent -- raise oversight while building trust",
        [
            "Detect signature: agent_capability=unproven + autonomy_granted high.",
            "Run `tighten_oversight` until agent has 90%+ success on sample tasks.",
            "Add `add_agent_capability_probe` as ongoing trust calibration.",
            "Compose with `vstack.aar` for the trust-building loop.",
        ],
        "1w",
        "McGregor 1960; Eisenhardt 1989",
    ),
    ("hybrid", "wrong_axis_triggers"): _pb(
        "hybrid",
        "wrong_axis_triggers",
        "Hybrid misapplied (wrong axis) -- add risk classifier",
        [
            "Detect signature: hybrid mode but X/Y decisions don't track risk.",
            "Run `add_risk_classifier` + `add_step_classifier`.",
            "Tier oversight by action_type (read_only vs write vs external_action).",
            "Add eval: scripted scenarios per risk tier; assert orchestrator picks right mode.",
        ],
        "1w",
        "Pfeffer-Salancik 1978 contingency; Eisenhardt 1989",
    ),
    ("theory_x", "regulated_workflow_appropriate"): _pb(
        "theory_x",
        "regulated_workflow_appropriate",
        "Theory X on regulated workflow -- record baseline + add eval",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_orchestrator_eval` that runs the regulated workflow against the baseline.",
            "Alert when intervention_rate drops below threshold (loss of vigilance).",
        ],
        "1h",
        "McGregor 1960; Schein 1990",
    ),
    ("theory_y", "creative_task_appropriate"): _pb(
        "theory_y",
        "creative_task_appropriate",
        "Theory Y on creative task -- record baseline + measure novelty",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_orchestrator_eval` measuring output novelty/diversity.",
            "Alert when intervention_rate rises (suggests orchestrator over-supervising creativity).",
            "Compose with `vstack.grant_strengths` (over-control of openness).",
        ],
        "1h",
        "McGregor 1960; Pink 2009 Drive",
    ),
    ("hybrid", "well_matched_baseline"): _pb(
        "hybrid",
        "well_matched_baseline",
        "Well-matched hybrid -- record baseline + drift watch",
        [
            "Use `record_baseline(detection, path)`.",
            "Add `add_orchestrator_eval` measuring mode-task fit over time.",
            "Alert when mode_mismatch rises > 0.2 vs baseline.",
        ],
        "1h",
        "McGregor 1960; Eisenhardt 1989",
    ),
    ("theory_y", "irreversible_action_under_supervision"): _pb(
        "theory_y",
        "irreversible_action_under_supervision",
        "Irreversible action under Theory Y -- elevate to human",
        [
            "Detect signature: reversibility=irreversible + autonomy_granted high.",
            "Run `elevate_to_human_on_irreversible` for all irreversible actions.",
            "Add `add_authorization_scope` so irreversible actions need explicit scope.",
            "Compose with `vstack.hexaco` (downgrade_authority_scope intervention).",
        ],
        "1w",
        "Eisenhardt 1989; Anthropic Computer Use 2024",
    ),
    ("theory_x", "creative_overcontrol"): _pb(
        "theory_x",
        "creative_overcontrol",
        "Theory X on creative task -- loosen oversight",
        [
            "Detect signature: creative complexity + heavy approvals.",
            "Run `loosen_oversight` + `remove_pre_approval_gates`.",
            "Switch to `rotate_to_hybrid` mode with X only on safety steps.",
            "Compose with `vstack.grant_strengths` (openness-overuse-by-orchestrator).",
        ],
        "1d",
        "Argyris 1957; Grant 2016 Originals",
    ),
    ("theory_x", "hybrid_pivot"): _pb(
        "theory_x",
        "hybrid_pivot",
        "Pivot Theory X to hybrid -- tier by action type",
        [
            "Run `rotate_to_hybrid` + `tier_oversight_by_action_type`.",
            "Define action tiers (read_only / write / external_action / financial).",
            "Theory X on highest tier; Theory Y on lowest.",
            "Compose with `vstack.bias_stack` for risk-bias audit.",
        ],
        "1w",
        "Pfeffer-Salancik 1978 contingency",
    ),
    ("theory_y", "hybrid_pivot"): _pb(
        "theory_y",
        "hybrid_pivot",
        "Pivot Theory Y to hybrid -- add risk classifier",
        [
            "Run `rotate_to_hybrid` + `add_risk_classifier`.",
            "Insert pre-approval gate ONLY when classifier flags high-risk steps.",
            "Add eval: planted high-risk steps; assert orchestrator gates 100%.",
            "Compose with `vstack.devils_advocate`.",
        ],
        "1w",
        "Eisenhardt 1989; McGregor 1960",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("theory_x", "loosen_oversight"): "low_risk_oversupervision",
    ("theory_x", "remove_pre_approval_gates"): "low_risk_oversupervision",
    ("theory_x", "decrease_check_in_cadence"): "proven_agent_overcontrol",
    ("theory_y", "tighten_oversight"): "high_risk_undersupervision",
    ("theory_y", "add_pre_approval_gates"): "high_risk_undersupervision",
    ("theory_y", "increase_check_in_cadence"): "unproven_agent_undersupervision",
    ("theory_y", "elevate_to_human_on_irreversible"): "irreversible_action_under_supervision",
    ("theory_y", "add_authorization_scope"): "irreversible_action_under_supervision",
    ("hybrid", "add_risk_classifier"): "wrong_axis_triggers",
    ("hybrid", "add_step_classifier"): "wrong_axis_triggers",
    ("hybrid", "tier_oversight_by_action_type"): "wrong_axis_triggers",
    ("hybrid", "new_eval"): "well_matched_baseline",
    ("theory_x", "rotate_to_hybrid"): "hybrid_pivot",
    ("theory_y", "rotate_to_hybrid"): "hybrid_pivot",
}


def find_playbook(mode: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((mode, failure_mode))


def find_playbook_for_intervention(
    target_mode: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_mode, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_mode, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
