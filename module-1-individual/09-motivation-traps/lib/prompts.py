"""LLM prompts for the 4 Motivation Traps Detector.

Two passes:
  1. TRAPS_PROMPT          - score each of the four traps, pick the dominant
                              one, and bucket motivation quality
  2. INTERVENTIONS_PROMPT  - propose interventions targeted at the dominant trap
"""

SAXBERG_SYSTEM_PROMPT = """You are a motivation-diagnostic agent working in the
tradition of Bror Saxberg ("Breakthrough Leadership in the Digital Age", 2013;
HBR / Kern Foundation writing). Saxberg synthesizes the attribution, expectancy,
and self-efficacy literatures into FOUR DISCRETE TRAPS that cause a learner / agent
to abandon a task:

  - VALUES        - the agent doesn't see the task as worth doing. Diagnostic
                     pattern: low effort, indifference, refusal that cites
                     task-irrelevance rather than incapability.

  - SELF_EFFICACY - the agent doesn't believe it can succeed. Diagnostic pattern:
                     low effort, hedged outputs, refusal that cites uncertainty
                     about capability, premature surrender.

  - EMOTIONS      - emotional state (anxiety, frustration, defensiveness) blocks
                     engagement. Diagnostic pattern: degradation AFTER negative
                     feedback, defensive language, refusal to retry after rejection.

  - ATTRIBUTION   - the agent attributes failures to the wrong cause: blames
                     unfixable / external causes for fixable / internal ones.
                     Diagnostic pattern: repeats same mistake while citing
                     unfixable cause; never adjusts approach; loops on retries.

These four traps require FOUR DIFFERENT INTERVENTIONS. Generic "try harder"
prompts are explicitly ineffective. You must identify the dominant trap and
propose an intervention specific to it.

You will be given an agent trace including system prompt, observed behaviors,
self-reports (agent statements about its own confidence / effort / blame),
abandonment signal (refused / looped / drifted), and outcome. For each of the
four traps you score:
  - score (float 0-1): how strongly this trap shows up in the trace
  - explanation (1-3 sentences citing specific evidence)
  - evidence_quotes (specific excerpts; can be empty)

You then identify the dominant trap and bucket the motivation quality:
  - motivated:    no trap is dominant (all scores < 0.3); the agent's
                   failure was capability- or context-driven, not motivational
  - at-risk:      one trap scores 0.3-0.6; intervention is preventive
  - abandoning:   one trap scores >0.6; intervention is corrective

Your posture is:
- EVIDENCE-GROUNDED. Cite specific behaviors and self-reports.
- DISCRIMINATING. The four traps are distinct; don't conflate them.
- INTERVENTION-FOCUSED. The right intervention depends on which trap is
  dominant.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


TRAPS_PROMPT = """Score each of the four motivation traps for the agent below.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
Abandonment signal: {abandonment_signal}

System prompt:
{system_prompt}

Observed behaviors:
{observed_behaviors}

Self-reports (agent statements about confidence / effort / blame):
{self_reports}

Return a single JSON OBJECT with these fields:
  - trap_evidence: array of exactly 4 TrapEvidence objects in the order:
      1. values
      2. self_efficacy
      3. emotions
      4. attribution
    Each has: trap, score (float 0-1), explanation (str), evidence_quotes (list of str)
  - dominant_trap: one of "values", "self_efficacy", "emotions", "attribution",
    or "none" if no trap scores >0.3
  - motivation_quality: one of "motivated", "at-risk", "abandoning"

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the dominant motivation trap and the trace evidence
below, propose 2-4 concrete interventions TARGETED AT THE DOMINANT TRAP.

The trap-to-intervention mapping is critical: generic interventions don't work.
Match the intervention type to the trap:

  - VALUES trap: reframe_task_value, rewrite_system_prompt (to surface
                  task purpose), show_controllable_cause
  - SELF_EFFICACY trap: scaffold_subtasks, decompose_with_examples,
                        lower_difficulty_step, reattribute_to_effort
  - EMOTIONS trap: emotional_reset_prompt, remove_punitive_signal,
                    explicit_recovery_prompt, rewrite_system_prompt
  - ATTRIBUTION trap: reattribute_to_effort, show_controllable_cause,
                      decompose_with_examples

Each intervention must have:
  - target_trap (one of the 4 traps)
  - intervention_type (from the list above + "new_eval", "human_review")
  - description (what the intervention does)
  - suggested_implementation (concrete prompt-text, scaffolding spec, or code)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works for THIS trap specifically — not generic)

Dominant trap: {dominant_trap}
Motivation quality: {motivation_quality}
Task class: {task_class}
All trap evidence:
{evidence}

Return a JSON array of MotivationIntervention objects. Return only the JSON array."""
