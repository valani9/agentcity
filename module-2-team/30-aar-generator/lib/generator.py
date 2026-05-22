"""
AAR Generator: produces a Wharton 4-step After-Action Review from an
agent run trace.

This implementation is LLM-backed because the lessons step requires
causal reasoning about *why* the agent's results diverged from its goal,
which is exactly the kind of work an LLM is good at when given the full
trace as context.

The generator is LLM-client agnostic. Pass in any client that exposes a
synchronous `complete(prompt: str, system: str | None = None) -> str`
method; concrete adapters for Anthropic, OpenAI, and a local-Ollama
client are in `lib/clients.py`.
"""

from __future__ import annotations

import json
from typing import Protocol

from .prompts import (
    GOAL_EXTRACTION_PROMPT,
    LESSONS_DERIVATION_PROMPT,
    NEXT_STEPS_PROMPT,
    RESULTS_EXTRACTION_PROMPT,
    AAR_SYSTEM_PROMPT,
)
from .schema import AAR, AgentTrace, Lesson, NextStep


class LLMClient(Protocol):
    """Minimal interface that any LLM client must support."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AARGenerator:
    """Generate a Wharton 4-step After-Action Review from an agent trace.

    The generator runs four passes — one per step of the AAR. Each pass is
    LLM-driven and produces a structured output. Lessons cross-link to
    other AgentCity patterns (e.g., a "stuck-in-loop" lesson links to
    pattern #27 Bias-Stack Detector / escalation-of-commitment).
    """

    def __init__(self, llm_client: LLMClient, model: str = "claude-sonnet-4-6") -> None:
        self.llm = llm_client
        self.model = model

    def generate(self, trace: AgentTrace) -> AAR:
        """Run all four AAR steps in order and assemble the final document."""
        trace_text = self._serialize_trace(trace)

        goal = self._step_1_goal(trace, trace_text)
        results = self._step_2_results(trace, trace_text)
        lessons = self._step_3_lessons(trace, trace_text, goal, results)
        next_steps = self._step_4_next_steps(trace, trace_text, lessons)

        aar = AAR(
            goal=goal,
            results=results,
            lessons=lessons,
            next_steps=next_steps,
            source_trace_id=trace.agent_id,
            generator_model=self.model,
            success=trace.success,
        )

        # Derive convenience artifacts
        aar.suggested_prompt_patch = self._derive_prompt_patch(lessons, next_steps)
        aar.suggested_eval_test = self._derive_eval_test(lessons, trace)
        aar.lesson_record_for_memory = self._derive_lesson_record(lessons, trace)

        return aar

    # --- Step implementations ------------------------------------------

    def _step_1_goal(self, trace: AgentTrace, trace_text: str) -> str:
        """Step 1: What did we want to accomplish?

        The agent's *stated* goal is on the trace, but the AAR step also
        captures any implicit sub-goals or commitments the agent took on
        during execution.
        """
        prompt = GOAL_EXTRACTION_PROMPT.format(
            stated_goal=trace.goal, trace=trace_text
        )
        return self.llm.complete(prompt, system=AAR_SYSTEM_PROMPT).strip()

    def _step_2_results(self, trace: AgentTrace, trace_text: str) -> str:
        """Step 2: What did we actually do?

        Plain narrative of what happened. Not blame-assignment. Not yet
        lesson derivation. Just facts.
        """
        prompt = RESULTS_EXTRACTION_PROMPT.format(
            outcome=trace.outcome,
            success=trace.success,
            trace=trace_text,
        )
        return self.llm.complete(prompt, system=AAR_SYSTEM_PROMPT).strip()

    def _step_3_lessons(
        self,
        trace: AgentTrace,
        trace_text: str,
        goal: str,
        results: str,
    ) -> list[Lesson]:
        """Step 3: Why was there a difference?

        This is the heart of the AAR. The LLM is asked to identify named
        failure patterns in the gap between goal and results, anchor each
        in OB literature where possible (via the AgentCity pattern
        library), and propose a root cause for each.
        """
        prompt = LESSONS_DERIVATION_PROMPT.format(
            goal=goal,
            results=results,
            trace=trace_text,
        )
        raw = self.llm.complete(prompt, system=AAR_SYSTEM_PROMPT).strip()
        # Expected output: a JSON array of Lesson objects.
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = self._extract_json_array(raw)
        return [Lesson(**lesson) for lesson in data]

    def _step_4_next_steps(
        self,
        trace: AgentTrace,
        trace_text: str,
        lessons: list[Lesson],
    ) -> list[NextStep]:
        """Step 4: What will we do differently next time?

        For each lesson, propose one or more concrete interventions. The
        intervention is concrete enough to implement directly: a prompt
        edit, a new tool, a new eval test, a scaffold change.
        """
        lessons_text = json.dumps([l.model_dump() for l in lessons], indent=2)
        prompt = NEXT_STEPS_PROMPT.format(lessons=lessons_text, trace=trace_text)
        raw = self.llm.complete(prompt, system=AAR_SYSTEM_PROMPT).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = self._extract_json_array(raw)
        return [NextStep(**step) for step in data]

    # --- Convenience-artifact derivation -------------------------------

    def _derive_prompt_patch(
        self, lessons: list[Lesson], next_steps: list[NextStep]
    ) -> str | None:
        """Pull out the prompt-patch interventions and concatenate them.

        If no `prompt_patch` interventions are proposed, returns None.
        """
        patches = [
            s.suggested_implementation
            for s in next_steps
            if s.intervention_type == "prompt_patch"
        ]
        return "\n\n".join(patches) if patches else None

    def _derive_eval_test(
        self, lessons: list[Lesson], trace: AgentTrace
    ) -> str | None:
        """Pull out new-eval-test interventions and return the first as code.

        Future iterations will produce a full pytest-compatible file with
        all proposed evals; for now, return the first proposed test.
        """
        # Placeholder: a proper implementation generates pytest code from
        # the lesson + trace via a separate LLM call.
        return None

    def _derive_lesson_record(
        self, lessons: list[Lesson], trace: AgentTrace
    ) -> dict | None:
        """Build a structured lesson record suitable for injection into agent memory.

        The record format is intentionally minimal — agent memory systems
        differ, so we surface a generic dict that any system can adapt.
        """
        if not lessons:
            return None
        return {
            "type": "aar_lesson",
            "agent_id": trace.agent_id,
            "agent_framework": trace.agent_framework,
            "lessons": [l.model_dump() for l in lessons],
            "original_goal": trace.goal,
        }

    # --- Helpers --------------------------------------------------------

    def _serialize_trace(self, trace: AgentTrace) -> str:
        """Render an AgentTrace as text suitable for inclusion in an LLM prompt."""
        out: list[str] = [f"Goal: {trace.goal}", f"Outcome: {trace.outcome}", ""]
        for step in trace.steps:
            out.append(f"[{step.timestamp.isoformat()}] ({step.type}) {step.content}")
        return "\n".join(out)

    @staticmethod
    def _extract_json_array(text: str) -> list[dict]:
        """Best-effort extraction of a JSON array from a markdown-fenced LLM response."""
        # Try fenced-code variant first
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return []
