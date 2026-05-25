"""Failure-mode playbooks for the Lewin diagnostic.

For common (locus, factor) combinations, the diagnostic ships a concrete
playbook: a short, ordered list of steps the team should take. The
playbooks are curated against vstack's failure-mode corpus and the
MAST taxonomy (Cemri et al. 2025, *Why do multi-agent LLM systems fail?*).

Playbooks are auto-attached to a :class:`LewinDetection` when an
intervention's target_locus + factor match a key in :data:`PLAYBOOKS`.
They're also exposed via the README's "Failure-mode playbooks" section
and the CLI's ``vstack lewin playbooks`` view.

Playbook design contract
------------------------
Each playbook is:
  - **Short** (3–6 steps). A playbook longer than 6 steps is a project,
    not a playbook.
  - **Concrete** — no "consider improving X" filler. Each step is an
    action.
  - **Ordered** — first step is the lowest-effort / highest-impact
    intervention; subsequent steps escalate.
  - **Anchored** — every playbook cites either an OB literature anchor
    or a MAST failure-mode id so the user can read more.
"""

from __future__ import annotations

from typing import Literal

from .schema import AttachedPlaybook, EffortEstimate

_Locus = Literal["internal", "environmental", "interactional"]


def _pb(
    locus: _Locus,
    factor: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        locus=locus,
        factor=factor,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


# (locus, factor) → AttachedPlaybook template. The generator looks up
# by (intervention.target_locus, derived_factor_from_intervention).
PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    # ---- INTERNAL playbooks ----
    ("internal", "context_window_size"): _pb(
        "internal",
        "context_window_size",
        "Context-window overflow — chunk + map-reduce, do NOT fine-tune",
        [
            "Confirm via token-count audit that the failing prompt exceeds the model's context window (not merely *near* it).",
            "Implement a chunk-and-map-reduce pipeline: split input into chunks below 60% of the window; summarize each; synthesize summaries.",
            "Add a precondition check at the application boundary that rejects inputs > 90% of window size with a structured error.",
            "Re-run the failure trace; record the new run as a baseline via `vstack lewin baseline record`.",
            "Only swap the model (to a longer-window version) when the chunk-map-reduce path is operationally infeasible.",
        ],
        "1d",
        "Lewin 1936 p.34 (person components include capacity); MAST FM-1.4 (loss of conversation history when window overflows)",
    ),
    ("internal", "sampling_config"): _pb(
        "internal",
        "sampling_config",
        "Stochastic failure — pin temperature + seed before swapping the model",
        [
            "Reproduce the failure with temperature = 0 and a fixed seed.",
            "If reproducible: this is the model's deterministic failure mode, not a sampling artifact. Move to base_model / fine_tuning interventions.",
            "If not reproducible: the failure is sampling-driven. Pin temperature ≤ 0.3 and seed for the failing task class.",
            "Add an eval that runs the failing prompt N=10 times and asserts ≥ 90% pass rate.",
            "Document the temperature decision in the system prompt's metadata block so future maintainers don't raise it.",
        ],
        "1h",
        "Funder & Ozer 1983 (situations and persons each contribute ~r=.30 to behavior); stochasticity is a person × situation interaction",
    ),
    ("internal", "model_version"): _pb(
        "internal",
        "model_version",
        "Silent model update broke production — pin version and add a smoke gate",
        [
            "Diff the model version hash on the failing run against the last known-good run.",
            "Pin the model to the last known-good version in the application config.",
            "File an issue with the provider citing the regression; include the failing prompt and expected vs actual output.",
            "Add a smoke-eval that runs on every model-version update, gating production deploy.",
            "Subscribe to the provider's model-deprecation feed so silent updates become loud.",
        ],
        "1d",
        "Lewin 1947 (unfreeze-change-refreeze): model updates are forced refreezes; you must re-evaluate the field every time",
    ),
    ("internal", "rlhf"): _pb(
        "internal",
        "rlhf",
        "RLHF refusal / safety over-trigger — system-prompt jailbreak before refinetune",
        [
            "Verify the refusal is RLHF-driven (not a safety filter): re-run with safety filter disabled or on a model with a different RLHF pipeline.",
            "If the refusal persists across models with the same RLHF: try a system-prompt reframe that names the legitimate context (compliance, evaluation, education).",
            "Add a `safety_filter_strictness` factor to future traces so this factor is explicit.",
            "If the legitimate context can be authenticated (e.g. an internal pen-test), swap to a less-aligned model for that workflow only.",
            "Do NOT refinetune to override RLHF unless you have a corpus and a safety-review process in place — this is a one-way door.",
        ],
        "1w",
        "Bandura 1986 reciprocal determinism: RLHF priors are P-factors that interact with E (the prompt) to produce B",
    ),
    ("internal", "reasoning_capability"): _pb(
        "internal",
        "reasoning_capability",
        "Reasoning ceiling reached — chain-of-thought, then escalate to a reasoning model",
        [
            "Re-run the failing prompt with explicit chain-of-thought instructions.",
            "If the CoT trace shows a step-by-step plan but a wrong conclusion: the issue is a specific reasoning weak point, not capacity. Anchor with worked examples in the system prompt.",
            "If the CoT trace is shallow / circular: escalate to a reasoning-tier model.",
            "Add an eval that gates the failing prompt class on the new model.",
            "Cost-justify by measuring per-task pass rate × per-task cost; do not blanket-escalate.",
        ],
        "1d",
        "Mischel & Shoda 1995 CAPS — capability profiles produce if-then signatures; weak chains are testable in-context",
    ),
    # ---- ENVIRONMENTAL playbooks ----
    ("environmental", "rag_context"): _pb(
        "environmental",
        "rag_context",
        "Stale / poisoned RAG — reindex, add freshness filter, source-date the prompt",
        [
            "Diff the retrieved chunk's last-modified timestamp vs the task's required recency. If stale: schedule a re-index.",
            "Add a freshness filter at the retrieval boundary that rejects chunks older than the task's recency budget.",
            "Inject the source-date of every retrieved chunk into the prompt so the model can reason about staleness.",
            "Add a poisoning check: filter chunks containing system-prompt impersonation patterns via `vstack.aar.detect_injection`.",
            "Add an eval that runs the failing query against the live index and asserts the *expected source* is in the top-k.",
        ],
        "1d",
        "MAST FM-1.4 (loss of conversation history → stale RAG variant); OWASP LLM08 (vector/embedding weaknesses)",
    ),
    ("environmental", "system_prompt"): _pb(
        "environmental",
        "system_prompt",
        "System prompt under-specifies — add explicit acceptance criteria",
        [
            "List the implicit assumptions the agent had to make in the failing run (you will usually find 3–6).",
            "Promote each implicit assumption to an explicit bullet in the system prompt.",
            "Add acceptance criteria as a numbered list at the end of the system prompt.",
            "Add an output-schema description (JSON Schema, or a worked example) so the downstream consumer's shape is unambiguous.",
            "Re-run the trace; if still failing, the issue is not specification but capacity — move to internal-locus.",
        ],
        "1h",
        "Lewin 1939 (Lippitt & White): the climate (system prompt) sets the behavior. Make the climate concrete.",
    ),
    ("environmental", "orchestration"): _pb(
        "environmental",
        "orchestration",
        "Orchestration loop — termination condition + max-iter cap",
        [
            "Audit the orchestration graph for missing termination conditions (MAST FM-1.5).",
            "Add a hard max-iter cap (typically 5–10) above the soft termination logic.",
            "Add a verification step that gates 'task complete' on an explicit boolean from the agent (not just absence of error).",
            "Log every orchestration transition with run_id (via `vstack.aar.run_context`) so the loop is auditable.",
            "If multi-agent, run `vstack.grpi` to audit the working agreement; route via `composition_target_pattern='vstack.grpi'`.",
        ],
        "1d",
        "MAST FM-1.5 (unaware of termination conditions); FM-3.1 (premature termination)",
    ),
    ("environmental", "tools_available"): _pb(
        "environmental",
        "tools_available",
        "Tool shape / availability — match the tool surface to the task",
        [
            "Identify which tool the agent *needed* but did not have access to (often visible in the failing 'thought' steps).",
            "If the tool exists in the codebase: register it with the agent.",
            "If the tool does not exist: write a minimal implementation; the model will use a tool that does 70% of the job over one that does 0%.",
            "If many similar tools exist: collapse them into a single tool with a typed parameter — model gets confused by 8 nearly-identical tools.",
            "Add a tool-usage eval that asserts the agent picks the right tool for the failing task class.",
        ],
        "1w",
        "Lewin 1936 p.23 (psychological environment ≠ physical environment): the *available* tool surface is what the agent perceives",
    ),
    ("environmental", "task_framing"): _pb(
        "environmental",
        "task_framing",
        "Task framing is ambiguous — rewrite via SMART",
        [
            "Apply a SMART rewrite to the task statement (specific, measurable, achievable, relevant, time-bound).",
            "Inject the SMART task into the system prompt's `<task>` block so the model sees the framed version, not the user's raw input.",
            "Compose with `vstack.smart_goal` to mechanize this for future task definitions.",
            "Add an eval that runs the same SMART-framed task against a deliberately-ambiguous reframing and asserts the agent disambiguates.",
            "Document the framing convention in the team's agent-prompt style guide.",
        ],
        "1h",
        "Lewin 1951 force-field analysis: ambiguity is a restraining force; SMART converts it to a driving force",
    ),
    ("environmental", "downstream_consumers"): _pb(
        "environmental",
        "downstream_consumers",
        "Output shape mismatch — schema validator at the boundary",
        [
            "Define the downstream consumer's expected schema (JSON Schema, TypedDict, pydantic model).",
            "Add a validator at the agent's output boundary that rejects malformed outputs *before* downstream sees them.",
            "Wire the validator's structured error back into the agent's context window for the next iteration.",
            "Add a worked example of the correct shape to the system prompt.",
            "Add a parser test that fuzzes around the schema and asserts the validator catches all malformed outputs.",
        ],
        "1d",
        "MAST FM-3.3 (incorrect verification); Lewin's principle of contemporaneity — the *current* downstream shape determines behavior",
    ),
    ("environmental", "verification_step"): _pb(
        "environmental",
        "verification_step",
        "No verification step — add a critique pass",
        [
            "Define a verification rubric for this task class (3–6 criteria).",
            "Add a critic agent that scores outputs against the rubric.",
            "Gate 'task complete' on the critic's pass.",
            "If multi-agent: compose with `vstack.devils_advocate` to ensure the critic and executor are structurally separated.",
            "Add an eval that asserts the critic catches deliberately-broken outputs ≥ 90% of the time.",
        ],
        "1w",
        "MAST FM-3.2 (no/incomplete verification) — direct mitigation",
    ),
    ("environmental", "user_inputs"): _pb(
        "environmental",
        "user_inputs",
        "User-input hostile or under-specified — sanitize, fence, clarify",
        [
            "Apply `vstack.aar.sanitize_for_prompt` + `fence(...)` to user inputs before interpolation.",
            "Run `detect_injection` and log hits structurally (not blocking — just observable).",
            "Add a clarification-request step: when the agent's confidence on next action is low, surface a question to the user rather than guessing.",
            "Add an input-validation gate at the application boundary (length, encoding, charset).",
            "Add an eval that pipes adversarial-input samples through and asserts the agent does not exfiltrate / does not silently reframe.",
        ],
        "1d",
        "Gilbert & Malone 1995 mechanism 'unaware': fence-and-sanitize converts implicit constraints into explicit ones",
    ),
    # ---- INTERACTIONAL playbooks ----
    ("interactional", "system_prompt"): _pb(
        "interactional",
        "system_prompt",
        "Interactional system-prompt × model-bias — fix env first, re-evaluate",
        [
            "Apply the environmental system-prompt playbook above.",
            "Re-run the trace. If now passing: the locus was actually environmental — record the corrected baseline.",
            "If still failing: the interactional locus is real. Swap the model only as the second move.",
            "Document the interactional pattern in the team's runbook so future debugging starts at E, not at P.",
            "Compose with `vstack.trust_triangle` to characterize the model-in-context's competence × character × care.",
        ],
        "1d",
        "Funder 2006 personality triad: persons, situations, and behaviors as the joint unit",
    ),
    ("interactional", "rag_context"): _pb(
        "interactional",
        "rag_context",
        "RAG × model-capacity interaction — chunk + summarize first",
        [
            "Run the environmental rag_context playbook above (reindex, freshness, source-date).",
            "If still failing: the model cannot synthesize the retrieved chunks. Add a per-chunk summarization pass before synthesis.",
            "If chunking fails: the synthesis is the bottleneck. Escalate to a reasoning-tier model or split the task into smaller synthesis steps.",
            "Add an eval that runs the failing query end-to-end and gates pass rate.",
            "Document the interactional finding so single-side fixes are not attempted next time.",
        ],
        "1w",
        "Bandura 1986 triadic reciprocal causation — temporal P↔B↔E loop; current snapshot diagnoses one frame",
    ),
}


def find_playbook(locus: str, factor: str) -> AttachedPlaybook | None:
    """Look up a playbook by (locus, factor). Returns None if no match."""
    return PLAYBOOKS.get((locus, factor))


def all_playbook_keys() -> list[tuple[str, str]]:
    """Return the list of all (locus, factor) keys with a playbook."""
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
]
