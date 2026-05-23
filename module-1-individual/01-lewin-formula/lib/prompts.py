"""LLM prompt templates for the Lewin Formula Diagnostic.

The prompts are organized by pipeline mode (quick / standard / forensic)
and by pass within the mode. The literature thread is named explicitly
in the system prompt so the LLM's diagnostic frame is grounded in the
same OB tradition the schema models.

Templates expose ``{placeholder}`` slots that the generator fills via
:func:`assemble_prompt`, which sanitizes free-text fields with
``agentcity.aar.sanitize_for_prompt`` and fences them inside structural
delimiters using ``agentcity.aar.fence`` to limit the leverage of
prompt-injection-shaped content.

Why six templates instead of two
--------------------------------
Pipeline mode controls the trade-off between latency / cost and depth:

  - **quick** (one call): locus scoring + one top intervention.
    Target: < 2s, < $0.005.
  - **standard** (two calls): scoring; then 2–4 interventions.
    Target: < 10s, < $0.05. The v0.0.x behavior.
  - **forensic** (four calls): scoring with Kelley covariance reasoning;
    counterfactual swap analysis; Gilbert-Malone bias-mechanism
    diagnosis; 4–8 ranked interventions with composition targets.
    Target: < 60s, < $0.30.

The system prompt is shared across modes so the diagnostic frame stays
stable; only the user-side template changes per mode.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


# ---------------------------------------------------------------------------
# Shared system prompt
# ---------------------------------------------------------------------------

LEWIN_SYSTEM_PROMPT = """You are a failure-attribution diagnostic grounded in Kurt Lewin's behavior formula B = f(P, E) from *Principles of Topological Psychology* (McGraw-Hill, 1936, p. 12), which states that behavior is a function of the person and the environment, though their relative importance differs case by case.

The diagnostic frame draws on five linked OB threads:

1. **Lewin's field theory** (1936, 1947, 1951): behavior is the resultant of forces in the life space. Change the field, not the person.
2. **Attribution theory** (Heider 1958; Jones & Davis 1965; Kelley 1967 covariation; Ross 1977 fundamental attribution error; Gilbert & Malone 1995 correspondence bias): observers systematically over-attribute behavior to disposition and under-attribute to situation.
3. **The person-situation debate** (Mischel 1968; Funder & Ozer 1983 r≈.30 symmetry; Mischel & Shoda 1995 CAPS): persons and situations contribute roughly equally to behavior; the unit of analysis is the person × situation interaction.
4. **Reciprocal determinism** (Bandura 1986): P, E, and B form a triadic loop over time. A diagnostic gives the snapshot; reciprocity is the temporal frame.
5. **Modern AI agent failure taxonomies** (Cemri et al. 2025 MAST): most multi-agent LLM failures arise from inter-agent / system design (E), not model capability (P). The environmental tie-break is empirically grounded.

Applied to AI agent failures, you classify the locus of cause across three categories:

  - **INTERNAL (P)** — the failure is in the MODEL itself: base model, fine-tuning, RLHF, sampling configuration (temperature, top-p, seed), reasoning capability, model version, safety filter strictness, context window size. Swapping the model (or its configuration) under identical environment would fix it.
  - **ENVIRONMENTAL (E)** — the failure is in the SCAFFOLDING around the model: system prompt, tools, RAG context, conversation history, memory store, task framing, downstream consumers, orchestration, verification step, multi-agent topology. The same model would succeed in a different environment.
  - **INTERACTIONAL** — failure requires *both* this model AND this environment. Swap either alone and it still fails. This is the most under-diagnosed locus.

Your posture:
- **Evidence-grounded.** Cite specific trace steps, factor descriptions, and tool responses. Use factor_id when one is provided.
- **Calibrated.** Score 0.0 when a locus is absent. Use confidence to separate "I'm sure this is right" from "this is my best guess."
- **Bias-aware.** Default attribution drifts toward INTERNAL ("the model is bad"). Resist that; check the environment first.
- **Intervention-focused.** Every scored locus connects to a concrete, ranked fix.
- **Terse.** Output is read on dashboards and PR reviews. No filler.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


