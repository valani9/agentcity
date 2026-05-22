"""
LencioniDiagnostic: runs Patrick Lencioni's Five Dysfunctions framework
against a multi-agent system trace and produces a structured diagnosis
plus concrete interventions.

Pipeline:
  1. Validate the trace (non-empty goal, at least 2 agents, at least one message)
  2. Score the pyramid: LLM scores all five dysfunctions for the trace
  3. Identify the dominant dysfunction (highest score; pyramid order breaks ties)
  4. Compute overall team health from the score distribution
  5. Generate interventions targeting the dominant dysfunction first

The generator reuses the AAR Generator's LLMClient protocol — anything
that exposes `complete(prompt, system) -> str` works. Anthropic, OpenAI,
Ollama, and Stub adapters live in `agentcity.aar.clients`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

# Reuse the same robust JSON parsing + retry helpers as the AAR Generator.
# Both patterns ship in the same package so cross-pattern imports are safe.
from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    INTERVENTIONS_PROMPT,
    LENCIONI_SYSTEM_PROMPT,
    PYRAMID_SCORE_PROMPT,
)
from .schema import (
    DYSFUNCTIONS,
    DysfunctionEvidence,
    Intervention,
    LencioniDiagnosis,
    MultiAgentTrace,
)

log = logging.getLogger("agentcity.lencioni.generator")


class LLMClient(Protocol):
    """Minimal LLM interface; matches the AAR Generator's LLMClient."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class LencioniDiagnostic:
    """Diagnose multi-agent system failures via Lencioni's Five Dysfunctions."""

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

    def run(self, trace: MultiAgentTrace) -> LencioniDiagnosis:
        """Score the pyramid, identify the dominant dysfunction, and propose
        interventions.

        Raises:
            ValueError: if the trace fails minimal sanity checks
                (empty goal, fewer than 2 agents, no messages). LLM-side
                errors retry internally and surface only on full exhaustion.
        """
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Lencioni diagnostic for team %s (agents=%d, messages=%d, success=%s)",
            trace.team_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
            trace.success,
        )

        evidence = self._pass_1_pyramid_score(trace, trace_text)
        pyramid_score = self._build_pyramid_score(evidence)
        dominant = self._dominant_dysfunction(pyramid_score)
        interventions = self._pass_2_interventions(trace, trace_text, evidence, dominant)
        team_health = self._team_health(pyramid_score)

        diagnosis = LencioniDiagnosis(
            team_id=trace.team_id,
            dominant_dysfunction=dominant,
            pyramid_score=pyramid_score,
            dysfunctions=evidence,
            interventions=interventions,
            overall_team_health=team_health,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Lencioni diagnostic for team %s done in %.2fs (dominant=%s, health=%s, interventions=%d)",
            trace.team_id or "<unknown>",
            elapsed,
            dominant,
            team_health,
            len(interventions),
        )
        return diagnosis

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: MultiAgentTrace) -> None:
        if not trace.goal or not trace.goal.strip():
            raise ValueError(
                "MultiAgentTrace.goal cannot be empty. The diagnostic "
                "compares team behavior against the stated goal."
            )
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError(
                "MultiAgentTrace.agents must contain at least 2 agents. "
                "Lencioni's framework describes team dynamics; for single-"
                "agent failures, use pattern #30 (AAR Generator) instead."
            )
        if not trace.messages:
            raise ValueError(
                "MultiAgentTrace.messages cannot be empty. Without inter-"
                "agent messages the diagnostic has no evidence to ground in."
            )

    # --- LLM-driven passes ---------------------------------------------

    def _pass_1_pyramid_score(
        self, trace: MultiAgentTrace, trace_text: str
    ) -> list[DysfunctionEvidence]:
        prompt = PYRAMID_SCORE_PROMPT.format(
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LENCIONI_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[DysfunctionEvidence] = []
        for entry in data:
            try:
                evidence.append(DysfunctionEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DysfunctionEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        # Ensure all five canonical dysfunctions are represented; fill
        # missing ones with zero-severity entries so the pyramid is always
        # complete in the output.
        seen = {ev.dysfunction for ev in evidence}
        for d in DYSFUNCTIONS:
            if d not in seen:
                evidence.append(
                    DysfunctionEvidence(
                        dysfunction=d,  # type: ignore[arg-type]
                        severity="none",
                        score=0.0,
                        explanation="No evidence of this dysfunction observed in the trace.",
                        evidence_quotes=[],
                    )
                )

        # Sort into pyramid order (foundation first).
        order = {d: i for i, d in enumerate(DYSFUNCTIONS)}
        evidence.sort(key=lambda e: order.get(e.dysfunction, len(DYSFUNCTIONS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: MultiAgentTrace,
        trace_text: str,
        evidence: list[DysfunctionEvidence],
        dominant: str,
    ) -> list[Intervention]:
        if dominant == "none-observed":
            return []

        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LENCIONI_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[Intervention] = []
        for entry in data:
            try:
                interventions.append(Intervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed Intervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis helpers ---------------------------------------------

    def _build_pyramid_score(self, evidence: list[DysfunctionEvidence]) -> dict[str, float]:
        """Build a {dysfunction: score} dict in canonical pyramid order."""
        scores: dict[str, float] = {d: 0.0 for d in DYSFUNCTIONS}
        for ev in evidence:
            scores[ev.dysfunction] = max(scores.get(ev.dysfunction, 0.0), ev.score)
        return scores

    def _dominant_dysfunction(
        self, pyramid_score: dict[str, float]
    ) -> Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
        "none-observed",
    ]:
        """Pick the dominant dysfunction.

        Tie-breaking favors *lower* dysfunctions in the pyramid (the
        foundation) — per Lencioni, a higher dysfunction cannot be the
        true bottleneck if a lower one is also present at similar severity.
        """
        max_score = max(pyramid_score.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        # Iterate in pyramid order; first dysfunction at the maximum wins.
        for d in DYSFUNCTIONS:
            if pyramid_score.get(d, 0.0) >= max_score - 0.05:
                return d  # type: ignore[return-value]
        return "none-observed"

    def _team_health(
        self, pyramid_score: dict[str, float]
    ) -> Literal["healthy", "stressed", "dysfunctional"]:
        """Coarse health label from the score distribution.

        - healthy:        all dysfunctions <= 0.3
        - stressed:       at least one dysfunction in [0.3, 0.6]
        - dysfunctional:  at least one dysfunction > 0.6
        """
        max_score = max(pyramid_score.values(), default=0.0)
        if max_score > 0.6:
            return "dysfunctional"
        if max_score > 0.3:
            return "stressed"
        return "healthy"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: MultiAgentTrace) -> str:
        header = [
            f"Goal: {trace.goal}",
            f"Agents: {', '.join(trace.agents)}",
            f"Outcome: {trace.outcome}",
            "",
        ]
        msg_lines = [
            f"[{m.timestamp.isoformat()}] ({m.message_type}) "
            f"{m.from_agent} → {m.to_agent or 'TEAM'}: {m.content}"
            for m in trace.messages
        ]
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full

        log.warning(
            "Multi-agent trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
