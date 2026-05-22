"""BiasStackDetector: diagnose the four canonical Kahneman/Tversky biases
(anchoring, overconfidence, confirmation, escalation-of-commitment) in
an agent reasoning trace.

Pipeline:
  1. Validate the trace (non-empty task, outcome, at least one step)
  2. Pass 1: LLM scores all four biases against the trace
  3. Identify the dominant bias (anchoring wins tie-breaks — it's the
     foundational bias from which the others compound)
  4. Compute the overall reasoning-quality label
  5. Pass 2: propose interventions targeting the dominant bias
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import BIAS_SCORING_PROMPT, BIAS_SYSTEM_PROMPT, INTERVENTIONS_PROMPT
from .schema import (
    BIASES,
    AgentReasoningTrace,
    BiasEvidence,
    BiasIntervention,
    BiasStackDetection,
)

log = logging.getLogger("agentcity.bias_stack.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class BiasStackDetector:
    """Run the Bias-Stack diagnostic on an AgentReasoningTrace."""

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

    def run(self, trace: AgentReasoningTrace) -> BiasStackDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Bias-Stack detection for agent %s (steps=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.steps),
            trace.success,
        )

        evidence = self._pass_1_scores(trace, trace_text)
        bias_scores = self._build_scores(evidence)
        dominant = self._dominant_bias(bias_scores)
        interventions = self._pass_2_interventions(trace, trace_text, evidence, dominant)
        quality = self._reasoning_quality(bias_scores)

        detection = BiasStackDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_bias=dominant,
            bias_scores=bias_scores,
            biases=evidence,
            interventions=interventions,
            overall_reasoning_quality=quality,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Bias-Stack detection for agent %s done in %.2fs "
            "(dominant=%s, quality=%s, interventions=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            quality,
            len(interventions),
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentReasoningTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentReasoningTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentReasoningTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("AgentReasoningTrace.steps cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_scores(self, trace: AgentReasoningTrace, trace_text: str) -> list[BiasEvidence]:
        prompt = BIAS_SCORING_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            trace=trace_text,
        )
        raw = self._complete(prompt, system=BIAS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[BiasEvidence] = []
        for entry in data:
            try:
                evidence.append(BiasEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed BiasEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.bias for ev in evidence}
        for bias in BIASES:
            if bias not in seen:
                evidence.append(
                    BiasEvidence(
                        bias=bias,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this bias observed.",
                        evidence_quotes=[],
                    )
                )

        order = {bias: i for i, bias in enumerate(BIASES)}
        evidence.sort(key=lambda e: order.get(e.bias, len(BIASES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: AgentReasoningTrace,
        trace_text: str,
        evidence: list[BiasEvidence],
        dominant: str,
    ) -> list[BiasIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=BIAS_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[BiasIntervention] = []
        for entry in data:
            try:
                interventions.append(BiasIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed BiasIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _build_scores(self, evidence: list[BiasEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {bias: 0.0 for bias in BIASES}
        for ev in evidence:
            scores[ev.bias] = max(scores.get(ev.bias, 0.0), ev.score)
        return scores

    def _dominant_bias(
        self, bias_scores: dict[str, float]
    ) -> Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
        "none-observed",
    ]:
        """Pick the dominant bias.

        Tie-breaking favors lower biases in the BIASES list (anchoring first).
        Anchoring is the foundational bias from which the others compound,
        per the Kahneman/Tversky framework.
        """
        max_score = max(bias_scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for bias in BIASES:
            if bias_scores.get(bias, 0.0) >= max_score - 0.05:
                return bias  # type: ignore[return-value]
        return "none-observed"

    def _reasoning_quality(
        self, bias_scores: dict[str, float]
    ) -> Literal["well-calibrated", "bias-prone", "severely-biased"]:
        max_score = max(bias_scores.values(), default=0.0)
        if max_score > 0.6:
            return "severely-biased"
        if max_score > 0.3:
            return "bias-prone"
        return "well-calibrated"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentReasoningTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        step_lines: list[str] = []
        for i, step in enumerate(trace.steps):
            ts = (
                f"[{step.timestamp.isoformat()}] "
                if step.timestamp is not None
                else f"[step {i + 1}] "
            )
            conf = f" (confidence={step.confidence:.2f})" if step.confidence is not None else ""
            step_lines.append(f"{ts}({step.type}){conf} {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Reasoning trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
