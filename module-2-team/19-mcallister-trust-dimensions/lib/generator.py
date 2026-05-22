"""TrustBalanceDetector: diagnose McAllister's two trust dimensions
(cognitive and affective) in a user-agent conversation.

Pipeline:
  1. Validate the trace (non-empty task, outcome, at least one turn)
  2. Pass 1: LLM scores both dimensions against the conversation
  3. Compute the trust-balance (cognitive_score - affective_score)
  4. Determine the dominant dimension and overall trust-quality bucket
  5. Pass 2: propose interventions for the under-built dimension
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import DIMENSION_SCORING_PROMPT, INTERVENTIONS_PROMPT, TRUST_SYSTEM_PROMPT
from .schema import (
    TRUST_DIMENSIONS,
    TrustBalanceDetection,
    TrustConversationTrace,
    TrustDimensionEvidence,
    TrustIntervention,
)

log = logging.getLogger("agentcity.mcallister_trust.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class TrustBalanceDetector:
    """Run the Cognitive/Affective Trust diagnostic on a TrustConversationTrace."""

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

    def run(self, trace: TrustConversationTrace) -> TrustBalanceDetection:
        self._validate_trace(trace)
        conversation_text = self._serialize_conversation(trace)

        started = time.monotonic()
        log.info(
            "Running Trust-Dimensions detection for agent %s (turns=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.turns),
            trace.success,
        )

        evidence = self._pass_1_dimensions(trace, conversation_text)
        scores = self._build_scores(evidence)
        balance = round(scores.get("cognitive", 0.0) - scores.get("affective", 0.0), 2)
        dominant = self._dominant_dimension(scores)
        quality = self._trust_quality(scores)
        interventions = self._pass_2_interventions(
            trace, conversation_text, evidence, scores, quality
        )

        detection = TrustBalanceDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_dimension=dominant,
            dimension_scores=scores,
            dimensions=evidence,
            trust_balance=balance,
            trust_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Trust-Dimensions detection for agent %s done in %.2fs "
            "(dominant=%s, quality=%s, balance=%.2f)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            quality,
            balance,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: TrustConversationTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("TrustConversationTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("TrustConversationTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("TrustConversationTrace.turns cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_dimensions(
        self, trace: TrustConversationTrace, conversation_text: str
    ) -> list[TrustDimensionEvidence]:
        prompt = DIMENSION_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            user_satisfaction=(
                f"{trace.user_satisfaction:.2f}"
                if trace.user_satisfaction is not None
                else "(not measured)"
            ),
            conversation=conversation_text,
        )
        raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[TrustDimensionEvidence] = []
        for entry in data:
            try:
                evidence.append(TrustDimensionEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TrustDimensionEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.dimension for ev in evidence}
        for dim in TRUST_DIMENSIONS:
            if dim not in seen:
                evidence.append(
                    TrustDimensionEvidence(
                        dimension=dim,  # type: ignore[arg-type]
                        score=0.0,
                        severity_of_gap="high",
                        explanation="No evidence of this dimension built in the conversation.",
                        evidence_quotes=[],
                    )
                )

        order = {dim: i for i, dim in enumerate(TRUST_DIMENSIONS)}
        evidence.sort(key=lambda e: order.get(e.dimension, len(TRUST_DIMENSIONS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: TrustConversationTrace,
        conversation_text: str,
        evidence: list[TrustDimensionEvidence],
        scores: dict[str, float],
        quality: str,
    ) -> list[TrustIntervention]:
        if quality == "balanced-trust":
            return []
        # Target the lower-scoring dimension (or both if low-trust)
        target = min(scores, key=lambda d: scores[d])
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            target_dimension=target,
            trust_quality=quality,
            evidence=evidence_text,
            conversation=conversation_text,
        )
        raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[TrustIntervention] = []
        for entry in data:
            try:
                interventions.append(TrustIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TrustIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _build_scores(self, evidence: list[TrustDimensionEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {dim: 0.0 for dim in TRUST_DIMENSIONS}
        for ev in evidence:
            scores[ev.dimension] = max(scores.get(ev.dimension, 0.0), ev.score)
        return scores

    def _dominant_dimension(
        self, scores: dict[str, float]
    ) -> Literal["cognitive", "affective", "balanced", "neither"]:
        cog = scores.get("cognitive", 0.0)
        aff = scores.get("affective", 0.0)
        if cog < 0.2 and aff < 0.2:
            return "neither"
        if abs(cog - aff) < 0.1:
            return "balanced"
        return "cognitive" if cog > aff else "affective"

    def _trust_quality(
        self, scores: dict[str, float]
    ) -> Literal[
        "balanced-trust",
        "cognitive-only",
        "warm-but-incompetent",
        "low-trust",
    ]:
        cog = scores.get("cognitive", 0.0)
        aff = scores.get("affective", 0.0)
        if cog < 0.3 and aff < 0.3:
            return "low-trust"
        if cog >= 0.5 and aff >= 0.5:
            return "balanced-trust"
        if cog >= 0.5 and aff < 0.3:
            return "cognitive-only"
        if aff >= 0.5 and cog < 0.3:
            return "warm-but-incompetent"
        # Mixed/partial cases: classify by the stronger axis.
        if cog >= aff:
            return "cognitive-only"
        return "warm-but-incompetent"

    # --- Conversation serialization ------------------------------------

    def _serialize_conversation(self, trace: TrustConversationTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        turn_lines: list[str] = []
        for i, turn in enumerate(trace.turns):
            ts = (
                f"[{turn.timestamp.isoformat()}] "
                if turn.timestamp is not None
                else f"[turn {i + 1}] "
            )
            turn_lines.append(f"{ts}{turn.role}: {turn.content}")
        full = "\n".join(header + turn_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Trust conversation exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... CONVERSATION TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