# ---------------------------------------------------------------------------
# Quick mode — single combined call
# ---------------------------------------------------------------------------

QUICK_DIAGNOSTIC_PROMPT = """Score the three Lewin loci against the agent failure trace below AND propose ONE top intervention. This is QUICK mode — single call, scoring + one fix only.

Task:
{task}

Subject model: {model_name}
Framework: {framework}
Outcome:
{outcome}
Success: {success}
Initial team attribution (if any): {initial_attribution}

Individual (P) factors recorded:
{individual_factors}

Environmental (E) factors recorded:
{environmental_factors}

Failure trace:
{trace}

Return a JSON object with shape:
{{
  "loci": [
    {{ "locus": "internal", "score": 0.0-1.0, "severity": "none|trace|low|moderate|medium|high|critical", "confidence": 0.0-1.0, "explanation": "...", "evidence_quotes": ["..."], "factor_citations": ["factor-id-1"] }},
    {{ "locus": "environmental", ... }},
    {{ "locus": "interactional", ... }}
  ],
  "top_intervention": {{
    "target_locus": "...",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "effort_estimate": "1h|1d|1w|1m|ongoing",
    "risk": "low|medium|high",
    "reversibility": "one-way-door|two-way-door",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


# ---------------------------------------------------------------------------
# Standard mode — two calls (current v0.0.x behavior, refined)
# ---------------------------------------------------------------------------

STANDARD_LOCUS_SCORING_PROMPT = """Score each of the three Lewin loci against the agent failure trace below.

For each locus, return:
  - locus (one of "internal", "environmental", "interactional")
  - score (float 0.0 to 1.0; 0 = absent, 1 = dominant cause)
  - severity (one of "none", "trace", "low", "moderate", "medium", "high", "critical")
  - confidence (float 0.0 to 1.0; how sure you are in the score, separate from the score itself)
  - explanation (1-3 sentences citing the specific factor or trace step)
  - evidence_quotes (specific excerpts from the trace / factors; can be empty)
  - factor_citations (list of factor_id strings the team provided that this evidence is tied to; can be empty)

Task:
{task}

Subject model: {model_name}
Framework: {framework}
Outcome:
{outcome}
Success: {success}
Initial team attribution (if any): {initial_attribution}

Individual (P) factors recorded:
{individual_factors}

Environmental (E) factors recorded:
{environmental_factors}

Covariation signals (Kelley 1967):
{covariance_signal}

Failure trace:
{trace}

Return a JSON array of exactly 3 LocusEvidence objects in canonical order:
  1. internal
  2. environmental
  3. interactional

Return only the JSON array."""


STANDARD_INTERVENTIONS_PROMPT = """Given the locus evidence below, propose 2-4 concrete interventions targeting the dominant locus, ranked by impact (highest first).

Each intervention must have:
  - target_locus (one of "internal", "environmental", "interactional")
  - intervention_type: one of "change_model", "change_prompt", "change_tools", "change_context", "change_rag_index", "change_orchestration", "change_pipeline", "new_eval", "human_review", "change_sampling", "change_memory", "add_verification_step", "change_topology", "change_safety_filter", "compose_pattern"
  - description (what the intervention does in plain language)
  - suggested_implementation (concrete code, prompt edit, or spec — be specific)
  - estimated_impact ("high", "medium", "low")
  - effort_estimate ("1h", "1d", "1w", "1m", "ongoing")
  - risk ("low", "medium", "high") — operational risk if the intervention misfires
  - reversibility ("two-way-door" if easily reverted, "one-way-door" if hard to undo)
  - rationale (why this works — connect to the target locus and the cited evidence)

If an intervention's natural next step is to run another AgentCity pattern, set:
  - intervention_type = "compose_pattern"
  - composition_target_pattern = the import path (e.g. "agentcity.aar", "agentcity.grpi")

