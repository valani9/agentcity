"""ProcessGainLossDetector: diagnose Steiner / Robbins-&-Judge process
gain or process loss in a multi-agent team vs. its individual-agent
baselines.

Pipeline:
  1. Validate (>=2 baselines, non-empty task + team result)
  2. Compute the gain/loss score from team quality vs. best individual
  3. Compute the cost-overhead ratio if cost data is present
  4. Pass 1: LLM scores the six canonical process-loss factors against
     the comparison + interaction log
  5. Determine the process-quality bucket
  6. Pass 2: propose interventions for the dominant factor (skipped on
     process gain)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    FACTOR_SCORING_PROMPT,
    INTERVENTIONS_PROMPT,
    PROCESS_SYSTEM_PROMPT,
)
from .schema import (
    PROCESS_FACTORS,
    IndividualBaseline,
    ProcessFactorEvidence,
    ProcessGainLossDetection,
    ProcessIntervention,
    ProcessTrace,
)

log = logging.getLogger("agentcity.process_gain_loss.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class ProcessGainLossDetector:
    """Run the Process Gain/Loss diagnostic on a ProcessTrace."""

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

    def run(self, trace: ProcessTrace) -> ProcessGainLossDetection:
        self._validate_trace(trace)

        # Synthesis: quality metrics
        best_baseline = max(trace.individual_baselines, key=lambda b: b.quality_score)
        individual_best_q = best_baseline.quality_score
        individual_mean_q = sum(b.quality_score for b in trace.individual_baselines) / len(
            trace.individual_baselines
        )
        team_q = trace.team_result.quality_score
        gain_loss = round(team_q - individual_best_q, 3)
        quality_bucket = self._process_quality(gain_loss)
        cost_overhead = self._cost_overhead(trace, best_baseline)

        started = time.monotonic()
        log.info(
            "Running Process Gain/Loss diagnostic for trace %s "
            "(individual_best=%.2f, team=%.2f, gain_loss=%+.2f)",
            trace.trace_id or "<unknown>",
            individual_best_q,
            team_q,
            gain_loss,
        )

        # On process gain, skip both LLM passes.
        if quality_bucket == "process-gain":
            log.info(
                "Process gain (%.2f) — skipping factor + intervention passes",
                gain_loss,
            )
            return ProcessGainLossDetection(
                trace_id=trace.trace_id,
                process_quality=quality_bucket,
                gain_loss_score=gain_loss,
                individual_best_quality=individual_best_q,
                individual_best_agent=best_baseline.agent_name,
                individual_mean_quality=round(individual_mean_q, 3),
                team_quality=team_q,
                contributing_factors=[],
                interventions=[],
                cost_overhead_ratio=cost_overhead,
                generator_model=self.model,
                success=trace.success,
            )

        factors = self._pass_1_factors(
            trace, individual_best_q, individual_mean_q, team_q, gain_loss
        )
        interventions = self._pass_2_interventions(trace, factors, quality_bucket, gain_loss)

        detection = ProcessGainLossDetection(
            trace_id=trace.trace_id,
            process_quality=quality_bucket,
            gain_loss_score=gain_loss,
            individual_best_quality=individual_best_q,
            individual_best_agent=best_baseline.agent_name,
            individual_mean_quality=round(individual_mean_q, 3),
            team_quality=team_q,
            contributing_factors=factors,
            interventions=interventions,
            cost_overhead_ratio=cost_overhead,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Process Gain/Loss diagnostic for trace %s done in %.2fs "
            "(quality=%s, gain_loss=%+.2f, interventions=%d)",
            trace.trace_id or "<unknown>",
            elapsed,
            quality_bucket,
            gain_loss,
            len(interventions),
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: ProcessTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("ProcessTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("ProcessTrace.outcome cannot be empty.")
        if len(trace.individual_baselines) < 2:
            raise ValueError("ProcessTrace.individual_baselines must contain at least 2 baselines.")
        if not trace.team_result.agents:
            raise ValueError("ProcessTrace.team_result.agents cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_factors(
        self,
        trace: ProcessTrace,
        individual_best_q: float,
        individual_mean_q: float,
        team_q: float,
        gain_loss: float,
    ) -> list[ProcessFactorEvidence]:
        baselines_text = json.dumps(
            [b.model_dump() for b in trace.individual_baselines],
            indent=2,
            default=str,
        )
        team_text = json.dumps(trace.team_result.model_dump(), indent=2, default=str)
        interaction = self._truncate(trace.interaction_log) or "(no interaction log provided)"

        prompt = FACTOR_SCORING_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            baselines=baselines_text,
            team_result=team_text,
            interaction_log=interaction,
            individual_best_quality=f"{individual_best_q:.2f}",
            individual_mean_quality=f"{individual_mean_q:.2f}",
            team_quality=f"{team_q:.2f}",
            gain_loss_score=f"{gain_loss:+.2f}",
        )
        raw = self._complete(prompt, system=PROCESS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        factors: list[ProcessFactorEvidence] = []
        for entry in data:
            try:
                factors.append(ProcessFactorEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed ProcessFactorEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {f.factor for f in factors}
        for f_name in PROCESS_FACTORS:
            if f_name not in seen:
                factors.append(
                    ProcessFactorEvidence(
                        factor=f_name,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this factor observed.",
                        evidence_quotes=[],
                    )
                )

        order = {f_name: i for i, f_name in enumerate(PROCESS_FACTORS)}
        factors.sort(key=lambda f: order.get(f.factor, len(PROCESS_FACTORS)))
        return factors

    def _pass_2_interventions(
        self,
        trace: ProcessTrace,
        factors: list[ProcessFactorEvidence],
        quality: str,
        gain_loss: float,
    ) -> list[ProcessIntervention]:
        evidence_text = json.dumps([f.model_dump() for f in factors], indent=2, default=str)
        interaction = self._truncate(trace.interaction_log) or "(no interaction log provided)"
        prompt = INTERVENTIONS_PROMPT.format(
            process_quality=quality,
            gain_loss_score=f"{gain_loss:+.2f}",
            evidence=evidence_text,
            interaction_log=interaction,
        )
        raw = self._complete(prompt, system=PROCESS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[ProcessIntervention] = []
        for entry in data:
            try:
                interventions.append(ProcessIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed ProcessIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _process_quality(
        self, gain_loss: float
    ) -> Literal["process-gain", "neutral", "process-loss"]:
        if gain_loss > 0.05:
            return "process-gain"
        if gain_loss < -0.05:
            return "process-loss"
        return "neutral"

    def _cost_overhead(
        self,
        trace: ProcessTrace,
        best_baseline: IndividualBaseline,
    ) -> float | None:
        team_cost = trace.team_result.cost_units
        individual_cost = best_baseline.cost_units
        if team_cost is None or individual_cost is None or individual_cost <= 0:
            return None
        return round(team_cost / individual_cost, 2)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_trace_chars:
            return text
        log.warning(
            "Interaction log exceeds max_trace_chars (%d > %d); truncating",
            len(text),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            text[:keep]
            + f"\n\n[... LOG TRUNCATED ({len(text) - self.max_trace_chars} chars omitted) ...]\n\n"
            + text[-keep:]
        )
