"""
TrustTriangleAudit: diagnoses an agent's wobble across the three legs of
trust (Logic, Authenticity, Empathy) per Frei & Morriss 2020.

Pipeline:
  1. Validate the interaction trace
  2. Pass 1: score all three legs from the trace
  3. Identify the dominant wobble (highest score; "none-observed" if all low)
  4. Compute an overall trust level from the score distribution
  5. Pass 2: generate interventions targeting the dominant wobble

Reuses the AAR Generator's LLMClient protocol, retry helper, and JSON
parser — see agentcity.aar._retry and agentcity.aar._json_parsing.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    INTERVENTIONS_PROMPT,
    LEG_SCORE_PROMPT,
    TRUST_SYSTEM_PROMPT,
)
from .schema import (
    LEGS,
    AgentInteractionTrace,
    LegEvidence,
    TrustIntervention,
    TrustTriangleAudit,
)

log = logging.getLogger("agentcity.trust_triangle.generator")


class LLMClient(Protocol):
    """Minimal LLM interface; matches the AAR Generator's LLMClient."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class TrustTriangleAuditor:
    """Run the Trust Triangle Audit against an AgentInteractionTrace."""

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

    def run(self, trace: AgentInteractionTrace) -> TrustTriangleAudit:
        """Score the triangle, identify the dominant wobble, propose interventions.

        Raises:
            ValueError: if the trace fails minimal sanity checks
                (empty task, empty outcome, empty turns).
        """
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Trust Triangle Audit for agent %s (turns=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.turns),
            trace.success,
        )

        evidence = self._pass_1_leg_scores(trace, trace_text)
        leg_scores = self._build_leg_scores(evidence)
        dominant = self._dominant_wobble(leg_scores)
        interventions = self._pass_2_interventions(trace, trace_text, evidence, dominant)
        trust_level = self._trust_level(leg_scores)

        audit = TrustTriangleAudit(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_wobble=dominant,
            leg_scores=leg_scores,
            legs=evidence,
            interventions=interventions,
            overall_trust_level=trust_level,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Trust Triangle Audit for agent %s done in %.2fs "
            "(dominant=%s, trust_level=%s, interventions=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            trust_level,
            len(interventions),
        )
        return audit

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentInteractionTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentInteractionTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentInteractionTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError(
                "AgentInteractionTrace.turns cannot be empty. Trust is "
                "observable only through the agent's actual utterances."
            )

    # --- LLM-driven passes ---------------------------------------------

    def _pass_1_leg_scores(
        self, trace: AgentInteractionTrace, trace_text: str
    ) -> list[LegEvidence]:
        satisfaction = (
            f"{trace.user_satisfaction:.2f}"
            if trace.user_satisfaction is not None
            else "not reported"
        )
        prompt = LEG_SCORE_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            satisfaction=satisfaction,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[LegEvidence] = []
        for entry in data:
            try:
                evidence.append(LegEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LegEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        # Ensure all three legs are present; fill missing with zero wobble.
        seen = {ev.leg for ev in evidence}
        for leg in LEGS:
            if leg not in seen:
                evidence.append(
                    LegEvidence(
                        leg=leg,  # type: ignore[arg-type]
                        wobble_score=0.0,
                        severity="none",
                        explanation="No wobble detected on this leg.",
                        evidence_quotes=[],
                    )
                )

        order = {leg: i for i, leg in enumerate(LEGS)}
        evidence.sort(key=lambda e: order.get(e.leg, len(LEGS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        evidence: list[LegEvidence],
        dominant: str,
    ) -> list[TrustIntervention]:
        if dominant == "none-observed":
            return []

        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            trace=trace_text,
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

    # --- Synthesis helpers ---------------------------------------------

    def _build_leg_scores(self, evidence: list[LegEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {leg: 0.0 for leg in LEGS}
        for ev in evidence:
            scores[ev.leg] = max(scores.get(ev.leg, 0.0), ev.wobble_score)
        return scores

    def _dominant_wobble(
        self, leg_scores: dict[str, float]
    ) -> Literal["logic", "authenticity", "empathy", "none-observed"]:
        """Pick the leg with the highest wobble.

        Tie-breaking favors Logic > Authenticity > Empathy — Frei & Morriss
        argue Logic is the most concrete to repair, so it's the first leg
        to flag when scores are close.
        """
        max_score = max(leg_scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for leg in LEGS:
            if leg_scores.get(leg, 0.0) >= max_score - 0.05:
                return leg  # type: ignore[return-value]
        return "none-observed"

    def _trust_level(
        self, leg_scores: dict[str, float]
    ) -> Literal["high-trust", "moderate-trust", "low-trust"]:
        """Coarse trust-level label from the wobble distribution."""
        max_score = max(leg_scores.values(), default=0.0)
        if max_score > 0.6:
            return "low-trust"
        if max_score > 0.3:
            return "moderate-trust"
        return "high-trust"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentInteractionTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        turn_lines = []
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
            "Interaction trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