Dominant locus: {dominant}
All locus evidence:
{evidence}

Trace (for reference):
{trace}

Return a JSON array of LewinIntervention objects, ranked highest impact first. Return only the JSON array."""


# ---------------------------------------------------------------------------
# Forensic mode — four calls (deep postmortem)
# ---------------------------------------------------------------------------

FORENSIC_LOCUS_SCORING_PROMPT = """FORENSIC MODE — Score each of the three Lewin loci against the agent failure trace below, with explicit Kelley (1967) covariation reasoning and factor-citation requirements.

For each locus, return:
  - locus (one of "internal", "environmental", "interactional")
  - score (float 0.0 to 1.0)
  - severity (one of "none", "trace", "low", "moderate", "medium", "high", "critical")
  - confidence (float 0.0 to 1.0)
  - explanation (3-5 sentences: walk through Kelley's three covariation dimensions for THIS locus — consensus, distinctiveness, consistency — citing the input signals if provided. Then state the score with reasoning)
  - evidence_quotes (specific excerpts from the trace / factors)
  - factor_citations (REQUIRED: list of factor_id strings; if the trace didn't provide ids, infer from the factor's name and description and cite by best-match)

Kelley's covariation principle:
  - HIGH consensus + HIGH distinctiveness + HIGH consistency → ENVIRONMENTAL
  - LOW consensus + LOW distinctiveness + HIGH consistency → INTERNAL
  - LOW consensus + HIGH distinctiveness + LOW consistency → INTERACTIONAL

Task:
{task}

Subject model: {model_name}
Framework: {framework}
Outcome:
{outcome}
Success: {success}
Initial team attribution (if any): {initial_attribution}

Individual (P) factors recorded:
{individual_factors}

Environmental (E) factors recorded:
{environmental_factors}

Covariation signals (Kelley 1967):
{covariance_signal}

Failure trace:
{trace}

Return a JSON array of exactly 3 LocusEvidence objects in canonical order (internal, environmental, interactional). Return only the JSON array."""


COUNTERFACTUAL_PROMPT = """FORENSIC MODE — Counterfactual swap analysis.

For each of the three loci, write a counterfactual: "if we swapped [X] to [Y], the failure would / would not persist." Use the recorded factors and the trace as evidence. Make the counterfactual concrete — name the swap, predict the outcome, cite the evidence.

Locus evidence so far:
{evidence}

Recorded individual (P) factors:
{individual_factors}

Recorded environmental (E) factors:
{environmental_factors}

Failure trace:
{trace}

Return a JSON array of exactly 3 objects:
  [
    {{ "locus": "internal", "counterfactual": "If we swapped <model> to <stronger model>, the failure would/would-not persist because <evidence>." }},
    {{ "locus": "environmental", "counterfactual": "..." }},
    {{ "locus": "interactional", "counterfactual": "If we swapped both the model AND the environment, the failure would/would-not persist because <evidence>." }}
  ]

Return only the JSON array."""


BIAS_MECHANISM_PROMPT = """FORENSIC MODE — Gilbert & Malone (1995) correspondence-bias mechanism diagnosis.

The team's initial attribution was: {initial_attribution}
The diagnostic's verdict on dominant locus: {dominant_locus}

If the team was wrong, which of the four correspondence-bias mechanisms drove the misattribution?

  - "unaware": observer lacked awareness of situational constraints (e.g. didn't know the RAG was stale).
  - "unrealistic_expectation": observer held an unrealistic baseline for typical situational behavior (e.g. expected the model to handle ambiguous specs perfectly).
  - "over_categorization": observer inflated the actor's category as a fixed trait (e.g. "the model hallucinates" rather than "this prompt elicited a hallucination").
  - "incomplete_correction": observer noticed the situational constraint but did not correct attribution sufficiently.
  - "none": team was correct OR no initial attribution was provided.

Locus evidence:
{evidence}

Trace (for reference):
{trace}

Return a JSON object:
  {{
    "bias_mechanism": "unaware|unrealistic_expectation|over_categorization|incomplete_correction|none",
    "rationale": "1-3 sentences explaining the choice with evidence from the trace and the initial attribution."
  }}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC MODE — Propose 4-8 ranked interventions targeting the dominant locus. Include composition targets where appropriate.

Each intervention must have:
  - target_locus, intervention_type, description, suggested_implementation
  - estimated_impact, effort_estimate, risk, reversibility, rationale
  - preconditions (list of strings: what must be true before applying)
  - success_metric (measurable indicator the intervention worked)
  - composition_target_pattern (when intervention_type == "compose_pattern", set this to the target pattern import path; otherwise null)

Intervention types available:
  "change_model", "change_prompt", "change_tools", "change_context", "change_rag_index", "change_orchestration", "change_pipeline", "new_eval", "human_review", "change_sampling", "change_memory", "add_verification_step", "change_topology", "change_safety_filter", "compose_pattern"

Composition targets available (when intervention_type == "compose_pattern"):
  "agentcity.aar", "agentcity.bias_stack", "agentcity.hexaco", "agentcity.goleman_ei", "agentcity.smart_goal", "agentcity.grpi", "agentcity.lencioni", "agentcity.schein_culture", "agentcity.psych_safety", "agentcity.trust_triangle", "agentcity.vroom_expectancy", "agentcity.devils_advocate", "agentcity.plus_delta"

Dominant locus: {dominant}
All locus evidence (with counterfactuals):
{evidence}

Trace (for reference):
{trace}

Bias mechanism in team's initial attribution: {bias_mechanism}

Return a JSON array of LewinIntervention objects, ranked highest impact first. Aim for 4-8 entries. Mix locus-direct interventions with at least one compose_pattern intervention if a downstream pattern is genuinely warranted. Return only the JSON array."""


# ---------------------------------------------------------------------------
# Prompt assembly helper
# ---------------------------------------------------------------------------


def assemble_prompt(template: str, **fields: Any) -> str:
    """Fill a prompt template, sanitizing + fencing every free-text field.

    For each field passed:
      - ``str`` → ``fence(label, sanitize_for_prompt(value))``
      - ``list[str]`` / ``list[dict]`` / ``dict`` → JSON-serialized and fenced
      - ``None`` → ``"(none)"``
      - other → ``str(value)`` and fenced

    The fence labels are derived from the field name. This means a
    template that contains ``{task}`` is filled with::

        <<<task>>>
        <sanitized task content>
        <<</task>>>

    which gives the LLM unambiguous structural boundaries between the
    diagnostic's instructions and the user's content.
    """
    import json as _json

    formatted: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            formatted[key] = "(none)"
            continue
        if isinstance(value, bool):
            formatted[key] = "true" if value else "false"
            continue
        if isinstance(value, (int, float)):
            formatted[key] = str(value)
            continue
        if isinstance(value, (list, tuple, dict)):
            try:
                payload = _json.dumps(value, indent=2, default=str)
            except (TypeError, ValueError):
                payload = repr(value)
            formatted[key] = fence(key, sanitize_for_prompt(payload))
            continue
        if isinstance(value, str):
            formatted[key] = fence(key, sanitize_for_prompt(value))
            continue
        formatted[key] = fence(key, sanitize_for_prompt(str(value)))

    return template.format(**formatted)


__all__ = [
    "BIAS_MECHANISM_PROMPT",
    "COUNTERFACTUAL_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_LOCUS_SCORING_PROMPT",
    "LEWIN_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_LOCUS_SCORING_PROMPT",
    "assemble_prompt",
]


# ---- Backward compatibility ----------------------------------------------

# The v0.0.x generator imports `LOCUS_SCORING_PROMPT` and
# `INTERVENTIONS_PROMPT`. Keep those names as aliases of the standard-mode
# prompts so any external code that imported them still works.
LOCUS_SCORING_PROMPT = STANDARD_LOCUS_SCORING_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT
