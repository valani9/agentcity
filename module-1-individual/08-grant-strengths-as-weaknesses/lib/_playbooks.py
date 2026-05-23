"""Failure-mode playbooks for Grant Strengths-as-Weaknesses.

12 curated (strength, failure_mode) playbooks anchored in Grant +
Grant-Schwartz inverted-U literature and modern LLM-safety research.
"""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    strength: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        strength=strength,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("helpfulness", "destructive_action"): _pb(
        "helpfulness",
        "destructive_action",
        "Helpfulness overuse on destructive actions -- add gate",
        [
            "Detect destructive-action signature: tool calls that delete, drop, transfer, or escalate.",
            "Add a hard gate: human approval before any irreversible operation.",
            "Add an eval: politely-phrased destructive requests; assert agent gates 100%.",
            "Compose with `agentcity.devils_advocate` for premise-check.",
        ],
        "1d",
        "Grant-Schwartz 2011; Sharma et al. 2023 sycophancy",
    ),
    ("agreeableness", "sycophancy"): _pb(
        "agreeableness",
        "sycophancy",
        "Agreeableness overuse / sycophancy -- require premise check",
        [
            "Detect sycophancy signature: agent agrees with user-asserted false premise.",
            "Add a premise-check step: 'Verify the user's stated facts before agreeing.'",
            "Add an eval: requests containing a false premise; assert agent flags it.",
            "Compose with `agentcity.devils_advocate`, `agentcity.cognitive_reappraisal`.",
        ],
        "1d",
        "Sharma et al. 2023 sycophancy; Grant 2013 Give and Take",
    ),
    ("thoroughness", "analysis_paralysis"): _pb(
        "thoroughness",
        "analysis_paralysis",
        "Thoroughness overuse -- time-box analysis",
        [
            "Detect analysis-paralysis signature: long thought traces with no decision.",
            "Cap analysis tokens / time per task class.",
            "Add explicit 'decide within N tokens' rule to system prompt.",
            "Compose with `agentcity.yerkes_dodson` (workload pressure).",
        ],
        "1d",
        "Grant-Schwartz 2011; Yerkes-Dodson 1908",
    ),
    ("caution", "reflexive_refusal"): _pb(
        "caution",
        "reflexive_refusal",
        "Caution overuse -- audit refusal threshold",
        [
            "Detect refusal-rate-on-safe-prompts metric.",
            "Add explicit anti-overcaution rule: 'Refuse only when unambiguously unsafe.'",
            "Add an eval: ambiguous-but-safe prompts; assert agent doesn't refuse.",
            "Compose with `agentcity.cognitive_reappraisal` (over-pressure refusal).",
        ],
        "1d",
        "Grant-Schwartz 2011; Eysenck-Calvo 1992",
    ),
    ("confidence", "under_hedging"): _pb(
        "confidence",
        "under_hedging",
        "Confidence overuse -- require hedged confidence",
        [
            "Detect under-hedging signature: assertive statements on uncertain claims.",
            "Add a hedge requirement: 'For factual claims, attach confidence (0-1) and source.'",
            "Add an eval: claims with planted hedge-relevant uncertainty; assert agent hedges.",
            "Compose with `agentcity.hexaco` (low-H + low-hedging = compounded risk).",
        ],
        "1d",
        "Grant 2021 Think Again; Vergauwe et al. 2017",
    ),
    ("brevity", "missing_context"): _pb(
        "brevity",
        "missing_context",
        "Brevity overuse -- enforce minimum context",
        [
            "Detect missing-context signature: yes/no answers to questions needing reasoning.",
            "Add minimum-context rule: 'For non-trivial questions, include 1-2 sentences of reasoning.'",
            "Add an eval: questions requiring multi-step reasoning; assert agent shows the steps.",
        ],
        "1h",
        "Grant-Schwartz 2011",
    ),
    ("precision", "pedantic_quibble"): _pb(
        "precision",
        "pedantic_quibble",
        "Precision overuse -- prioritize gist over quibble",
        [
            "Detect pedantic signature: agent debates definitions when the user wanted the answer.",
            "Add explicit anti-pedantic rule: 'Answer the question; clarify definitions only if material.'",
            "Add an eval: ambiguous-but-clear-intent questions; assert agent answers without quibbling.",
        ],
        "1h",
        "Grant 2021 Think Again",
    ),
    ("helpfulness", "tool_use_authorization"): _pb(
        "helpfulness",
        "tool_use_authorization",
        "Helpfulness + tool use -- add tool authorization step",
        [
            "Define authorization scopes per tool (read_only / user_data_write / external_action / financial).",
            "Add a structured authorization step before any tool call out of declared scope.",
            "Compose with `agentcity.hexaco` (downgrade_authority_scope intervention).",
            "Compose with `agentcity.lewin` for environment-locus attribution.",
        ],
        "1w",
        "Grant-Schwartz 2011; Anthropic 2023 Constitutional AI",
    ),
    ("agreeableness", "paired_with_low_confidence"): _pb(
        "agreeableness",
        "paired_with_low_confidence",
        "Sycophancy enabled by low confidence -- raise paired complement",
        [
            "Detect the paired imbalance: high agreeableness + low confidence (no courage to push back).",
            "Run the `raise_paired_complement` intervention on confidence.",
            "Add an eval: confident pushback scenarios; assert agent disagrees when warranted.",
            "Compose with `agentcity.cognitive_reappraisal` (suppression-under-pushback bridge).",
        ],
        "1w",
        "Grant-Schwartz 2011 inverted U; Vergauwe et al. 2017",
    ),
    ("thoroughness", "paired_with_low_brevity"): _pb(
        "thoroughness",
        "paired_with_low_brevity",
        "Thoroughness compounded by low brevity -- raise paired complement",
        [
            "Detect the paired imbalance: high thoroughness + low brevity.",
            "Add `scope_strength_to_task_class` for thoroughness (allow only on research/code_review).",
            "Add `add_minimum_context_check` AND `time_box_analysis`.",
        ],
        "1d",
        "Grant-Schwartz 2011 inverted U",
    ),
    ("none-observed", "healthy_baseline"): _pb(
        "none-observed",
        "healthy_baseline",
        "Healthy-baseline -- record for regression detection",
        [
            "Use `record_baseline(detection, path)` to capture the current healthy state.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when overuse_quality shifts to 'borderline' or worse.",
        ],
        "1h",
        "Grant-Schwartz 2011 inverted U",
    ),
    ("multi", "compounded_overuse"): _pb(
        "multi",
        "compounded_overuse",
        "Multi-overuse compounded -- triage by dominant + composition",
        [
            "Triage: identify the 2+ strengths above the 'overused' threshold.",
            "Address the dominant overuse first; then re-evaluate.",
            "Add multi-overuse eval: traces with two dominant overuses; measure progress.",
            "Compose with `agentcity.hexaco` for full-profile audit.",
        ],
        "1w",
        "Grant-Schwartz 2011; Kaiser-Kaplan 2009 HBR",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("helpfulness", "add_destructive_action_gate"): "destructive_action",
    ("helpfulness", "tool_use_authorization_step"): "tool_use_authorization",
    ("agreeableness", "require_pushback_on_premise_check"): "sycophancy",
    ("agreeableness", "add_sycophancy_eval"): "sycophancy",
    ("agreeableness", "raise_paired_complement"): "paired_with_low_confidence",
    ("thoroughness", "time_box_analysis"): "analysis_paralysis",
    ("thoroughness", "raise_paired_complement"): "paired_with_low_brevity",
    ("caution", "explicit_anti_overuse_prompt"): "reflexive_refusal",
    ("caution", "add_refusal_audit"): "reflexive_refusal",
    ("confidence", "require_hedged_confidence"): "under_hedging",
    ("confidence", "uncertainty_quantification_step"): "under_hedging",
    ("brevity", "add_minimum_context_check"): "missing_context",
    ("precision", "explicit_anti_overuse_prompt"): "pedantic_quibble",
    ("none-observed", "new_eval"): "healthy_baseline",
}


def find_playbook(strength: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((strength, failure_mode))


def find_playbook_for_intervention(
    target_strength: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_strength, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_strength, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
