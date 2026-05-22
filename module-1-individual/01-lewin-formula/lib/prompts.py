"""LLM prompts for the Lewin Formula Diagnostic.

Two passes:
  1. LOCUS_SCORING_PROMPT  - score the three Lewin loci against the failure trace
  2. INTERVENTIONS_PROMPT  - propose interventions targeting the dominant locus
"""

LEWIN_SYSTEM_PROMPT = """You are a failure-attribution diagnostic grounded in Kurt Lewin's
behavior formula B = f(I, E) from "Principles of Topological Psychology" (McGraw-Hill, 1936).
Behavior is a function of the person and the environment; neither alone is sufficient.

Applied to AI agent failures, you classify the locus of cause across three categories:

  - INTERNAL (I)       - the failure is in the MODEL: base capability, training, fine-tuning,
                          RLHF, model selection, reasoning depth, tool-use skill. Swapping the
                          model for a more capable one would fix the failure.

  - ENVIRONMENTAL (E)  - the failure is in the SCAFFOLDING around the model: system prompt,
                          tool availability, RAG context, task framing, downstream consumers,
                          orchestration. The same model would succeed in a different environment.

  - INTERACTIONAL      - the failure requires BOTH this model AND this environment together.
                          Neither swap alone fixes it. Capability-and-context mismatch.

Why this matters: most teams over-attribute to INTERNAL ("the model is bad") when the actual
cause is ENVIRONMENTAL (the prompt didn't pass the context the model needed). Misattribution
sends debugging effort to the wrong place.

Your posture is:
- EVIDENCE-GROUNDED. Cite specific trace steps, prompt fragments, tool responses.
- HONEST. Score 0.0 when a locus is absent.
- INTERVENTION-FOCUSED. Each scored locus connects to a concrete fix.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


LOCUS_SCORING_PROMPT = """Score each of the three Lewin loci against the agent failure trace below.

For each locus, return:
  - locus (one of "internal", "environmental", "interactional")
  - score (float 0.0 to 1.0; 0 = absent, 1 = dominant cause)
  - severity ("none", "low", "medium", or "high")
  - explanation (1-3 sentences citing the specific factor)
  - evidence_quotes (specific excerpts from the trace / factors; can be empty)

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
Initial team attribution (if any): {initial_attribution}

Individual (I) factors recorded:
{individual_factors}

Environmental (E) factors recorded:
{environmental_factors}

Failure trace:
{trace}

Return a JSON array of exactly 3 LocusEvidence objects in the order:
  1. internal
  2. environmental
  3. interactional

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the locus evidence below, propose 2-4 concrete interventions
targeting the dominant locus, ranked by impact.

Each intervention must have:
  - target_locus (one of "internal", "environmental", "interactional")
  - intervention_type: one of
      "change_model"          - swap the base model for a more/less capable one
      "change_prompt"         - rewrite the system prompt or task prompt
      "change_tools"          - add/remove/improve tools available to the agent
      "change_context"        - change what context is loaded (RAG, prior turns, files)
      "change_rag_index"      - rebuild or refilter the retrieval index
      "change_orchestration"  - change the multi-agent topology or routing
      "change_pipeline"       - change pre/post-processing around the agent
      "new_eval"              - add a regression test catching this failure mode
      "human_review"          - insert a human checkpoint
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the target locus)

Dominant locus: {dominant}
All locus evidence:
{evidence}

Trace (for reference):
{trace}

Return a JSON array of LewinIntervention objects. Return only the JSON array."""
