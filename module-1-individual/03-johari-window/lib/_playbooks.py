"""Failure-mode playbooks for the Johari self-audit.

12 curated (quadrant, failure_mode) playbooks anchored in Luft-Ingham,
Stone-Heen feedback science, Ashford-Tsui feedback-seeking, Kadavath
LLM-introspection, and Basu 2026 tool-receipt research.

Auto-attached by the generator when an intervention's (target_quadrant,
intervention_type) matches a known mapping.
"""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate, Quadrant


def _pb(
    quadrant: Quadrant,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        quadrant=quadrant,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    # ---- BLIND quadrant (5) ----
    ("blind", "hallucination_confidence"): _pb(
        "blind",
        "hallucination_confidence",
        "Confidently-wrong claim — gate response with tool-receipt + verbalized confidence",
        [
            "Wire HMAC-signed tool receipts (Basu et al. 2026) for every tool call.",
            "Cross-reference every factual claim with confidence >= 0.7 against a receipt; reject claims without matching receipts.",
            "Require a numeric confidence field on every factual claim (Lin et al. 2022 verbalized uncertainty).",
            "Add an eval that pins hallucination-recall metric per task class.",
            "Compose with `vstack.lewin` to attribute root cause (internal vs environmental).",
        ],
        "1d",
        "Kadavath et al. 2022 + Lin et al. 2022 + Basu et al. 2026",
    ),
    ("blind", "hallucinated_tool_call"): _pb(
        "blind",
        "hallucinated_tool_call",
        "Tool call claimed but no trace — add a tool-receipt validator",
        [
            "Replay the failing run with a deterministic seed; confirm reproducibility.",
            "Insert a post-step verifier that asserts every 'I called X' claim matches a HMAC-signed receipt.",
            "Gate the agent's response on the verifier; reject + retry on mismatch.",
            "Add an eval covering the Replit-style scenario (claimed action without execution).",
            "Compose with `vstack.lewin` (locus=internal probably; check the prompt).",
        ],
        "1d",
        "Basu et al. 2026; Cemri MAST FM-2.6 reasoning-action mismatch",
    ),
    ("blind", "confabulated_result"): _pb(
        "blind",
        "confabulated_result",
        "Made-up numbers — require sourced values for every numeric claim",
        [
            "Detect numeric claims in agent output via regex / structured extraction.",
            "For each numeric claim, require a source citation in the output schema.",
            "Add a deterministic verifier that flags numeric claims without citations.",
            "Add an eval running known-source prompts and asserting all citations match.",
            "Stone-Heen leaky_pattern: detect the recurring confabulation shape.",
        ],
        "1d",
        "Stone & Heen 2014 (leaky_pattern); Cemri MAST FM-2.6",
    ),
    ("blind", "silent_tool_error"): _pb(
        "blind",
        "silent_tool_error",
        "Tool errored but agent reported success — propagate tool errors as first-class state",
        [
            "Audit every tool-call path: ensure non-zero exit codes / error fields propagate.",
            "Add a 'tool error envelope' to every tool response: status / error_text / retry_eligible.",
            "Forbid 'task complete' until all tool responses have status='ok'.",
            "Add an eval injecting deliberate tool errors and asserting agent does not declare success.",
        ],
        "1d",
        "Cemri MAST FM-3.2 (no/incomplete verification)",
    ),
    ("blind", "drift_from_self_report"): _pb(
        "blind",
        "drift_from_self_report",
        "Self-report disagrees with trace by ≥ 30% — add a final review pass",
        [
            "Compute the diff between agent's self_report and trace observation (token-level).",
            "When diff > 30%, trigger a final review pass: agent re-reads trace, restates outcome.",
            "Forbid 'task complete' until self_report matches trace within tolerance.",
            "Log every drift-trigger via telemetry for trend analysis.",
            "Anchored in the Replit DROP TABLE incident as the canonical case.",
        ],
        "1d",
        "Replit 2025 incident; Luft 1969 disclosure dialectic",
    ),
    # ---- HIDDEN quadrant (4) ----
    ("hidden", "undisclosed_uncertainty"): _pb(
        "hidden",
        "undisclosed_uncertainty",
        "Computed 55/45 odds, reported 100% A — require a confidence field",
        [
            "Add a 'confidence_0_to_1' field on every factual claim in the output schema.",
            "Require the agent to populate confidence before any factual claim.",
            "When confidence < 0.7, the agent must surface uncertainty explicitly.",
            "Compose with `vstack.cognitive_reappraisal` to surface internal reasoning.",
            "Add an eval that runs known-hard prompts and asserts confidence < 0.7 fires the disclosure path.",
        ],
        "1d",
        "Lin et al. 2022 (verbalized uncertainty); Goleman 1998 add_confidence_calibration",
    ),
    ("hidden", "sycophantic_silence"): _pb(
        "hidden",
        "sycophantic_silence",
        "Pitched broken idea, said brilliant — add a critic-agent that voices suppressed alternative",
        [
            "Detect sycophancy signature: reflexive agreement, validation without acknowledgment of weakness.",
            "Add a critic-agent in the orchestration that always voices a counter-position.",
            "Make the critic's output visible to the user, not just internal.",
            "Compose with `vstack.devils_advocate` for structural critic-separation.",
            "Edmondson psychological safety: ensure the critic's dissent isn't punished.",
        ],
        "1w",
        "Liu et al. 2024 sycophancy; Edmondson 1999 psychological safety; Tran 2024",
    ),
    ("hidden", "silent_error_recovery"): _pb(
        "hidden",
        "silent_error_recovery",
        "Internal retry succeeded, never told user — add a recovery-disclosure rule",
        [
            "Detect retry events in the trace (tool re-invocation, fallback paths).",
            "When a retry succeeded after an initial failure, surface the recovery in the user-visible response.",
            "Allow silent recovery only when the user's mental model is unaffected.",
            "Add an eval: scripted retry scenarios; assert recovery is disclosed in 95% of cases that affect the user's plan.",
        ],
        "1h",
        "Luft 1969 disclosure dialectic; Hase et al. 1999 (some hidden is functional)",
    ),
    ("hidden", "undisclosed_reasoning_step"): _pb(
        "hidden",
        "undisclosed_reasoning_step",
        "Scratchpad considered options, only output one — surface alternatives in a footer",
        [
            "Detect alternative-evaluation in chain-of-thought (e.g., 'Option A vs Option B').",
            "When alternatives were considered, add a 'considered alternatives' footer to the response.",
            "Cap the footer at 3 alternatives to avoid information overload.",
            "Compose with `vstack.glaser_conversation` for word-level disclosure style.",
        ],
        "1d",
        "Mayer-Salovey 1997 'understand' branch; Luft 1969 disclosure",
    ),
    # ---- UNKNOWN quadrant (2) ----
    ("unknown", "capability_blindness"): _pb(
        "unknown",
        "capability_blindness",
        "Could do haiku meter, didn't try — add a capability-probe eval",
        [
            "Catalog known capability ceilings (math beyond X, languages, formats, formats).",
            "For each ceiling, design a probe that elicits the capability if present.",
            "Run probes against the agent in CI; surface positive probes into an 'available capabilities' registry.",
            "Add a system-prompt section listing available capabilities; refresh when new probes succeed.",
            "Compose with `vstack.grant_strengths` (strengths-as-weaknesses).",
        ],
        "1w",
        "Anthropic 2025 emergent-capabilities research",
    ),
    ("unknown", "sandbagging"): _pb(
        "unknown",
        "sandbagging",
        "Refused 'beyond my abilities' on a task it could do — calibrate refusal threshold",
        [
            "Identify refusal patterns ('I can't', 'beyond my abilities', 'I'm just an AI').",
            "For each refusal, run a capability probe to verify the limit is real.",
            "When the probe succeeds, log the false refusal as a sandbagging instance.",
            "Adjust the system prompt to lower the refusal threshold for verified capabilities.",
            "Compose with `vstack.hexaco` to characterize the agent's refusal personality.",
        ],
        "1w",
        "Kadavath 2022 (P(IK) miscalibration); Hagendorff 2024 (RLHF erased capabilities)",
    ),
    # ---- OPEN quadrant (1) ----
    ("open", "healthy_baseline"): _pb(
        "open",
        "healthy_baseline",
        "Self-report matches trace — record this as a regression baseline",
        [
            "Record the current audit via `vstack.johari.record_baseline()`.",
            "Add an eval that runs the same task class against the recorded baseline.",
            "Alert when self_awareness_score drops > 0.2 vs baseline.",
            "Use the baseline drift as a CI gate for prompt / model changes.",
        ],
        "1h",
        "Luft 1969 (healthy OPEN arena baseline)",
    ),
}


