"""LewinAttributionDetector: diagnose Kurt Lewin's B = f(I, E) locus
(internal / environmental / interactional) for an agent failure trace.

Pipeline:
  1. Validate the trace (non-empty task, outcome, at least one step)
  2. Pass 1: LLM scores all three loci against the trace + factors
  3. Identify the dominant locus (environmental wins tie-breaks — the
     bias to correct is over-attribution to the model)
  4. Compute the attribution-quality label
  5. Check whether the diagnostic agrees with any initial attribution
  6. Pass 2: propose interventions targeting the dominant locus
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, LEWIN_SYSTEM_PROMPT, LOCUS_SCORING_PROMPT
from .schema import (
    LOCI,
    AgentFailureTrace,
    LewinDetection,
    LewinIntervention,
    LocusEvidence,
)

log = logging.getLogger("agentcity.lewin.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class LewinAttributionDetector:
    """Run the Lewin B = f(I, E) diagnostic on an AgentFailureTrace."""

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

    def run(self, trace: AgentFailureTrace) -> LewinDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Lewin diagnostic for agent %s (steps=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.steps),
            trace.success,
        )

        evidence = self._pass_1_loci(trace, trace_text)
        locus_scores = self._build_scores(evidence)
        dominant = self._dominant_locus(locus_scores)
        interventions = self._pass_2_interventions(trace, trace_text, evidence, dominant)
        quality = self._attribution_quality(locus_scores)
        initial_correct = self._check_initial_attribution(trace, dominant)

        detection = LewinDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_locus=dominant,
            locus_scores=locus_scores,
            loci=evidence,
            interventions=interventions,
            attribution_quality=quality,
            initial_attribution_correct=initial_correct,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Lewin diagnostic for agent %s done in %.2fs (dominant=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentFailureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentFailureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentFailureTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("AgentFailureTrace.steps cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_loci(self, trace: AgentFailureTrace, trace_text: str) -> list[LocusEvidence]:
        prompt = LOCUS_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            initial_attribution=trace.initial_attribution or "(none provided)",
            individual_factors=json.dumps(
                [f.model_dump() for f in trace.individual_factors], indent=2, default=str
            ),
            environmental_factors=json.dumps(
                [f.model_dump() for f in trace.environmental_factors],
                indent=2,
                default=str,
            ),
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LEWIN_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[LocusEvidence] = []
        for entry in data:
            try:
                evidence.append(LocusEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LocusEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.locus for ev in evidence}
        for locus in LOCI:
            if locus not in seen:
                evidence.append(
                    LocusEvidence(
                        locus=locus,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this locus observed.",
                        evidence_quotes=[],
                    )
                )

        order = {locus: i for i, locus in enumerate(LOCI)}
        evidence.sort(key=lambda e: order.get(e.locus, len(LOCI)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        evidence: list[LocusEvidence],
        dominant: str,
    ) -> list[LewinIntervention]:
        if dominant == "indeterminate":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LEWIN_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[LewinIntervention] = []
        for entry in data:
            try:
                interventions.append(LewinIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LewinIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _build_scores(self, evidence: list[LocusEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {locus: 0.0 for locus in LOCI}
        for ev in evidence:
            scores[ev.locus] = max(scores.get(ev.locus, 0.0), ev.score)
        return scores

    def _dominant_locus(
        self, locus_scores: dict[str, float]
    ) -> Literal["internal", "environmental", "interactional", "indeterminate"]:
        """Pick the dominant locus.

        Tie-breaking favors `environmental` over `internal` — the systematic
        bias to correct is over-attribution to "the model is bad" when the
        actual cause is something fixable in scaffolding.
        """
        max_score = max(locus_scores.values(), default=0.0)
        if max_score < 0.2:
            return "indeterminate"
        # Tie-break order: environmental, interactional, internal
        ordered = ("environmental", "interactional", "internal")
        for locus in ordered:
            if locus_scores.get(locus, 0.0) >= max_score - 0.05:
                return locus  # type: ignore[return-value]
        return "indeterminate"

    def _attribution_quality(
        self, locus_scores: dict[str, float]
    ) -> Literal["well-attributed", "ambiguous", "miscalibrated"]:
        sorted_scores = sorted(locus_scores.values(), reverse=True)
        if not sorted_scores:
            return "miscalibrated"
        top = sorted_scores[0]
        second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        gap = top - second
        if top < 0.3:
            return "miscalibrated"
        if gap >= 0.3:
            return "well-attributed"
        return "ambiguous"

    def _check_initial_attribution(self, trace: AgentFailureTrace, dominant: str) -> bool | None:
        if not trace.initial_attribution:
            return None
        initial = trace.initial_attribution.strip().lower()
        if initial in LOCI:
            return initial == dominant
        # Look for keywords if the team's attribution is freeform.
        if "model" in initial or "training" in initial or "rlhf" in initial:
            return dominant == "internal"
        if (
            "prompt" in initial
            or "context" in initial
            or "tool" in initial
            or "rag" in initial
            or "orchestrat" in initial
            or "scaffold" in initial
        ):
            return dominant == "environmental"
        if "both" in initial or "interaction" in initial:
            return dominant == "interactional"
        return None

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentFailureTrace) -> str:
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
            step_lines.append(f"{ts}({step.type}) {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Failure trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
