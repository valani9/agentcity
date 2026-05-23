"""MotivationTrapsDetector: identify which of Saxberg's four motivation
traps is dominant in an AI agent's task-abandonment pattern.

Pipeline:
  1. Validate the trace (non-empty task + outcome + abandonment_signal)
  2. Pass 1: LLM scores all four traps + identifies dominant + buckets quality
  3. Pass 2: propose interventions (skipped if quality is "motivated")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, SAXBERG_SYSTEM_PROMPT, TRAPS_PROMPT
from .schema import (
    MOTIVATION_TRAPS,
    AgentMotivationTrace,
    MotivationDetection,
    MotivationIntervention,
    TrapEvidence,
)

log = logging.getLogger("agentcity.motivation_traps.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class MotivationTrapsDetector:
    """Run the 4 Motivation Traps diagnostic on an AgentMotivationTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(self, trace: AgentMotivationTrace) -> MotivationDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running 4 Motivation Traps diagnostic for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_traps(trace)
        evidence = self._parse_evidence(data.get("trap_evidence", []))
        dominant = self._coerce_dominant(data.get("dominant_trap"), evidence)
        quality = self._motivation_quality(
            str(data.get("motivation_quality", "")).strip().lower(), evidence, dominant
        )

        interventions = (
            []
            if quality == "motivated"
            else self._pass_2_interventions(evidence, dominant, quality, trace.task_class)
        )

        detection = MotivationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            trap_evidence=evidence,
            dominant_trap=dominant,
            motivation_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "4 Motivation Traps diagnostic for agent %s done in %.2fs (dominant=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentMotivationTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentMotivationTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentMotivationTrace.outcome cannot be empty.")
        if not trace.abandonment_signal or not trace.abandonment_signal.strip():
            raise ValueError("AgentMotivationTrace.abandonment_signal cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_traps(self, trace: AgentMotivationTrace) -> dict[str, Any]:
        prompt = TRAPS_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            abandonment_signal=trace.abandonment_signal,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
            self_reports="\n".join(f"- {s}" for s in trace.self_reports) or "(none)",
        )
        raw = self._complete(prompt, system=SAXBERG_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        evidence: list[TrapEvidence],
        dominant_trap: str,
        motivation_quality: str,
        task_class: str,
    ) -> list[MotivationIntervention]:
        evidence_text = json.dumps([ev.model_dump() for ev in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_trap=dominant_trap,
            motivation_quality=motivation_quality,
            task_class=task_class,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=SAXBERG_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[MotivationIntervention] = []
        for entry in data:
            try:
                interventions.append(MotivationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed MotivationIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[TrapEvidence]:
        evidence: list[TrapEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(TrapEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TrapEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.trap for ev in evidence}
        for trap in MOTIVATION_TRAPS:
            if trap not in seen:
                evidence.append(
                    TrapEvidence(
                        trap=trap,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed for this trap.",
                        evidence_quotes=[],
                    )
                )

        order = {t: i for i, t in enumerate(MOTIVATION_TRAPS)}
        evidence.sort(key=lambda ev: order.get(ev.trap, len(MOTIVATION_TRAPS)))
        return evidence

    def _coerce_dominant(
        self, raw: Any, evidence: list[TrapEvidence]
    ) -> Literal["values", "self_efficacy", "emotions", "attribution", "none"]:
        valid = set(MOTIVATION_TRAPS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: pick the highest-scoring trap if any > 0.3, else "none"
        if not evidence:
            return "none"
        top = max(evidence, key=lambda ev: ev.score)
        if top.score <= 0.3:
            return "none"
        return top.trap

    def _motivation_quality(
        self,
        raw: str,
        evidence: list[TrapEvidence],
        dominant: str,
    ) -> Literal["motivated", "at-risk", "abandoning"]:
        if raw in ("motivated", "at-risk", "abandoning"):
            return raw  # type: ignore[return-value]
        # Fallback: bucket by dominant trap score
        if dominant == "none" or not evidence:
            return "motivated"
        dom = next((ev for ev in evidence if ev.trap == dominant), None)
        if dom is None:
            return "at-risk"
        if dom.score > 0.6:
            return "abandoning"
        if dom.score >= 0.3:
            return "at-risk"
        return "motivated"

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