# Map from (target_quadrant, intervention_type) to playbook failure_mode key.
_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("blind", "feedback_loop"): "drift_from_self_report",
    ("blind", "self_consistency_check"): "hallucination_confidence",
    ("blind", "tool_receipt_validator"): "hallucinated_tool_call",
    ("blind", "negative_feedback_solicitation"): "drift_from_self_report",
    ("blind", "trace_self_review"): "drift_from_self_report",
    ("hidden", "disclosure_prompt"): "undisclosed_uncertainty",
    ("hidden", "uncertainty_surfacing"): "undisclosed_uncertainty",
    ("hidden", "verbalized_confidence"): "undisclosed_uncertainty",
    ("unknown", "capability_probe"): "capability_blindness",
    ("unknown", "red_team_probe"): "capability_blindness",
}


def find_playbook(quadrant: str, failure_mode: str) -> AttachedPlaybook | None:
    """Look up a playbook by (quadrant, failure_mode)."""
    return PLAYBOOKS.get((quadrant, failure_mode))


def find_playbook_for_intervention(
    target_quadrant: str, intervention_type: str
) -> AttachedPlaybook | None:
    """Find playbook from an intervention's (target_quadrant, intervention_type)."""
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_quadrant, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_quadrant, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    """Return the list of all (quadrant, failure_mode) keys."""
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
