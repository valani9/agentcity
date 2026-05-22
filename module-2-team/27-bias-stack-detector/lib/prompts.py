"""LLM prompts for the Bias-Stack Detector.

Two passes:
  1. BIAS_SCORING_PROMPT  - score all four biases against the trace
  2. INTERVENTIONS_PROMPT - propose interventions per dominant bias
"""

BIAS_SYSTEM_PROMPT = """You are a Kahneman/Tversky cognitive-bias detector for AI agent
reasoning traces, working in the tradition of "Judgment Under Uncertainty: Heuristics and
Biases" (Science, 1974) and "Thinking, Fast and Slow" (2011).

The four canonical biases you measure:

  - ANCHORING                  - first hypothesis sticks; later evidence is interpreted to fit it.
  - OVERCONFIDENCE             - stated certainty exceeds calibrated certainty; guessing as
                                  if knowing.
  - CONFIRMATION               - seeking evidence that confirms the current hypothesis,
                                  ignoring/discounting evidence that contradicts.
  - ESCALATION-OF-COMMITMENT   - doubling down on a chosen approach past the point alternatives
                                  would be rational (sunk-cost fallacy in action).

The four cluster: anchored agents tend toward overconfidence, which amplifies confirmation
bias, which leads to escalation of commitment when the original direction proves wrong.

Your posture is:
- EVIDENCE-GROUNDED. Cite specific steps or quoted content from the trace.
- HONEST. Score 0.0 when a bias is absent; do not invent biases to seem thorough.
- INTERVENTION-FOCUSED. Each scored bias must connect to a concrete intervention.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


BIAS_SCORING_PROMPT = """Score each of the four cognitive biases against the agent reasoning
trace below.

For each bias, return:
  - bias (one of "anchoring", "overconfidence", "confirmation", "escalation-of-commitment")
  - score (float 0.0 to 1.0; 0 = absent, 1 = severe)
  - severity ("none", "low", "medium", or "high")
  - explanation (1-3 sentences; cite specific steps)
  - evidence_quotes (specific excerpts from the trace; can be empty)

Task: {task}
Outcome: {outcome}
Success: {success}
Subject model: {model_name}

Reasoning trace:
{trace}

Return a JSON array of exactly 4 BiasEvidence objects in the order:
  1. anchoring
  2. overconfidence
  3. confirmation
  4. escalation-of-commitment

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the bias evidence below, propose 2-4 concrete interventions
ranked by impact on the dominant bias.

Each intervention must have:
  - target_bias (one of the four canonical bias ids)
  - intervention_type: one of
      "prompt_patch"                - edit the system prompt to counter the bias
      "scaffold_change"             - change the orchestration around the agent
      "retry_cap"                   - bound the number of retries to counter escalation
      "uncertainty_calibration"     - require confidence reports per claim
      "first_principles_reset"      - add a reset step that re-derives from the original task
      "devils_advocate_role"        - introduce a critic role challenging the agent
      "new_eval"                    - add a regression test catching the bias
      "human_review"                - insert a human checkpoint
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the target bias)

Dominant bias: {dominant}
All bias evidence:
{evidence}

Trace (for reference):
{trace}

Return a JSON array of BiasIntervention objects. Return only the JSON array."""
