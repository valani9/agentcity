"""StructureMatrixAnalyzer: diagnose org-structure fit for an AI agent
crew.

Pipeline:
  1. Validate the trace (non-empty task + outcome + at least one agent)
  2. Pass 1: LLM scores all six structural dimensions + archetype +
     overall fit
  3. Determine fit-quality bucket
  4. Pass 2: propose interventions (skipped if fit-quality is "well-fit")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, STRUCTURE_PROMPT, STRUCTURE_SYSTEM_PROMPT
from .schema import (
    STRUCTURE_DIMENSIONS,
    CrewStructureTrace,
    StructureAnalysis,
    StructureDimensionScore,
    StructureIntervention,
)

log = logging.getLogger("agentcity.org_structure.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

_VALID_ARCHETYPES = {
    "flat-peer",
    "hierarchical",
    "centralized-functional",
    "decentralized-product",
    "matrix",
    "mixed",
}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class StructureMatrixAnalyzer:
    """Run the Org-Structure Matrix diagnostic on a CrewStructureTrace."""

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

    def run(self, trace: CrewStructureTrace) -> StructureAnalysis:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Org-Structure Matrix analysis for crew %s (%d agents)",
            trace.crew_id or "<unknown>",
            len(trace.agents),
        )

        data = self._pass_1_structure(trace)
        dimensions = self._parse_dimensions(data.get("dimensions", []))
        overall_fit = self._compute_overall_fit(dimensions, data.get("overall_fit"))
        archetype = self._coerce_archetype(data.get("archetype"))
        biggest_gap = self._coerce_biggest_gap(data.get("biggest_gap"), dimensions)
        fit_quality = self._fit_quality(
            overall_fit, str(data.get("fit_quality", "")).strip().lower()
        )

        interventions = (
            []
            if fit_quality == "well-fit"
            else self._pass_2_interventions(
                dimensions, archetype, biggest_gap, fit_quality, trace.task_class
            )
        )

        analysis = StructureAnalysis(
            crew_id=trace.crew_id,
            task_class=trace.task_class,
            archetype=archetype,
            dimensions=dimensions,
            overall_fit=overall_fit,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Org-Structure Matrix analysis for crew %s done in %.2fs "
            "(archetype=%s, fit=%.2f, gap=%s, quality=%s)",
            trace.crew_id or "<unknown>",
            elapsed,
            archetype,
            overall_fit,
            biggest_gap,
            fit_quality,
        )
        return analysis

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: CrewStructureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("CrewStructureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("CrewStructureTrace.outcome cannot be empty.")
        if not trace.agents:
            raise ValueError("CrewStructureTrace.agents cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_structure(self, trace: CrewStructureTrace) -> dict[str, Any]:
        roster_lines: list[str] = []
        for agent in trace.agents:
            reports = ", ".join(agent.reports_to) if agent.reports_to else "(top-level)"
            roster_lines.append(
                f"- {agent.agent_id} | role={agent.role_name} | "
                f"reports_to=[{reports}] | grouped_by={agent.grouped_by} | "
                f"decision_authority={agent.decision_authority}"
            )

        prompt = STRUCTURE_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            outcome=trace.outcome,
            success=trace.success,
            n_agents=len(trace.agents),
            roster="\n".join(roster_lines),
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
        )
        raw = self._complete(prompt, system=STRUCTURE_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        dimensions: list[StructureDimensionScore],
        archetype: str,
        biggest_gap: str,
        fit_quality: str,
        task_class: str,
    ) -> list[StructureIntervention]:
        evidence_text = json.dumps([d.model_dump() for d in dimensions], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            task_class=task_class,
            archetype=archetype,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=STRUCTURE_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[StructureIntervention] = []
        for entry in data:
            try:
                interventions.append(StructureIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StructureIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_dimensions(self, raw: list[Any]) -> list[StructureDimensionScore]:
        dims: list[StructureDimensionScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                dims.append(StructureDimensionScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StructureDimensionScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {d.dimension for d in dims}
        for dim in STRUCTURE_DIMENSIONS:
            if dim not in seen:
                dims.append(
                    StructureDimensionScore(
                        dimension=dim,  # type: ignore[arg-type]
                        observed_score=0.0,
                        target_score=0.5,
                        fit_score=0.5,
                        explanation="No evidence observed for this dimension.",
                        evidence_quotes=[],
                    )
                )

        order = {d: i for i, d in enumerate(STRUCTURE_DIMENSIONS)}
        dims.sort(key=lambda d: order.get(d.dimension, len(STRUCTURE_DIMENSIONS)))
        return dims

    def _compute_overall_fit(self, dimensions: list[StructureDimensionScore], raw: Any) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not dimensions:
            return 0.0
        mean = sum(d.fit_score for d in dimensions) / len(dimensions)
        return round(max(0.0, min(1.0, mean)), 2)

    def _coerce_archetype(
        self, raw: Any
    ) -> Literal[
        "flat-peer",
        "hierarchical",
        "centralized-functional",
        "decentralized-product",
        "matrix",
        "mixed",
    ]:
        if isinstance(raw, str) and raw.strip() in _VALID_ARCHETYPES:
            return raw.strip()  # type: ignore[return-value]
        return "mixed"

    def _coerce_biggest_gap(
        self, raw: Any, dimensions: list[StructureDimensionScore]
    ) -> Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
        "none",
    ]:
        valid = set(STRUCTURE_DIMENSIONS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: compute biggest gap from dimensions
        if not dimensions:
            return "none"
        worst = max(dimensions, key=lambda d: abs(d.observed_score - d.target_score))
        gap = abs(worst.observed_score - worst.target_score)
        if gap < 0.15:
            return "none"
        return worst.dimension

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
