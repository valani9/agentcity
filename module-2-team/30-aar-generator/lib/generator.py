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
import logging
import time
from typing import Any, Protocol

from ._json_parsing import extract_json_array
from ._retry import with_retry
from .prompts import (
    GOAL_EXTRACTION_PROMPT,
    LESSONS_DERIVATION_PROMPT,
    NEXT_STEPS_PROMPT,
    RESULTS_EXTRACTION_PROMPT,
    AAR_SYSTEM_PROMPT,
)
from .schema import AAR, AgentTrace, Lesson, NextStep

log = logging.getLogger("agentcity.aar.generator")


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

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars

        # Wrap the LLM call with retry logic. This is the single chokepoint
        # for all LLM I/O in the generator, so applying retry here covers
        # every step. Users can still pass an already-wrapped client (their
        # own retry policy will apply on top).
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def generate(self, trace: AgentTrace) -> AAR:
        """Run all four AAR steps in order and assemble the final document.

        Raises:
            ValueError: if the trace fails minimal sanity checks
                (e.g. empty goal). LLM-side errors are retried internally
                and surface only if all retries are exhausted.
        """
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Generating AAR for trace %s (steps=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.steps),
            trace.success,
        )

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

        elapsed = time.monotonic() - started
        log.info(
            "AAR generated for trace %s in %.2fs (lessons=%d, next_steps=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            len(lessons),
            len(next_steps),
        )

        return aar

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentTrace) -> None:
        """Apply minimal sanity checks before invoking the LLM."""
        if not trace.goal or not trace.goal.strip():
            raise ValueError(
                "AgentTrace.goal cannot be empty. The AAR's first step "
                "asks 'what did we want to accomplish?' and that needs "
                "an answer in the input."
            )
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError(
                "AgentTrace.outcome cannot be empty. The AAR's second "
                "step needs the actual outcome to compare against the goal."
            )

    # --- Step implementations ------------------------------------------

    def _step_1_goal(self, trace: AgentTrace, trace_text: str) -> str:
        """Step 1: What did we want to accomplish?

        The agent's *stated* goal is on the trace, but the AAR step also
        captures any implicit sub-goals or commitments the agent took on
        during execution.
        """
        prompt = GOAL_EXTRACTION_PROMPT.format(stated_goal=trace.goal, trace=trace_text)
        return self._complete(prompt, system=AAR_SYSTEM_PROMPT).strip()

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
        return self._complete(prompt, system=AAR_SYSTEM_PROMPT).strip()

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

        Skips Lessons that cannot be validated as the schema's `Lesson`
        type. We log at warning and continue; a partial AAR is more useful
        than no AAR.
        """
        prompt = LESSONS_DERIVATION_PROMPT.format(goal=goal, results=results, trace=trace_text)
        raw = self._complete(prompt, system=AAR_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)
        lessons: list[Lesson] = []
        for entry in data:
            try:
                lessons.append(Lesson(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed Lesson from LLM output (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return lessons

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

        Skips NextSteps that cannot be validated; see the equivalent
        behavior in `_step_3_lessons` for the rationale.
        """
        lessons_text = json.dumps([lesson.model_dump() for lesson in lessons], indent=2)
        prompt = NEXT_STEPS_PROMPT.format(lessons=lessons_text, trace=trace_text)
        raw = self._complete(prompt, system=AAR_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)
        steps: list[NextStep] = []
        for entry in data:
            try:
                steps.append(NextStep(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed NextStep from LLM output (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return steps

    # --- Convenience-artifact derivation -------------------------------

    def _derive_prompt_patch(self, lessons: list[Lesson], next_steps: list[NextStep]) -> str | None:
        """Pull out the prompt-patch interventions and concatenate them.

        If no `prompt_patch` interventions are proposed, returns None.
        """
        patches = [
            s.suggested_implementation for s in next_steps if s.intervention_type == "prompt_patch"
        ]
        return "\n\n".join(patches) if patches else None

    def _derive_eval_test(self, lessons: list[Lesson], trace: AgentTrace) -> str | None:
        """Pull out new-eval-test interventions and return the first as code.

        Future iterations will produce a full pytest-compatible file with
        all proposed evals; for now, return the first proposed test.
        """
        # Placeholder: a proper implementation generates pytest code from
        # the lesson + trace via a separate LLM call.
        return None

    def _derive_lesson_record(
        self, lessons: list[Lesson], trace: AgentTrace
    ) -> dict[str, Any] | None:
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
            "lessons": [lesson.model_dump() for lesson in lessons],
            "original_goal": trace.goal,
        }

    # --- Helpers --------------------------------------------------------

    def _serialize_trace(self, trace: AgentTrace) -> str:
        """Render an AgentTrace as text suitable for inclusion in an LLM prompt.

        If the serialized trace exceeds `max_trace_chars`, it is truncated
        from the middle (keeping the first 40% and last 40% of steps) with
        a clear marker, since the beginning and end of a trace are usually
        the most informative parts of a failure.
        """
        header = [f"Goal: {trace.goal}", f"Outcome: {trace.outcome}", ""]
        step_lines = [
            f"[{step.timestamp.isoformat()}] ({step.type}) {step.content}" for step in trace.steps
        ]
        full = "\n".join(header + step_lines)

        if len(full) <= self.max_trace_chars:
            return full

        log.warning(
            "Trace exceeds max_trace_chars (%d > %d); truncating from the middle",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        head = full[:keep]
        tail = full[-keep:]
        marker = (
            f"\n\n[... TRACE TRUNCATED for length "
            f"({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
        )
        return head + marker + tail
