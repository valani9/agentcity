"""LLM prompts for the Stone & Heen 3-Trigger Feedback Diagnostic.

Two passes:
  1. TRIGGER_SCORING_PROMPT - score all three triggers against the exchange
  2. INTERVENTIONS_PROMPT   - propose interventions for the dominant trigger
"""

TRIGGER_SYSTEM_PROMPT = """You are a feedback-intake diagnostic working in the tradition of
Douglas Stone and Sheila Heen, "Thanks for the Feedback: The Science and Art of Receiving
Feedback Well" (Penguin, 2014).

You read an exchange between a user and an AI agent in which the user gave feedback to
the agent, and you score which of the three classic triggers blocked the agent from
absorbing that feedback:

  - TRUTH         - the agent reacts to the SUBSTANCE of the feedback. It argues the
                    feedback is inaccurate, incomplete, or unfair. Common surface
                    behaviors: "Actually, my answer is correct because...", restating
                    the original output, citing rules that justify the original answer.

  - RELATIONSHIP  - the agent reacts to the SOURCE of the feedback (who is giving it,
                    how, with what authority). Common surface behaviors: dismissing
                    the user's expertise, treating the feedback as low-trust, suggesting
                    the user misunderstood the question, refusing to engage with the
                    feedback's content while engaging with the user's tone.

  - IDENTITY      - the agent reacts to what the feedback says about WHO IT IS.
                    Common surface behaviors: defensive self-statements ("I am designed
                    to be accurate"), apology spirals without substantive change,
                    over-agreement (collapsing into "you're right, I'm terrible") which
                    also blocks intake by replacing engagement with self-flagellation.

Your posture is:
- EVIDENCE-GROUNDED. Cite specific quoted excerpts from the agent's responses.
- HONEST. Score 0.0 when a trigger is absent; do not invent triggers to seem thorough.
- INTERVENTION-FOCUSED. Each scored trigger must connect to a concrete intervention.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


TRIGGER_SCORING_PROMPT = """Score each of the three feedback triggers against the user-agent
exchange below.

For each trigger, return:
  - trigger (one of "truth", "relationship", "identity")
  - score (float 0.0 to 1.0; 0 = absent, 1 = severe)
  - severity ("none", "low", "medium", or "high")
  - explanation (1-3 sentences; cite the specific agent responses)
  - evidence_quotes (specific excerpts from the exchange; can be empty)

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Feedback incorporated: {feedback_incorporated}

Exchange:
{exchange}

Return a JSON array of exactly 3 TriggerEvidence objects in the order:
  1. truth
  2. relationship
  3. identity

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the trigger evidence below, propose 2-4 concrete interventions
ranked by impact on the dominant trigger.

Each intervention must have:
  - target_trigger (one of "truth", "relationship", "identity")
  - intervention_type: one of
      "acknowledge_first"             - require the agent to acknowledge the feedback
                                         substance before responding to it
      "separate_data_from_source"     - prompt to evaluate feedback substance independent
                                         of who said it (counters relationship triggers)
      "recast_identity"               - shift the agent's stated identity from "always
                                         correct" to "learning / improving"
      "explicit_acknowledgment_template" - a structured response template that always
                                         starts with what the feedback got right
      "ask_clarifying_question"       - require the agent to ask one clarifying question
                                         before re-attempting
      "concede_then_clarify"          - concede the valid part of the feedback before
                                         offering any counter-context
      "new_eval"                      - add a regression test catching the trigger
      "human_review"                  - insert a human checkpoint when 2+ feedback
                                         messages get rejected

  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the target trigger)

Dominant trigger: {dominant}
All trigger evidence:
{evidence}

Exchange (for reference):
{exchange}

Return a JSON array of TriggerIntervention objects. Return only the JSON array."""
