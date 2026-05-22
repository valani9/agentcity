"""ConflictStyleSelector — Thomas-Kilmann's 5 conflict styles applied
to agent interactions.

Pipeline:
  1. Validate trace (non-empty task, outcome, ≥1 turn)
  2. Pass 1: LLM identifies observed style + optimal style + per-style
     scores + assertiveness/cooperativeness axes
  3. Pass 2: if mismatch > 0, propose recommendations to enable style-
     switching for similar future tasks
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    RECOMMENDATIONS_PROMPT,
    SELECTION_PROMPT,
    TK_SYSTEM_PROMPT,
)
from .schema import (
    STYLES,
    AgentInteractionTrace,
    ConflictStyleSelection,
    StyleRecommendation,
    StyleScore,
)

log = logging.getLogger("agentcity.thomas_kilmann.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class ConflictStyleSelector:
    """Thomas-Kilmann conflict-style selector for AI agent interactions."""

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

    def run(self, trace: AgentInteractionTrace) -> ConflictStyleSelection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Thomas-Kilmann selection for agent %s (turns=%d)",
            trace.agent_id or "<unknown>",
            len(trace.turns),
        )

        selection_data = self._pass_1_selection(trace, trace_text)

        observed = self._coerce_observed(selection_data.get("observed_style", "mixed"))
        optimal = self._coerce_style(selection_data.get("optimal_style", "collaborating"))
        mismatch = self._coerce_float(selection_data.get("style_mismatch", 0.5), 0.0, 1.0)
        assertiveness = self._coerce_float(selection_data.get("assertiveness_score", 0.5), 0.0, 1.0)
        cooperativeness = self._coerce_float(
            selection_data.get("cooperativeness_score", 0.5), 0.0, 1.0
        )
        style_scores = self._coerce_style_scores(selection_data.get("observed_style_scores", {}))

        evidence_raw = selection_data.get("style_evidence", [])
        style_evidence: list[StyleScore] = []
        for entry in evidence_raw:
            if not isinstance(entry, dict):
                continue
            try:
                style_evidence.append(StyleScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StyleScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        rationale = str(selection_data.get("rationale", ""))

        recommendations: list[StyleRecommendation] = []
        if mismatch > 0.05 and observed != optimal:
            recommendations = self._pass_2_recommendations(
                trace, trace_text, observed, optimal, mismatch, rationale
            )

        selection = ConflictStyleSelection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            observed_style=observed,
            optimal_style=optimal,
            style_mismatch=mismatch,
            assertiveness_score=assertiveness,
            cooperativeness_score=cooperativeness,
            observed_style_scores=style_scores,
            style_evidence=style_evidence,
            rationale=rationale,
            recommendations=recommendations,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Thomas-Kilmann selection for agent %s done in %.2fs "
            "(observed=%s, optimal=%s, mismatch=%.2f)",
            trace.agent_id or "<unknown>",
            elapsed,
            observed,
            optimal,
            mismatch,
        )
        return selection

    def _validate_trace(self, trace: AgentInteractionTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentInteractionTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentInteractionTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("AgentInteractionTrace.turns cannot be empty.")

    def _pass_1_selection(self, trace: AgentInteractionTrace, trace_text: str) -> dict[str, Any]:
        prompt = SELECTION_PROMPT.format(
            task=trace.task,
            task_category=trace.task_category or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=TK_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_recommendations(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        observed: str,
        optimal: str,
        mismatch: float,
        rationale: str,
    ) -> list[StyleRecommendation]:
        prompt = RECOMMENDATIONS_PROMPT.format(
            observed=observed,
            optimal=optimal,
            mismatch=mismatch,
            rationale=rationale,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=TK_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)
        recs: list[StyleRecommendation] = []
        for entry in data:
            try:
                recs.append(StyleRecommendation(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StyleRecommendation (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return recs

    # --- Coercion helpers ----------------------------------------------

    @staticmethod
    def _coerce_observed(
        value: Any,
    ) -> Literal[
        "competing", "accommodating", "avoiding", "compromising", "collaborating", "mixed"
    ]:
        if isinstance(value, str) and value in {*STYLES, "mixed"}:
            return value  # type: ignore[return-value]
        return "mixed"

    @staticmethod
    def _coerce_style(
        value: Any,
    ) -> Literal["competing", "accommodating", "avoiding", "compromising", "collaborating"]:
        if isinstance(value, str) and value in STYLES:
            return value  # type: ignore[return-value]
        return "collaborating"

    @staticmethod
    def _coerce_float(value: Any, lo: float, hi: float) -> float:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return (lo + hi) / 2
        return max(lo, min(hi, f))

    @staticmethod
    def _coerce_style_scores(value: Any) -> dict[str, float]:
        scores: dict[str, float] = {s: 0.0 for s in STYLES}
        if isinstance(value, dict):
            for k, v in value.items():
                if k in STYLES:
                    try:
                        scores[k] = max(0.0, min(1.0, float(v)))
                    except (TypeError, ValueError):
                        continue
        return scores

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentInteractionTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Task category: {trace.task_category or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        turn_lines = []
        for i, t in enumerate(trace.turns):
            ts = f"[{t.timestamp.isoformat()}] " if t.timestamp is not None else f"[turn {i + 1}] "
            turn_lines.append(f"{ts}{t.role}: {t.content}")
        full = "\n".join(header + turn_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning("TK trace exceeds max_trace_chars; truncating")
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRUNCATED ({len(full) - self.max_trace_chars} chars) ...]\n\n"
            + full[-keep:]
        )

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
