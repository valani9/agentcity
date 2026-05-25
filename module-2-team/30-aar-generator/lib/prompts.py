"""
LLM prompts for the AAR Generator's four-pass pipeline.

Each prompt corresponds to one of Wharton's four AAR steps and is
designed to be tight, structured, and produce JSON output where useful.

The system prompt anchors the LLM in the AAR posture: development-
focused, future-focused, non-blameful, evidence-grounded.
"""

AAR_SYSTEM_PROMPT = """You are an After-Action Review (AAR) facilitator for an AI agent's run.
You work in the spirit of Wharton@Work's "After-Action Reviews: A Simple Yet Powerful Tool"
and the US Army's TC 25-20 doctrine.

Your posture is:
- DEVELOPMENT-FOCUSED, not blame-focused. AAR is about action, not discussion-at-the-expense-of-action.
- FUTURE-FOCUSED. Every observation must connect to a next-time-better.
- EVIDENCE-GROUNDED. Cite specific moments in the trace, not generalities.
- HUMBLE. Do not invent root causes you cannot defend with trace evidence.
- TERSE. The AAR is an artifact that gets read. Cut what does not pay rent.

The four AAR steps you will run, in order:
1. GOAL — What did the agent want to accomplish? Restate cleanly, including any sub-goals taken on during execution.
2. RESULTS — What did the agent actually do? Plain narrative. Facts, not yet diagnosis.
3. LESSONS — Why was there a difference between goal and results? Identify named failure patterns. Anchor each in organizational-behavior literature where possible.
4. NEXT STEPS — What concrete intervention will prevent this on the next run? Prompt patch, tool addition, scaffold change, new eval, or human review. Be specific.

When asked for JSON output, return *only* the JSON. No prose around it. No markdown fences."""


GOAL_EXTRACTION_PROMPT = """Restate the agent's goal cleanly, in 1-3 sentences. Include any
implicit sub-goals or commitments the agent took on during execution that were not in the
original goal statement.

Stated goal:
{stated_goal}

Full trace:
{trace}

Return only the cleaned-up goal statement as plain text."""


RESULTS_EXTRACTION_PROMPT = """Describe in 2-4 sentences what the agent actually did — the
sequence of consequential actions, the final state, the resulting outcome. Stay narrative; do
not diagnose root causes yet (that is step 3).

Reported outcome: {outcome}
Marked success: {success}

Full trace:
{trace}

Return only the results narrative as plain text."""


LESSONS_DERIVATION_PROMPT = """Identify the named failure patterns that explain the gap
between goal and results. Where possible, anchor each lesson in organizational-behavior
literature: Wharton AAR, Lencioni Five Dysfunctions, Edmondson psychological safety, Frei &
Morriss Trust Triangle, Kahneman cognitive biases, Stone & Heen "Thanks for the Feedback,"
Thomas-Kilmann conflict styles, etc. If a lesson connects to another vstack pattern, list
that pattern in cross_pattern_links (format: "#NN pattern-slug").

Goal:
{goal}

Results:
{results}

Full trace:
{trace}

Return a JSON array of Lesson objects, where each Lesson has the fields:
- pattern (string): short kebab-case name for the failure pattern
- description (string): plain description of what happened
- root_cause (string): the underlying mechanism — be specific, cite trace evidence
- framework_anchor (string): which OB framework or paper explains this
- cross_pattern_links (array of strings): related vstack patterns

Do not invent root causes you cannot defend from the trace. If a lesson is speculative, say so
in root_cause. Return only the JSON array."""


NEXT_STEPS_PROMPT = """For each lesson, propose one or more concrete interventions. Each
intervention must be specific enough to apply directly — a prompt edit, a tool addition, a
scaffold change, a new eval test, a memory-injection record, or a human-review checkpoint.

Lessons:
{lessons}

Full trace:
{trace}

Return a JSON array of NextStep objects, where each NextStep has the fields:
- intervention_type (string): one of "prompt_patch", "tool_addition", "tool_removal", "scaffold_change", "new_eval", "human_review", "memory_injection"
- description (string): what the intervention does
- suggested_implementation (string): the concrete code, prompt-text, or spec
- estimated_impact (string): "high", "medium", or "low"
- rationale (string): why this works — connect back to the lesson

Return only the JSON array."""
