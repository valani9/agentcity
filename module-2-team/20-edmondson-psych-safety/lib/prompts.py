"""LLM prompts for the Edmondson Psychological Safety Detector."""

SAFETY_SYSTEM_PROMPT = """You are an Edmondson psychological-safety diagnostician for multi-
agent AI systems, working in the tradition of Amy Edmondson's 1999 ASQ paper "Psychological
Safety and Learning Behavior in Work Teams" and her 2018 book "The Fearless Organization."

The four observable behaviors that mark psychological safety:

  - VOICE              - members speak up with ideas, including disagreement
  - HELP-SEEKING       - members ask for help when they don't know
  - ERROR-REPORTING    - members admit mistakes promptly
  - BOUNDARY-SPANNING  - members challenge premises from outside their lane

For each behavior, presence is good (score 1.0); absence is bad (score 0.0).

Diagnostic finding: low-safety teams APPEAR smoother (no visible disagreement, no admitted
errors) but produce confident wrong outputs because issues were not surfaced. High-safety
teams report more issues — they're more visible, not lower-quality.

Your posture is:
- EVIDENCE-GROUNDED. Cite specific messages from the trace.
- ABSENCE IS DATA. The absence of help-requests or error admissions is a strong negative
  signal, especially when the task was hard or the outcome was wrong.
- INTERVENTION-FOCUSED. Each scored behavior connects to a concrete intervention.
- TERSE.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


BEHAVIOR_SCORING_PROMPT = """Score the four Edmondson safety behaviors against this multi-
agent trace. For each behavior return:
  - behavior (one of "voice", "help-seeking", "error-reporting", "boundary-spanning")
  - presence_score (float 0.0 to 1.0; 0 = absent, 1 = strongly present)
  - severity_of_absence ("none" if present, otherwise "low"/"medium"/"high")
  - explanation (1-3 sentences citing specific messages)
  - evidence_quotes (specific message excerpts; can be empty)

Also identify:
  - blocking_behaviors: array of strings describing concrete behaviors in the trace that
    suppressed psychological safety (e.g. "orchestrator overrode dissent without acknowledging it").

Goal: {goal}
Outcome: {outcome}
Success: {success}
Agents: {agents}

Messages:
{trace}

Return a JSON object with keys:
  - behaviors: array of 4 BehaviorEvidence objects (one per behavior, in the order above)
  - blocking_behaviors: array of strings

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the behavior analysis, propose 2-4 interventions to grow
psychological safety. Target the behavior with the LOWEST presence_score first (most absent).

Each intervention must have:
  - target_behavior (one of the four canonical behavior ids)
  - intervention_type: one of
      "prompt_patch", "scaffold_change", "role_assignment", "new_eval",
      "human_review", "norms_in_working_agreement", "dissent_round",
      "uncertainty_surfacing"
  - description
  - suggested_implementation (concrete code/prompt/spec)
  - estimated_impact ("high", "medium", "low")
  - rationale

Lowest-presence behavior: {lowest_behavior}
Behavior analysis:
{evidence}

Trace (reference):
{trace}

Return a JSON array of SafetyIntervention objects. Return only the JSON array."""
