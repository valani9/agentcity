"""SpanLoadCalculator: deterministic quantitative diagnostic of an AI
agent crew's structural load.

Pipeline:
  1. Validate the trace
  2. Compute six metrics LOCALLY (no LLM): max_span, mean_span,
     centralization_index, hierarchy_depth, span_gini, decision_bottleneck
  3. Bucket structural-load quality from the composite score
  4. ONE LLM pass: propose interventions (skipped on "well-balanced")
"""

from __future__ import annotations

import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .metrics import composite_load_score, compute_all_metrics_payload
from .prompts import INTERVENTIONS_PROMPT, SPAN_SYSTEM_PROMPT
from .schema import (
    CrewLoadTrace,
    SpanIntervention,
    SpanLoadAnalysis,
    SpanMetric,
)

log = logging.getLogger("agentcity.span_of_control.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class SpanLoadCalculator:
    """Run the deterministic Span-of-Control / Centralization diagnostic."""

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

    def run(self, trace: CrewLoadTrace) -> SpanLoadAnalysis:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Span-of-Control diagnostic for crew %s (%d agents)",
            trace.crew_id or "<unknown>",
            len(trace.agents),
        )

        # All metrics computed DETERMINISTICALLY — no LLM involvement
        metrics_payload, bottleneck_ids = compute_all_metrics_payload(trace)
        metrics = [
            SpanMetric(
                metric=name,  # type: ignore[arg-type]
                value=value,
                normalized_score=norm,
                explanation=explanation,
            )
            for name, (value, norm, explanation) in metrics_payload.items()
        ]
        load_score = composite_load_score(metrics_payload)
        quality = self._load_quality(load_score)

        interventions = (
            []
            if quality == "well-balanced"
            else self._pass_interventions(
                trace, metrics, metrics_payload, bottleneck_ids, quality, load_score
            )
        )

        analysis = SpanLoadAnalysis(
            crew_id=trace.crew_id,
            metrics=metrics,
            structural_load_score=load_score,
            structural_load_quality=quality,
            bottleneck_agent_ids=bottleneck_ids,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Span-of-Control diagnostic for crew %s done in %.2fs (load=%.2f, quality=%s)",
            trace.crew_id or "<unknown>",
            elapsed,
            load_score,
            quality,
        )
        return analysis

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: CrewLoadTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("CrewLoadTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("CrewLoadTrace.outcome cannot be empty.")
        if not trace.agents:
            raise ValueError("CrewLoadTrace.agents cannot be empty.")

    # --- LLM pass (interventions only — math is locked) ---------------

    def _pass_interventions(
        self,
        trace: CrewLoadTrace,
        metrics: list[SpanMetric],
        metrics_payload: dict[str, tuple[float, float, str]],
        bottleneck_ids: list[str],
        load_quality: str,
        load_score: float,
    ) -> list[SpanIntervention]:
        metrics_table = "\n".join(
            f"- {name}: value={value:.2f}, normalized={norm:.2f}"
            for name, (value, norm, _) in metrics_payload.items()
        )
        roster_lines = []
        for agent in trace.agents:
            reports = ", ".join(agent.reports_to) if agent.reports_to else "(top-level)"
            roster_lines.append(
                f"- {agent.agent_id} | role={agent.role_name} | "
                f"reports_to=[{reports}] | decision_authority={agent.decision_authority}"
            )
        prompt = INTERVENTIONS_PROMPT.format(
            metrics_table=metrics_table,
            bottleneck_ids=", ".join(bottleneck_ids) or "(none)",
            load_quality=load_quality,
            load_score=f"{load_score:.2f}",
            roster="\n".join(roster_lines),
        )
        raw = self._complete(prompt, system=SPAN_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[SpanIntervention] = []
        for entry in data:
            try:
                interventions.append(SpanIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SpanIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _load_quality(
        self, load_score: float
    ) -> Literal["well-balanced", "under-stress", "overloaded"]:
        if load_score < 0.3:
            return "well-balanced"
        if load_score < 0.6:
            return "under-stress"
        return "overloaded"
