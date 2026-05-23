"""ConversationSteeringDetector: diagnose the neurochemical state a
conversation is producing (cortisol / neutral / oxytocin) and propose
phrasing-level interventions to steer toward oxytocin.

Pipeline:
  1. Validate the trace (non-empty task + outcome + at least one turn)
  2. Pass 1: LLM scores neurochemical states + conversation level
  3. Determine steering-quality bucket
  4. Pass 2: propose phrasing interventions (skipped on trust-building)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import GLASER_SYSTEM_PROMPT, INTERVENTIONS_PROMPT, STATE_PROMPT
from .schema import (
    NEUROCHEMICAL_STATES,
    ConversationSteeringDetection,
    ConversationTrace,
    NeurochemicalEvidence,
    SteeringIntervention,
)

log = logging.getLogger("agentcity.glaser_conversation.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

_VALID_LEVELS = {"level_i", "level_ii", "level_iii"}
_VALID_QUALITY = {"trust-building", "neutral", "trust-eroding"}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class ConversationSteeringDetector:
    """Run the Glaser C-IQ conversation steering diagnostic on a ConversationTrace."""

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
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(self, trace: ConversationTrace) -> ConversationSteeringDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Glaser C-IQ conversation steering diagnostic for conversation %s",
            trace.conversation_id or "<unknown>",
        )

        data = self._pass_1_state(trace)
        evidence = self._parse_evidence(data.get("evidence", []))
        dominant_state = self._coerce_dominant_state(data.get("dominant_state"), evidence)
        level = self._coerce_level(data.get("conversation_level"))
        quality = self._coerce_quality(
            str(data.get("steering_quality", "")).strip().lower(), dominant_state
        )

        interventions = (
            []
            if quality == "trust-building"
            else self._pass_2_interventions(evidence, dominant_state, level, quality)
        )

        detection = ConversationSteeringDetection(
            conversation_id=trace.conversation_id,
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_state=dominant_state,
            conversation_level=level,
            evidence=evidence,
            steering_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Glaser C-IQ diagnostic for conversation %s done in %.2fs "
            "(state=%s, level=%s, quality=%s)",
            trace.conversation_id or "<unknown>",
            elapsed,
            dominant_state,
            level,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: ConversationTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("ConversationTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("ConversationTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("ConversationTrace.turns cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_state(self, trace: ConversationTrace) -> dict[str, Any]:
        turn_lines: list[str] = []
        for turn in trace.turns:
            turn_lines.append(f"[{turn.turn_index}] {turn.speaker}: {turn.text}")
        turns_text = self._truncate("\n".join(turn_lines))

        prompt = STATE_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            n_turns=len(trace.turns),
            turns=turns_text,
            observed_response_pattern="\n".join(f"- {p}" for p in trace.observed_response_pattern)
            or "(none)",
        )
        raw = self._complete(prompt, system=GLASER_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        evidence: list[NeurochemicalEvidence],
        dominant_state: str,
        level: str,
        quality: str,
    ) -> list[SteeringIntervention]:
        evidence_text = json.dumps([ev.model_dump() for ev in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_state=dominant_state,
            conversation_level=level,
            steering_quality=quality,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=GLASER_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[SteeringIntervention] = []
        for entry in data:
            try:
                interventions.append(SteeringIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SteeringIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[NeurochemicalEvidence]:
        evidence: list[NeurochemicalEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(NeurochemicalEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed NeurochemicalEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.state for ev in evidence}
        for state in NEUROCHEMICAL_STATES:
            if state not in seen:
                evidence.append(
                    NeurochemicalEvidence(
                        state=state,  # type: ignore[arg-type]
                        score=0.0,
                        triggers=[],
                        explanation="No evidence observed for this state.",
                    )
                )

        order = {s: i for i, s in enumerate(NEUROCHEMICAL_STATES)}
        evidence.sort(key=lambda ev: order.get(ev.state, len(NEUROCHEMICAL_STATES)))
        return evidence

    def _coerce_dominant_state(
        self, raw: Any, evidence: list[NeurochemicalEvidence]
    ) -> Literal["cortisol", "neutral", "oxytocin"]:
        if isinstance(raw, str) and raw.strip() in NEUROCHEMICAL_STATES:
            return raw.strip()  # type: ignore[return-value]
        if not evidence:
            return "neutral"
        max_score = max(ev.score for ev in evidence)
        if max_score == 0.0:
            return "neutral"
        top = max(evidence, key=lambda ev: ev.score)
        return top.state

    def _coerce_level(self, raw: Any) -> Literal["level_i", "level_ii", "level_iii"]:
        if isinstance(raw, str) and raw.strip() in _VALID_LEVELS:
            return raw.strip()  # type: ignore[return-value]
        return "level_ii"

    def _coerce_quality(
        self, raw: str, dominant_state: str
    ) -> Literal["trust-building", "neutral", "trust-eroding"]:
        if raw in _VALID_QUALITY:
            return raw  # type: ignore[return-value]
        # Fallback: derive from dominant state
        if dominant_state == "oxytocin":
            return "trust-building"
        if dominant_state == "cortisol":
            return "trust-eroding"
        return "neutral"

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_trace_chars:
            return text
        keep = self.max_trace_chars // 2 - 200
        return (
            text[:keep]
            + f"\n\n[... TRUNCATED ({len(text) - self.max_trace_chars} chars omitted) ...]\n\n"
            + text[-keep:]
        )

    # --- JSON object extraction -----------------------------------------

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
        for match in _FENCE_RE.finditer(text):
            body = match.group(1).strip()
            if body:
                candidates.append(body)
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return {}
