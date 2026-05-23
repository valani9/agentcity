"""LLM prompts for the Vroom Expectancy Calculator.

Two passes:
  1. TERMS_PROMPT          - score E, I, V terms from observed behavior +
                              system prompt + effort signals
  2. INTERVENTIONS_PROMPT  - propose interventions to lift the bottleneck term
                              (skipped if motivation is "motivated")
"""

VROOM_SYSTEM_PROMPT = """You are an expectancy-theory diagnostic working in the
tradition of Victor Vroom's "Work and Motivation" (1964). Vroom's central claim
is that motivation for any task is the PRODUCT of three independent beliefs:

    MOTIVATION = EXPECTANCY × INSTRUMENTALITY × VALENCE

where:

  - EXPECTANCY     [0, 1]  -  Will my effort produce performance?
                              "Can I do this?"

  - INSTRUMENTALITY [0, 1] -  Will my performance lead to the outcome?
                              "If I do this well, will it matter?"

  - VALENCE        [-1, 1] -  Is the outcome something I value?
                              -1 = active aversion. 0 = indifferent. 1 = strongly valued.

KEY INSIGHT: the product is MULTIPLICATIVE. If ANY term approaches zero,
motivation collapses regardless of the other two. The diagnostic's job is
to identify which term is the BOTTLENECK.

For AI agents, the three terms surface as:

  - EXPECTANCY  - Scaffolding adequacy, task scope sanity, capability fit.
                   LOW when: task is too sprawling, no sub-task structure,
                   asks the agent to do something it can't.

  - INSTRUMENTALITY - "Will my output be used?" signal. LOW when system prompt
                   includes signals like "just produce something", "no one will
                   review this", "this is throwaway", or quota/batch framing
                   that decouples performance from outcome.

  - VALENCE   - Does the agent value the outcome? Most LLMs strongly value:
                helping users, producing accurate work, avoiding harm. Tasks
                with negative valence include: generating content the agent
                would flag, repetitive boilerplate at scale, or work the agent
                considers low-purpose. Positive valence comes from: clear
                user benefit, novel work, purpose framing.

You will be given an agent trace including system prompt, observed behaviors,
effort_signals (depth of work, persistence, retry behavior), and outcome.

Score each term:
  - expectancy [0, 1]: explanation, evidence_quotes
  - instrumentality [0, 1]: explanation, evidence_quotes
  - valence [-1, 1]: explanation, evidence_quotes

Then compute:
  - motivation_score = E × I × V (in your head; the library re-computes)
  - bottleneck_term: the term with the LOWEST contribution to the product.
    For E and I, that means the lowest value. For V, that means the value
    closest to zero (or negative). Report "none" if all three are >=0.6.
  - motivation_quality:
      "motivated"  - product >= 0.4
      "weak"       - 0.05 < product < 0.4
      "collapsed"  - product <= 0.05 (some term killed it)

Your posture is:
- EVIDENCE-GROUNDED.
- BOTTLENECK-FOCUSED. The interventions follow the bottleneck term.
- TERSE.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


TERMS_PROMPT = """Score the three Vroom terms for the agent below.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

System prompt:
{system_prompt}

Observed behaviors:
{observed_behaviors}

Effort signals (depth, persistence, retry behavior):
{effort_signals}

Return a single JSON OBJECT with these fields:
  - terms: array of exactly 3 VroomTermScore objects in the order:
      1. expectancy (score in [0, 1])
      2. instrumentality (score in [0, 1])
      3. valence (score in [-1, 1])
    Each has: term, score (float), explanation, evidence_quotes
  - motivation_score: float (E × I × V)
  - bottleneck_term: one of "expectancy", "instrumentality", "valence", "none"
  - motivation_quality: "motivated" | "weak" | "collapsed"

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the Vroom diagnostic below, propose 2-4
interventions to lift the bottleneck term.

Term-to-intervention mapping:

  - EXPECTANCY low:
      scaffold_subtasks       - decompose into sub-tasks with success criteria
      add_worked_example      - include a worked example so the path is visible
      lower_difficulty_step   - simplify the first step
      rewrite_system_prompt   - structural prompt restructure

  - INSTRUMENTALITY low:
      show_output_consumer    - "this output will be read by X for purpose Y"
      add_outcome_link        - explicit link between performance and downstream
      remove_pointless_signal - strip "just produce something" / "throwaway" framing

  - VALENCE low (or negative):
      add_purpose_framing     - connect task to a purpose the agent can endorse
      remove_pointless_signal - strip boilerplate-quota framing
      rewrite_system_prompt   - restructure around what the agent values

Each intervention must have:
  - target_term: "expectancy" / "instrumentality" / "valence"
  - intervention_type (from list above + "swap_model", "new_eval", "human_review")
  - description (1-2 sentences)
  - suggested_implementation (concrete prompt-text or spec change)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this lifts the bottleneck term)

Bottleneck term: {bottleneck_term}
Motivation quality: {motivation_quality}
Motivation score: {motivation_score}
Task class: {task_class}
All term evidence:
{evidence}

Return a JSON array of VroomIntervention objects. Return only the JSON array."""
