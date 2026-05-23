"""StrengthsOveruseDetector: diagnose Adam Grant's strengths-as-weaknesses
pattern in an agent behavior trace. Identifies which of the seven canonical
strength-overuse failure modes is dominant.

Pipeline:
  1. Validate the trace (non-empty task, outcome, steps)
  2. Pass 1: LLM scores all 7 strengths' overuse + picks dominant + harm
  3. Determine overuse-quality bucket
  4. Pass 2: propose interventions targeting the dominant overuse (skipped on healthy)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import GRANT_SYSTEM_PROMPT, INTERVENTIONS_PROMPT, STRENGTH_SCORING_PROMPT
from .schema import (
    STRENGTHS,
    AgentBehaviorTrace,
    StrengthIntervention,
    StrengthOveruseDetection,
    StrengthOveruseEvidence,
)

log = logging.getLogger("agentcity.grant_strengths.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class StrengthsOveruseDetector:
    """Run the Strengths-as-Weaknesses diagnostic on an AgentBehaviorTrace."""

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

    def run(self, trace: AgentBehaviorTrace) -> StrengthOveruseDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Strengths-Overuse detection for agent %s (steps=%d)",
            trace.agent_id or "<unknown>",
            len(trace.steps),
        )

        data = self._pass_1_strengths(trace, trace_text)
        evidence = self._parse_evidence(data.get("strengths", []))
        scores = self._build_scores(evidence)
        dominant = self._coerce_dominant(data.get("dominant_overuse"), scores)
        harm = self._coerce_harm(data.get("harm_caused"))
        quality = self._overuse_quality(
            scores, str(data.get("overuse_quality", "")).strip().lower()
        )

        interventions = (
            []
            if quality == "healthy"
            else self._pass_2_interventions(evidence, dominant, harm, quality)
        )

        detection = StrengthOveruseDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_overuse=dominant,
            strength_scores=scores,
            strengths=evidence,
            harm_caused=harm,
            overuse_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Strengths-Overuse detection for agent %s done in %.2fs "
            "(dominant=%s, harm=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            harm,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentBehaviorTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentBehaviorTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentBehaviorTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("AgentBehaviorTrace.steps cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_strengths(self, trace: AgentBehaviorTrace, trace_text: str) -> dict[str, Any]:
        prompt = STRENGTH_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            harm_visible=trace.harm_visible,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=GRANT_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        evidence: list[StrengthOveruseEvidence],
        dominant: str,
        harm: str,
        quality: str,
    ) -> list[StrengthIntervention]:
        evidence_text = json.dumps([ev.model_dump() for ev in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_overuse=dominant,
            harm_caused=harm,
            overuse_quality=quality,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=GRANT_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[StrengthIntervention] = []
        for entry in data:
            try:
                interventions.append(StrengthIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StrengthIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[StrengthOveruseEvidence]:
        evidence: list[StrengthOveruseEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(StrengthOveruseEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StrengthOveruseEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.strength for ev in evidence}
        for strength in STRENGTHS:
            if strength not in seen:
                evidence.append(
                    StrengthOveruseEvidence(
                        strength=strength,  # type: ignore[arg-type]
                        overuse_score=0.0,
                        severity="none",
                        explanation="No evidence of overuse observed.",
                        evidence_quotes=[],
                    )
                )

        order = {strength: i for i, strength in enumerate(STRENGTHS)}
        evidence.sort(key=lambda ev: order.get(ev.strength, len(STRENGTHS)))
        return evidence

    def _build_scores(self, evidence: list[StrengthOveruseEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {strength: 0.0 for strength in STRENGTHS}
        for ev in evidence:
            scores[ev.strength] = max(scores.get(ev.strength, 0.0), ev.overuse_score)
        return scores

    def _coerce_dominant(
        self, raw: Any, scores: dict[str, float]
    ) -> Literal[
        "helpfulness",
        "agreeableness",
        "thoroughness",
        "caution",
        "confidence",
        "brevity",
        "precision",
        "none-observed",
    ]:
        valid = set(STRENGTHS) | {"none-observed"}
        if isinstance(raw, str) and raw.strip().lower() in valid:
            return raw.strip().lower()  # type: ignore[return-value]
        # Fallback: pick highest-scoring strength if above threshold
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for strength in STRENGTHS:
            if scores.get(strength, 0.0) >= max_score - 0.05:
                return strength  # type: ignore[return-value]
        return "none-observed"

    def _coerce_harm(self, raw: Any) -> Literal["none", "low", "medium", "high"]:
        if isinstance(raw, str) and raw.strip().lower() in ("none", "low", "medium", "high"):
            return raw.strip().lower()  # type: ignore[return-value]
        return "none"

    def _overuse_quality(
        self, scores: dict[str, float], raw_quality: str
    ) -> Literal["healthy", "borderline", "overused"]:
        if raw_quality in ("healthy", "borderline", "overused"):
            return raw_quality  # type: ignore[return-value]
        max_score = max(scores.values(), default=0.0)
        if max_score >= 0.6:
            return "overused"
        if max_score >= 0.3:
            return "borderline"
        return "healthy"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentBehaviorTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            f"Harm visible: {trace.harm_visible}",
            "",
        ]
        step_lines: list[str] = []
        for i, step in enumerate(trace.steps):
            ts = (
                f"[{step.timestamp.isoformat()}] "
                if step.timestamp is not None
                else f"[step {i + 1}] "
            )
            step_lines.append(f"{ts}({step.type}) {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Behavior trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
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
