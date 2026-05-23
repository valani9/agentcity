"""CultureProfileDetector: profile an agent's behavior on Robbins & Judge's
seven culture characteristics, and identify where it doesn't match the
target profile for the task class.

Pipeline:
  1. Validate the trace (non-empty task, outcome, task_class, prompt or behaviors)
  2. Pass 1: LLM scores all 7 characteristics observed vs target + picks
     biggest gap + fit quality
  3. Pass 2: propose interventions to close the gap (skipped on well-fit)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, PROFILE_PROMPT, ROBBINS_SYSTEM_PROMPT
from .schema import (
    CULTURE_CHARACTERISTICS,
    AgentCultureTrace,
    CharacteristicScore,
    CultureIntervention,
    CultureProfileDetection,
)

log = logging.getLogger("agentcity.robbins_culture.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class CultureProfileDetector:
    """Run the 7-Characteristics culture profile diagnostic."""

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

    def run(self, trace: AgentCultureTrace) -> CultureProfileDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running 7-Characteristics culture profile for agent %s (task_class=%s)",
            trace.agent_id or "<unknown>",
            trace.task_class,
        )

        data = self._pass_1_profile(trace)
        characteristics = self._parse_characteristics(data.get("characteristics", []))
        overall_fit = self._coerce_fraction(
            data.get("overall_fit"), default=self._compute_overall_fit(characteristics)
        )
        biggest_gap = self._coerce_gap(data.get("biggest_gap"), characteristics)
        fit_quality = self._fit_quality(
            overall_fit, str(data.get("fit_quality", "")).strip().lower()
        )

        interventions = (
            []
            if fit_quality == "well-fit"
            else self._pass_2_interventions(trace, characteristics, biggest_gap, fit_quality)
        )

        detection = CultureProfileDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            characteristics=characteristics,
            overall_fit=overall_fit,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "7-Characteristics profile for agent %s done in %.2fs (fit=%.2f, quality=%s, gap=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            overall_fit,
            fit_quality,
            biggest_gap,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentCultureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentCultureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentCultureTrace.outcome cannot be empty.")
        if not trace.system_prompt and not trace.observed_behaviors:
            raise ValueError(
                "AgentCultureTrace must include at least one of system_prompt or "
                "observed_behaviors."
            )

    # --- LLM passes ----------------------------------------------------

    def _pass_1_profile(self, trace: AgentCultureTrace) -> dict[str, Any]:
        prompt = PROFILE_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
        )
        raw = self._complete(prompt, system=ROBBINS_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        trace: AgentCultureTrace,
        characteristics: list[CharacteristicScore],
        biggest_gap: str,
        fit_quality: str,
    ) -> list[CultureIntervention]:
        evidence_text = json.dumps([c.model_dump() for c in characteristics], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            task_class=trace.task_class,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=ROBBINS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[CultureIntervention] = []
        for entry in data:
            try:
                interventions.append(CultureIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed CultureIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_characteristics(self, raw: list[Any]) -> list[CharacteristicScore]:
        scores: list[CharacteristicScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                scores.append(CharacteristicScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed CharacteristicScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {s.characteristic for s in scores}
        for c in CULTURE_CHARACTERISTICS:
            if c not in seen:
                scores.append(
                    CharacteristicScore(
                        characteristic=c,  # type: ignore[arg-type]
                        observed_score=0.5,
                        target_score=0.5,
                        fit_score=1.0,
                        explanation="No data observed; defaulting to neutral.",
                        evidence_quotes=[],
                    )
                )

        order = {c: i for i, c in enumerate(CULTURE_CHARACTERISTICS)}
        scores.sort(key=lambda s: order.get(s.characteristic, len(CULTURE_CHARACTERISTICS)))
        return scores

    def _compute_overall_fit(self, scores: list[CharacteristicScore]) -> float:
        if not scores:
            return 0.0
        return round(sum(s.fit_score for s in scores) / len(scores), 2)

    def _coerce_fraction(self, raw: Any, default: float = 0.0) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, value))

    def _coerce_gap(
        self, raw: Any, scores: list[CharacteristicScore]
    ) -> Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
        "none",
    ]:
        valid = set(CULTURE_CHARACTERISTICS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: largest |observed - target| among the scores
        if not scores:
            return "none"
        biggest = max(scores, key=lambda s: abs(s.observed_score - s.target_score))
        if abs(biggest.observed_score - biggest.target_score) < 0.1:
            return "none"
        return biggest.characteristic

    def _fit_quality(
        self, overall_fit: float, raw_quality: str
    ) -> Literal["well-fit", "partial-fit", "misfit"]:
        if raw_quality in ("well-fit", "partial-fit", "misfit"):
            return raw_quality  # type: ignore[return-value]
        if overall_fit >= 0.8:
            return "well-fit"
        if overall_fit >= 0.5:
            return "partial-fit"
        return "misfit"

    # --- JSON object extraction ----------------------------------------

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
