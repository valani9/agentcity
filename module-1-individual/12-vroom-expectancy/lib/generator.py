"""VroomExpectancyCalculator: diagnose Vroom's E × I × V motivation
calculus for an AI agent and identify the bottleneck term.

Pipeline:
  1. Validate the trace (non-empty task + outcome + at least one of
     system_prompt / observed_behaviors / effort_signals)
  2. Pass 1: LLM scores E, I, V from evidence
  3. RE-COMPUTE motivation_score = E × I × V in Python (LLM cannot override)
  4. Identify bottleneck term + bucket motivation quality
  5. Pass 2: propose interventions (skipped if motivation is "motivated")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, TERMS_PROMPT, VROOM_SYSTEM_PROMPT
from .schema import (
    VROOM_TERMS,
    AgentExpectancyTrace,
    VroomDetection,
    VroomIntervention,
    VroomTermScore,
)

log = logging.getLogger("agentcity.vroom_expectancy.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class VroomExpectancyCalculator:
    """Run the Vroom Expectancy diagnostic on an AgentExpectancyTrace."""

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

    def run(self, trace: AgentExpectancyTrace) -> VroomDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Vroom Expectancy diagnostic for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_terms(trace)
        terms = self._parse_terms(data.get("terms", []))
        # CRITICAL: re-compute the product in Python. The LLM cannot override.
        motivation_score = self._compute_motivation(terms)
        bottleneck = self._coerce_bottleneck(data.get("bottleneck_term"), terms)
        quality = self._motivation_quality(
            motivation_score, str(data.get("motivation_quality", "")).strip().lower()
        )

        interventions = (
            []
            if quality == "motivated"
            else self._pass_2_interventions(
                terms, bottleneck, motivation_score, quality, trace.task_class
            )
        )

        detection = VroomDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            terms=terms,
            motivation_score=motivation_score,
            bottleneck_term=bottleneck,
            motivation_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Vroom diagnostic for agent %s done in %.2fs (score=%.2f, bottleneck=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            motivation_score,
            bottleneck,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentExpectancyTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentExpectancyTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentExpectancyTrace.outcome cannot be empty.")
        if not trace.system_prompt and not trace.observed_behaviors and not trace.effort_signals:
            raise ValueError(
                "AgentExpectancyTrace must include at least one of system_prompt, "
                "observed_behaviors, or effort_signals."
            )

    # --- LLM passes ----------------------------------------------------

    def _pass_1_terms(self, trace: AgentExpectancyTrace) -> dict[str, Any]:
        prompt = TERMS_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
            effort_signals="\n".join(f"- {e}" for e in trace.effort_signals) or "(none)",
        )
        raw = self._complete(prompt, system=VROOM_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        terms: list[VroomTermScore],
        bottleneck: str,
        motivation_score: float,
        quality: str,
        task_class: str,
    ) -> list[VroomIntervention]:
        evidence_text = json.dumps([t.model_dump() for t in terms], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            bottleneck_term=bottleneck,
            motivation_quality=quality,
            motivation_score=f"{motivation_score:.2f}",
            task_class=task_class,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=VROOM_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[VroomIntervention] = []
        for entry in data:
            try:
                interventions.append(VroomIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed VroomIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + DETERMINISTIC computation --------------------------

    def _parse_terms(self, raw: list[Any]) -> list[VroomTermScore]:
        terms: list[VroomTermScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                terms.append(VroomTermScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed VroomTermScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {t.term for t in terms}
        for term in VROOM_TERMS:
            if term not in seen:
                terms.append(
                    VroomTermScore(
                        term=term,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed for this term.",
                        evidence_quotes=[],
                    )
                )

        order = {t: i for i, t in enumerate(VROOM_TERMS)}
        terms.sort(key=lambda t: order.get(t.term, len(VROOM_TERMS)))
        return terms

    def _compute_motivation(self, terms: list[VroomTermScore]) -> float:
        """Re-compute E × I × V deterministically. The LLM cannot override
        this — it's pure math on the scored terms.

        E and I are clamped to [0, 1] (out-of-range scores get clipped).
        V is in [-1, 1] as scored. Product is clipped to [-1, 1].
        """
        by_term = {t.term: t.score for t in terms}
        e = max(0.0, min(1.0, by_term.get("expectancy", 0.0)))
        i = max(0.0, min(1.0, by_term.get("instrumentality", 0.0)))
        v = max(-1.0, min(1.0, by_term.get("valence", 0.0)))
        product = e * i * v
        return round(max(-1.0, min(1.0, product)), 4)

    def _coerce_bottleneck(
        self, raw: Any, terms: list[VroomTermScore]
    ) -> Literal["expectancy", "instrumentality", "valence", "none"]:
        valid = set(VROOM_TERMS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: identify the bottleneck term as the one with lowest
        # multiplicative contribution. For E and I that's the lowest value;
        # for V, the value closest to (or below) zero.
        if not terms:
            return "none"
        by_term = {t.term: t.score for t in terms}
        e = by_term.get("expectancy", 0.5)
        i = by_term.get("instrumentality", 0.5)
        v = by_term.get("valence", 0.5)
        # "None" when all terms are decent
        if e >= 0.6 and i >= 0.6 and v >= 0.6:
            return "none"
        # Pick the term that contributes least to the product
        # (effective value for the bottleneck question)
        candidates = [("expectancy", e), ("instrumentality", i), ("valence", v)]
        bottleneck = min(candidates, key=lambda c: c[1])
        return bottleneck[0]  # type: ignore[return-value]

    def _motivation_quality(
        self, motivation_score: float, raw_quality: str
    ) -> Literal["motivated", "weak", "collapsed"]:
        if raw_quality in ("motivated", "weak", "collapsed"):
            return raw_quality  # type: ignore[return-value]
        if motivation_score >= 0.4:
            return "motivated"
        if motivation_score > 0.05:
            return "weak"
        return "collapsed"

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
