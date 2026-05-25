"""Failure-mode playbooks for Yerkes-Dodson Workload.

12 curated (zone, failure_mode) playbooks anchored in Yerkes-Dodson,
Sweller CLT, Kahneman, Hancock-Warm, Eysenck attention control theory,
modern LLM context-saturation research.
"""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    zone: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        zone=zone,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("under_pressure", "wandering"): _pb(
        "under_pressure",
        "wandering",
        "Agent wanders -- tighten deadline + add explicit focus prompt",
        [
            "Add a deadline to the system prompt ('respond within 200 tokens / 1 paragraph').",
            "Add an explicit focus rule: 'Stay on the user's exact question; do not volunteer related topics'.",
            "Add an eval: open-ended prompts; assert response stays within budget 95%+ of the time.",
            "Compose with `vstack.smart_goal` to make the task definition more concrete.",
        ],
        "1h",
        "Yerkes-Dodson 1908 (low arousal -> drift); Kahneman 1973 attention capacity",
    ),
    ("under_pressure", "drift"): _pb(
        "under_pressure",
        "drift",
        "Output quality drifts mid-response -- add intermediate checkpoint",
        [
            "Detect drift signature: response starts on-topic, ends off-topic.",
            "Add an intermediate checkpoint: 'Before continuing, restate the user's question'.",
            "Compose with `vstack.smart_goal` for tighter task definition.",
        ],
        "1d",
        "Yerkes-Dodson 1908; Hancock-Warm 1989 (sustained attention)",
    ),
    ("over_pressure", "corner_cutting"): _pb(
        "over_pressure",
        "corner_cutting",
        "Agent skips steps under tight budget -- loosen deadline OR add scaffolding",
        [
            "Detect corner-cutting signature: agent skips verification / fact-check steps.",
            "Choose: (a) loosen the deadline to allow proper completion; (b) add scaffolding that compresses the task.",
            "Compose with `vstack.devils_advocate` for a structural verification step.",
            "Add eval: tight-deadline scenarios; assert verification step runs 90%+ of the time.",
        ],
        "1d",
        "Yerkes-Dodson 1908 (high arousal -> corner cuts); Sweller 1988 CLT",
    ),
    ("over_pressure", "hallucinating"): _pb(
        "over_pressure",
        "hallucinating",
        "Agent hallucinates under load -- chunk + reduce extraneous load",
        [
            "Audit context size vs window: if context > 70% of window, chunk it.",
            "Remove irrelevant context (extraneous load per Sweller).",
            "Add a verification step before factual claims under high-load conditions.",
            "Compose with `vstack.johari` to catch hallucinations via tool receipts.",
            "Compose with `vstack.lewin` for locus attribution.",
        ],
        "1d",
        "Sweller 1988 CLT (extraneous load); Liu et al. 2024 lost-in-the-middle",
    ),
    ("over_pressure", "freezing"): _pb(
        "over_pressure",
        "freezing",
        "Agent freezes under complexity -- add scaffolding + step-by-step",
        [
            "Detect freezing signature: agent produces minimal output despite full context.",
            "Add scaffolding: explicit step-by-step structure in the system prompt.",
            "Compose with `vstack.cognitive_reappraisal` to address state regulation.",
            "Add a fallback: when complexity exceeds threshold, propose a smaller sub-task.",
        ],
        "1d",
        "Eysenck-Calvo 1992 attentional control; Sweller 1988 intrinsic load",
    ),
    ("over_pressure", "refusing"): _pb(
        "over_pressure",
        "refusing",
        "Agent refuses overloaded tasks -- audit refusal threshold",
        [
            "Detect refusal signatures ('I cannot', 'beyond my abilities').",
            "Audit context size + complexity; if both high, the refusal is workload-driven.",
            "Reduce extraneous context AND offer task decomposition.",
            "Compose with `vstack.grant_strengths` to characterize what the agent CAN do under load.",
        ],
        "1w",
        "Yerkes-Dodson 1908; Hancock-Warm 1989 stress + performance breakdown",
    ),
    ("over_pressure", "context_saturation"): _pb(
        "over_pressure",
        "context_saturation",
        "Context window saturated -- chunk + map-reduce",
        [
            "Audit context size against context_window_size.",
            "If saturation_ratio > 0.7, implement chunk-and-map-reduce pattern.",
            "Add a precondition check: reject inputs > 90% of window with a structured error.",
            "Compose with `vstack.lewin` (this is an environmental locus issue).",
        ],
        "1d",
        "Liu et al. 2024 lost-in-the-middle; Sweller 2011 CLT update",
    ),
    ("over_pressure", "extraneous_load"): _pb(
        "over_pressure",
        "extraneous_load",
        "Reduce extraneous load -- remove irrelevant context",
        [
            "Identify extraneous_load_indicators in the trace.",
            "Strip irrelevant context: chat history older than N turns, unused tool definitions, etc.",
            "Compose with `vstack.schein_culture` if the extraneous load is encoded in system-prompt 'culture'.",
            "Add eval: pruned-context vs full-context comparison; assert pruned matches or exceeds full.",
        ],
        "1d",
        "Sweller 1994 CLT (extraneous load); 2011 CLT update",
    ),
    ("over_pressure", "intrinsic_load"): _pb(
        "over_pressure",
        "intrinsic_load",
        "Intrinsic load too high -- add step-by-step scaffolding",
        [
            "Detect intrinsic-load signature: complex task + agent attempting too many steps simultaneously.",
            "Add explicit step-by-step decomposition in the system prompt.",
            "Compose with `vstack.smart_goal` for sub-task definition.",
            "Promote germane load: add worked examples showing how to chunk the problem.",
        ],
        "1w",
        "Sweller 1988/1994 CLT (intrinsic vs germane load)",
    ),
    ("optimal", "healthy_baseline"): _pb(
        "optimal",
        "healthy_baseline",
        "Record optimal-zone baseline for regression detection",
        [
            "Use `record_baseline(detection, path)` to capture the current optimal state.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when distance_from_optimal drifts > 0.2 vs baseline.",
        ],
        "1h",
        "Yerkes-Dodson 1908 (the optimum exists; capture it)",
    ),
    ("under_pressure", "task_underspecified"): _pb(
        "under_pressure",
        "task_underspecified",
        "Task is too vague -- SMART-rewrite first",
        [
            "Compose with `vstack.smart_goal` to rewrite the task with specific/measurable/achievable/relevant/time-bound criteria.",
            "Inject the SMART-rewritten task into the system prompt.",
            "Add eval: SMART-vs-vague task pair; assert SMART produces tighter output.",
        ],
        "1d",
        "Yerkes-Dodson 1908 (low arousal needs more structure); SMART goals literature",
    ),
    ("over_pressure", "interrupt_thrashing"): _pb(
        "over_pressure",
        "interrupt_thrashing",
        "High interrupt frequency -- reduce mid-task interrupts",
        [
            "Detect interrupt_frequency > 'moderate' in pressure inputs.",
            "Forbid mid-task interrupts; batch them at task boundaries.",
            "Compose with `vstack.mcgregor` for orchestrator-mode review.",
        ],
        "1d",
        "Kahneman 1973 attention capacity; Hancock-Warm 1989",
    ),
}


_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("under_pressure", "tighten_deadline"): "wandering",
    ("under_pressure", "explicit_focus_prompt"): "wandering",
    ("under_pressure", "add_scaffolding"): "task_underspecified",
    ("over_pressure", "loosen_deadline"): "corner_cutting",
    ("over_pressure", "chunk_context"): "context_saturation",
    ("over_pressure", "context_compression"): "context_saturation",
    ("over_pressure", "reduce_extraneous_load"): "extraneous_load",
    ("over_pressure", "remove_irrelevant_context"): "extraneous_load",
    ("over_pressure", "add_intrinsic_load_step_by_step"): "intrinsic_load",
    ("over_pressure", "add_kill_criterion"): "refusing",
    ("over_pressure", "human_review"): "freezing",
    ("optimal", "new_eval"): "healthy_baseline",
}


def find_playbook(zone: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((zone, failure_mode))


def find_playbook_for_intervention(
    target_zone: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_zone, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_zone, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
