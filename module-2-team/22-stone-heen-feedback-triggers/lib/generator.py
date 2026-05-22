"""FeedbackTriggerDetector: diagnose Stone & Heen's three feedback triggers
(truth, relationship, identity) in a user-agent feedback exchange.

Pipeline:
  1. Validate the trace (non-empty task, outcome, at least one message)
  2. Pass 1: LLM scores all three triggers against the exchange
  3. Identify the dominant trigger (truth wins tie-breaks — it's the most
     common trigger and the one with the cleanest interventions)
  4. Compute the overall feedback-intake-quality label
  5. Pass 2: propose interventions targeting the dominant trigger
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, TRIGGER_SCORING_PROMPT, TRIGGER_SYSTEM_PROMPT
from .schema import (
    TRIGGERS,
    FeedbackInteractionTrace,
    FeedbackTriggerDetection,
    TriggerEvidence,
    TriggerIntervention,
)

log = logging.getLogger("agentcity.feedback_triggers.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class FeedbackTriggerDetector:
    """Run the 3-Trigger diagnostic on a FeedbackInteractionTrace."""

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

    def run(self, trace: FeedbackInteractionTrace) -> FeedbackTriggerDetection:
        self._validate_trace(trace)
        exchange_text = self._serialize_exchange(trace)

        started = time.monotonic()
        log.info(
            "Running 3-Trigger detection for agent %s (messages=%d, incorporated=%s)",
            trace.agent_id or "<unknown>",
            len(trace.messages),
            trace.feedback_incorporated,
        )

        evidence = self._pass_1_scores(trace, exchange_text)
        trigger_scores = self._build_scores(evidence)
        dominant = self._dominant_trigger(trigger_scores)
        interventions = self._pass_2_interventions(trace, exchange_text, evidence, dominant)
        quality = self._intake_quality(trigger_scores, trace.feedback_incorporated)

        detection = FeedbackTriggerDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_trigger=dominant,
            trigger_scores=trigger_scores,
            triggers=evidence,
            interventions=interventions,
            feedback_intake_quality=quality,
            generator_model=self.model,
            feedback_incorporated=trace.feedback_incorporated,
        )

        elapsed = time.monotonic() - started
        log.info(
            "3-Trigger detection for agent %s done in %.2fs "
            "(dominant=%s, quality=%s, interventions=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            quality,
            len(interventions),
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: FeedbackInteractionTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("FeedbackInteractionTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("FeedbackInteractionTrace.outcome cannot be empty.")
        if not trace.messages:
            raise ValueError("FeedbackInteractionTrace.messages cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_scores(
        self, trace: FeedbackInteractionTrace, exchange_text: str
    ) -> list[TriggerEvidence]:
        prompt = TRIGGER_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            feedback_incorporated=trace.feedback_incorporated,
            exchange=exchange_text,
        )
        raw = self._complete(prompt, system=TRIGGER_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[TriggerEvidence] = []
        for entry in data:
            try:
                evidence.append(TriggerEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TriggerEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.trigger for ev in evidence}
        for trigger in TRIGGERS:
            if trigger not in seen:
                evidence.append(
                    TriggerEvidence(
                        trigger=trigger,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this trigger observed.",
                        evidence_quotes=[],
                    )
                )

        order = {trigger: i for i, trigger in enumerate(TRIGGERS)}
        evidence.sort(key=lambda e: order.get(e.trigger, len(TRIGGERS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: FeedbackInteractionTrace,
        exchange_text: str,
        evidence: list[TriggerEvidence],
        dominant: str,
    ) -> list[TriggerIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            exchange=exchange_text,
        )
        raw = self._complete(prompt, system=TRIGGER_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[TriggerIntervention] = []
        for entry in data:
            try:
                interventions.append(TriggerIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TriggerIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _build_scores(self, evidence: list[TriggerEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {trigger: 0.0 for trigger in TRIGGERS}
        for ev in evidence:
            scores[ev.trigger] = max(scores.get(ev.trigger, 0.0), ev.score)
        return scores

    def _dominant_trigger(
        self, trigger_scores: dict[str, float]
    ) -> Literal["truth", "relationship", "identity", "none-observed"]:
        """Pick the dominant trigger.

        Tie-breaking favors lower triggers in the TRIGGERS list (truth first).
        Truth is the most common trigger and the one with the cleanest set
        of interventions, so it's the right default to break ties on.
        """
        max_score = max(trigger_scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for trigger in TRIGGERS:
            if trigger_scores.get(trigger, 0.0) >= max_score - 0.05:
                return trigger  # type: ignore[return-value]
        return "none-observed"

    def _intake_quality(
        self, trigger_scores: dict[str, float], feedback_incorporated: bool
    ) -> Literal["absorbs-feedback", "trigger-prone", "feedback-rejecting"]:
        max_score = max(trigger_scores.values(), default=0.0)
        if not feedback_incorporated and max_score > 0.5:
            return "feedback-rejecting"
        if max_score > 0.3:
            return "trigger-prone"
        return "absorbs-feedback"

    # --- Exchange serialization ----------------------------------------

    def _serialize_exchange(self, trace: FeedbackInteractionTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Feedback incorporated: {trace.feedback_incorporated}",
            "",
        ]
        msg_lines: list[str] = []
        for i, m in enumerate(trace.messages):
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else f"[msg {i + 1}] "
            tag = " (FEEDBACK)" if m.is_feedback and m.source == "user" else ""
            msg_lines.append(f"{ts}{m.source}{tag}: {m.content}")
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Feedback exchange exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... EXCHANGE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
