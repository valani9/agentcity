"""ReappraisalDetector: diagnose Gross's emotion-regulation strategy
for an AI agent (reappraisal vs suppression vs rumination vs avoidance
vs expression).

Pipeline:
  1. Validate the trace (non-empty user_input + agent_response + outcome)
  2. Pass 1: LLM scores all 6 strategies + identifies dominant + buckets adaptivity
  3. Pass 2: propose interventions (skipped if adaptivity is "adaptive")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import GROSS_SYSTEM_PROMPT, INTERVENTIONS_PROMPT, STRATEGY_PROMPT
from .schema import (
    REGULATION_STRATEGIES,
    AgentRegulationTrace,
    RegulationDetection,
    RegulationIntervention,
    StrategyEvidence,
)

log = logging.getLogger("agentcity.cognitive_reappraisal.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class ReappraisalDetector:
    """Run the Cognitive Reappraisal (Gross) diagnostic on an agent's response."""

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

    def run(self, trace: AgentRegulationTrace) -> RegulationDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Cognitive Reappraisal diagnostic for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_strategy(trace)
        evidence = self._parse_evidence(data.get("strategy_evidence", []))
        dominant = self._coerce_dominant(data.get("dominant_strategy"), evidence)
        adaptivity = self._coerce_adaptivity(
            str(data.get("adaptivity", "")).strip().lower(), evidence, dominant
        )

        interventions = (
            []
            if adaptivity == "adaptive"
            else self._pass_2_interventions(evidence, dominant, adaptivity)
        )

        detection = RegulationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            strategy_evidence=evidence,
            dominant_strategy=dominant,
            adaptivity=adaptivity,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Reappraisal diagnostic for agent %s done in %.2fs (dominant=%s, adaptivity=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            adaptivity,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentRegulationTrace) -> None:
        if not trace.user_input or not trace.user_input.strip():
            raise ValueError("AgentRegulationTrace.user_input cannot be empty.")
        if not trace.agent_response or not trace.agent_response.strip():
            raise ValueError("AgentRegulationTrace.agent_response cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentRegulationTrace.outcome cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_strategy(self, trace: AgentRegulationTrace) -> dict[str, Any]:
        prompt = STRATEGY_PROMPT.format(
            user_emotion_label=trace.user_emotion_label,
            user_emotion_intensity=trace.user_emotion_intensity,
            user_input=trace.user_input,
            agent_response=trace.agent_response,
            agent_internal_state=trace.agent_internal_state or "(none)",
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._complete(prompt, system=GROSS_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        evidence: list[StrategyEvidence],
        dominant: str,
        adaptivity: str,
    ) -> list[RegulationIntervention]:
        evidence_text = json.dumps([ev.model_dump() for ev in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_strategy=dominant,
            adaptivity=adaptivity,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=GROSS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[RegulationIntervention] = []
        for entry in data:
            try:
                interventions.append(RegulationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RegulationIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[StrategyEvidence]:
        evidence: list[StrategyEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(StrategyEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StrategyEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.strategy for ev in evidence}
        for strat in REGULATION_STRATEGIES:
            if strat not in seen:
                evidence.append(
                    StrategyEvidence(
                        strategy=strat,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed for this strategy.",
                        evidence_quotes=[],
                    )
                )

        order = {s: i for i, s in enumerate(REGULATION_STRATEGIES)}
        evidence.sort(key=lambda ev: order.get(ev.strategy, len(REGULATION_STRATEGIES)))
        return evidence

    def _coerce_dominant(
        self, raw: Any, evidence: list[StrategyEvidence]
    ) -> Literal[
        "reappraisal",
        "suppression",
        "rumination",
        "avoidance",
        "expression",
        "none",
    ]:
        if isinstance(raw, str) and raw.strip() in REGULATION_STRATEGIES:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: highest-scoring strategy, or "none" if all are 0
        if not evidence:
            return "none"
        top = max(evidence, key=lambda ev: ev.score)
        if top.score == 0.0:
            return "none"
        return top.strategy

    def _coerce_adaptivity(
        self,
        raw: str,
        evidence: list[StrategyEvidence],
        dominant: str,
    ) -> Literal["adaptive", "mixed", "maladaptive"]:
        if raw in ("adaptive", "mixed", "maladaptive"):
            return raw  # type: ignore[return-value]
        # Fallback: dominant strategy implies adaptivity
        if dominant == "reappraisal":
            reappraisal_score = next(
                (ev.score for ev in evidence if ev.strategy == "reappraisal"), 0.0
            )
            return "adaptive" if reappraisal_score >= 0.6 else "mixed"
        if dominant in ("suppression", "rumination", "avoidance"):
            return "maladaptive"
        return "mixed"

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
