"""OrchestratorModeDetector: diagnose McGregor Theory X vs Theory Y vs
hybrid mode in an orchestrator-agent interaction trace.

Pipeline:
  1. Validate the trace (non-empty task, outcome, sub-agents, steps)
  2. Pass 1: LLM scores observed_mode + optimal_mode + indicators + rationale
     against the task properties + interaction trace
  3. Determine the mode-quality bucket from mode_mismatch
  4. Pass 2: propose interventions targeting the optimal mode
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
    INTERVENTIONS_PROMPT,
    MCGREGOR_SYSTEM_PROMPT,
    MODE_SCORING_PROMPT,
)
from .schema import (
    ModeIndicators,
    OrchestratorIntervention,
    OrchestratorModeDetection,
    OrchestratorTrace,
)

log = logging.getLogger("agentcity.mcgregor.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class OrchestratorModeDetector:
    """Run the Theory X/Y diagnostic on an OrchestratorTrace."""

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

    def run(self, trace: OrchestratorTrace) -> OrchestratorModeDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Orchestrator Mode detection for trace %s (sub_agents=%d, steps=%d)",
            trace.trace_id or "<unknown>",
            len(trace.sub_agents),
            len(trace.steps),
        )

        data = self._pass_1_mode(trace, trace_text)
        observed = self._coerce_mode(data.get("observed_mode"))
        optimal = self._coerce_mode(data.get("optimal_mode"))
        mismatch = self._coerce_fraction(data.get("mode_mismatch"))
        indicators = self._parse_indicators(data.get("indicators", {}))
        rationale = str(data.get("rationale", "")).strip()
        quality = self._mode_quality(mismatch, str(data.get("mode_quality", "")).strip().lower())

        interventions = (
            []
            if quality == "well-matched"
            else self._pass_2_interventions(
                trace, trace_text, observed, optimal, mismatch, quality, rationale, indicators
            )
        )

        detection = OrchestratorModeDetection(
            trace_id=trace.trace_id,
            observed_mode=observed,
            optimal_mode=optimal,
            mode_mismatch=mismatch,
            indicators=indicators,
            mode_quality=quality,
            rationale=rationale,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Orchestrator Mode detection for trace %s done in %.2fs "
            "(observed=%s, optimal=%s, quality=%s, mismatch=%.2f)",
            trace.trace_id or "<unknown>",
            elapsed,
            observed,
            optimal,
            quality,
            mismatch,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: OrchestratorTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("OrchestratorTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("OrchestratorTrace.outcome cannot be empty.")
        if not trace.sub_agents:
            raise ValueError("OrchestratorTrace.sub_agents cannot be empty.")
        if not trace.steps:
            raise ValueError("OrchestratorTrace.steps cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_mode(self, trace: OrchestratorTrace, trace_text: str) -> dict[str, Any]:
        props = trace.task_properties
        prompt = MODE_SCORING_PROMPT.format(
            task=trace.task,
            sub_agents=", ".join(trace.sub_agents),
            outcome=trace.outcome,
            success=trace.success,
            risk_level=props.risk_level,
            complexity=props.complexity,
            reversibility=props.reversibility,
            regulatory_exposure=props.regulatory_exposure,
            agent_capability=props.agent_capability,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=MCGREGOR_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        trace: OrchestratorTrace,
        trace_text: str,
        observed: str,
        optimal: str,
        mismatch: float,
        quality: str,
        rationale: str,
        indicators: ModeIndicators,
    ) -> list[OrchestratorIntervention]:
        prompt = INTERVENTIONS_PROMPT.format(
            observed_mode=observed,
            optimal_mode=optimal,
            mode_mismatch=f"{mismatch:.2f}",
            mode_quality=quality,
            rationale=rationale or "(none provided)",
            indicators=json.dumps(indicators.model_dump(), indent=2, default=str),
            trace=trace_text,
        )
        raw = self._complete(prompt, system=MCGREGOR_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[OrchestratorIntervention] = []
        for entry in data:
            try:
                interventions.append(OrchestratorIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed OrchestratorIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _coerce_mode(self, raw: Any) -> Literal["theory_x", "theory_y", "hybrid"]:
        if isinstance(raw, str) and raw.strip().lower() in ("theory_x", "theory_y", "hybrid"):
            return raw.strip().lower()  # type: ignore[return-value]
        return "hybrid"

    def _coerce_fraction(self, raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    def _parse_indicators(self, raw: dict[str, Any]) -> ModeIndicators:
        if not isinstance(raw, dict):
            raw = {}
        try:
            return ModeIndicators(
                check_in_frequency=self._coerce_fraction(raw.get("check_in_frequency", 0.0)),
                autonomy_granted=self._coerce_fraction(raw.get("autonomy_granted", 0.0)),
                pre_approval_required=self._coerce_fraction(raw.get("pre_approval_required", 0.0)),
                intervention_rate=self._coerce_fraction(raw.get("intervention_rate", 0.0)),
                explanation=str(raw.get("explanation", "")).strip()
                or "No indicator explanation provided by the model.",
                evidence_quotes=[
                    str(q) for q in raw.get("evidence_quotes", []) if isinstance(q, str)
                ],
            )
        except Exception as exc:
            log.warning(
                "Could not parse indicators (%s); using zero baseline.",
                type(exc).__name__,
            )
            return ModeIndicators(
                check_in_frequency=0.0,
                autonomy_granted=0.0,
                pre_approval_required=0.0,
                intervention_rate=0.0,
                explanation="Indicators could not be parsed from the model response.",
                evidence_quotes=[],
            )

    def _mode_quality(
        self, mismatch: float, raw_quality: str
    ) -> Literal["well-matched", "mild-mismatch", "severe-mismatch"]:
        if raw_quality in ("well-matched", "mild-mismatch", "severe-mismatch"):
            return raw_quality  # type: ignore[return-value]
        if mismatch <= 0.2:
            return "well-matched"
        if mismatch <= 0.5:
            return "mild-mismatch"
        return "severe-mismatch"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: OrchestratorTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Sub-agents: {', '.join(trace.sub_agents)}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            f"Risk: {trace.task_properties.risk_level}",
            f"Complexity: {trace.task_properties.complexity}",
            f"Reversibility: {trace.task_properties.reversibility}",
            f"Regulatory exposure: {trace.task_properties.regulatory_exposure}",
            f"Agent capability: {trace.task_properties.agent_capability}",
            "",
        ]
        step_lines: list[str] = []
        for i, step in enumerate(trace.steps):
            ts = (
                f"[{step.timestamp.isoformat()}] "
                if step.timestamp is not None
                else f"[step {i + 1}] "
            )
            target = f" -> {step.sub_agent}" if step.sub_agent else ""
            step_lines.append(f"{ts}({step.step_type}, by={step.actor}{target}) {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Orchestrator trace exceeds max_trace_chars (%d > %d); truncating",
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
