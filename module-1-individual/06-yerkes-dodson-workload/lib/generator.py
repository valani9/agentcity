"""WorkloadDetector: diagnose Yerkes-Dodson workload-pressure zones for an
AI agent. Identifies whether the agent is under-pressure (wandering),
optimal (focused), or over-pressure (corner-cutting / freezing /
hallucinating / refusing).

Pipeline:
  1. Validate the trace (non-empty task, outcome, observed_behaviors)
  2. Single LLM pass to score zones + identify failure mode + propose
     interventions
  3. Post-process: fill missing zones, coerce labels, infer distance
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._retry import with_retry

from .prompts import WORKLOAD_PROMPT, YERKES_DODSON_SYSTEM_PROMPT
from .schema import (
    AgentPerformanceTrace,
    WorkloadDetection,
    WorkloadIntervention,
    WorkloadZoneEvidence,
)

log = logging.getLogger("agentcity.yerkes_dodson.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

_ZONES: tuple[str, ...] = ("under_pressure", "optimal", "over_pressure")
_VALID_FAILURE_MODES = {
    "wandering",
    "focused",
    "corner_cutting",
    "freezing",
    "hallucinating",
    "refusing",
    "unknown",
}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class WorkloadDetector:
    """Run the Yerkes-Dodson workload-pressure diagnostic on an agent trace."""

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

    def run(self, trace: AgentPerformanceTrace) -> WorkloadDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Yerkes-Dodson workload detection for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_workload(trace)
        evidence = self._parse_evidence(data.get("zone_evidence", []))
        observed_zone = self._coerce_zone(data.get("observed_zone"), evidence)
        distance = self._coerce_fraction(data.get("distance_from_optimal"), evidence)
        failure_mode = self._coerce_failure_mode(data.get("failure_mode"), observed_zone)
        interventions = self._parse_interventions(data.get("interventions", []), observed_zone)

        detection = WorkloadDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            observed_zone=observed_zone,
            zone_evidence=evidence,
            distance_from_optimal=distance,
            failure_mode=failure_mode,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Yerkes-Dodson detection for agent %s done in %.2fs (zone=%s, mode=%s, distance=%.2f)",
            trace.agent_id or "<unknown>",
            elapsed,
            observed_zone,
            failure_mode,
            distance,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentPerformanceTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentPerformanceTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentPerformanceTrace.outcome cannot be empty.")
        if not trace.observed_behaviors:
            raise ValueError("AgentPerformanceTrace.observed_behaviors cannot be empty.")

    # --- LLM pass ------------------------------------------------------

    def _pass_1_workload(self, trace: AgentPerformanceTrace) -> dict[str, Any]:
        p = trace.pressure
        prompt = WORKLOAD_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            deadline_pressure=p.deadline_pressure,
            budget_pressure=p.budget_pressure,
            retry_cap=p.retry_cap if p.retry_cap is not None else "unbounded",
            error_visibility=p.error_visibility,
            task_complexity=p.task_complexity,
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors),
        )
        raw = self._complete(prompt, system=YERKES_DODSON_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[WorkloadZoneEvidence]:
        evidence: list[WorkloadZoneEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(WorkloadZoneEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed WorkloadZoneEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.zone for ev in evidence}
        for zone in _ZONES:
            if zone not in seen:
                evidence.append(
                    WorkloadZoneEvidence(
                        zone=zone,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )

        order = {z: i for i, z in enumerate(_ZONES)}
        evidence.sort(key=lambda ev: order.get(ev.zone, len(_ZONES)))
        return evidence

    def _parse_interventions(
        self, raw: list[Any], observed_zone: str
    ) -> list[WorkloadIntervention]:
        # Skip interventions if zone is optimal
        if observed_zone == "optimal":
            return []
        interventions: list[WorkloadIntervention] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                interventions.append(WorkloadIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed WorkloadIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _coerce_zone(
        self, raw: Any, evidence: list[WorkloadZoneEvidence]
    ) -> Literal["under_pressure", "optimal", "over_pressure"]:
        if isinstance(raw, str) and raw.strip() in _ZONES:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: highest-scoring zone. If all scores tie (e.g. empty
        # response → all zeros), default to "optimal" rather than picking
        # the first zone in list order.
        if not evidence:
            return "optimal"
        max_score = max(ev.score for ev in evidence)
        if max_score == 0.0:
            return "optimal"
        top = max(evidence, key=lambda ev: ev.score)
        return top.zone

    def _coerce_fraction(self, raw: Any, evidence: list[WorkloadZoneEvidence]) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        # Fallback: distance proportional to confidence in non-optimal zones.
        # If all zone scores are 0 (no data), return 0.0 to match the
        # "optimal" zone fallback rather than treating zero-data as
        # maximum distance.
        if not evidence:
            return 0.0
        max_score = max(ev.score for ev in evidence)
        if max_score == 0.0:
            return 0.0
        optimal_ev = next((ev for ev in evidence if ev.zone == "optimal"), None)
        if optimal_ev is None:
            return 0.5
        return round(max(0.0, min(1.0, 1.0 - optimal_ev.score)), 2)

    def _coerce_failure_mode(
        self, raw: Any, observed_zone: str
    ) -> Literal[
        "wandering",
        "focused",
        "corner_cutting",
        "freezing",
        "hallucinating",
        "refusing",
        "unknown",
    ]:
        if isinstance(raw, str) and raw.strip() in _VALID_FAILURE_MODES:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: infer from zone
        if observed_zone == "optimal":
            return "focused"
        if observed_zone == "under_pressure":
            return "wandering"
        if observed_zone == "over_pressure":
            return "corner_cutting"
        return "unknown"

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
