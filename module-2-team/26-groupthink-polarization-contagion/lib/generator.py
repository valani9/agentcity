"""DebatePathologyDetector: diagnose groupthink, polarization, and
emotional contagion in a multi-agent debate trace.

Pipeline:
  1. Validate the trace (>=2 agents, >=2 messages, non-empty task + final_decision)
  2. Pass 1: LLM scores all three pathologies against the debate
  3. Identify the dominant pathology (groupthink wins tie-breaks — it's the
     pathology with the cleanest, most-replicated intervention literature)
  4. Detect the convergence round heuristically from positions
  5. Compute the debate-quality label
  6. Pass 2: propose interventions targeting the dominant pathology
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    DEBATE_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,
    PATHOLOGY_SCORING_PROMPT,
)
from .schema import (
    PATHOLOGIES,
    DebateIntervention,
    DebatePathologyDetection,
    MultiAgentDebateTrace,
    PathologyEvidence,
)

log = logging.getLogger("agentcity.debate_pathology.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class DebatePathologyDetector:
    """Run the Groupthink/Polarization/Contagion diagnostic on a debate trace."""

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

    def run(self, trace: MultiAgentDebateTrace) -> DebatePathologyDetection:
        self._validate_trace(trace)
        debate_text = self._serialize_debate(trace)

        started = time.monotonic()
        log.info(
            "Running Debate-Pathology detection for debate %s (agents=%d, messages=%d)",
            trace.debate_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
        )

        evidence = self._pass_1_pathologies(trace, debate_text)
        scores = self._build_scores(evidence)
        dominant = self._dominant_pathology(scores)
        convergence = self._convergence_round(trace)
        quality = self._debate_quality(scores)
        interventions = self._pass_2_interventions(trace, debate_text, evidence, dominant, quality)

        detection = DebatePathologyDetection(
            debate_id=trace.debate_id,
            dominant_pathology=dominant,
            pathology_scores=scores,
            pathologies=evidence,
            debate_quality=quality,
            convergence_round=convergence,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Debate-Pathology detection for debate %s done in %.2fs "
            "(dominant=%s, quality=%s, convergence_round=%s)",
            trace.debate_id or "<unknown>",
            elapsed,
            dominant,
            quality,
            convergence,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: MultiAgentDebateTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("MultiAgentDebateTrace.task cannot be empty.")
        if not trace.final_decision or not trace.final_decision.strip():
            raise ValueError("MultiAgentDebateTrace.final_decision cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentDebateTrace.agents must contain at least 2 agents.")
        if len(trace.messages) < 2:
            raise ValueError("MultiAgentDebateTrace.messages must contain at least 2 messages.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_pathologies(
        self, trace: MultiAgentDebateTrace, debate_text: str
    ) -> list[PathologyEvidence]:
        prompt = PATHOLOGY_SCORING_PROMPT.format(
            task=trace.task,
            agents=", ".join(trace.agents),
            final_decision=trace.final_decision,
            outcome=trace.outcome,
            success=trace.success,
            debate=debate_text,
        )
        raw = self._complete(prompt, system=DEBATE_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[PathologyEvidence] = []
        for entry in data:
            try:
                evidence.append(PathologyEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed PathologyEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.pathology for ev in evidence}
        for p in PATHOLOGIES:
            if p not in seen:
                evidence.append(
                    PathologyEvidence(
                        pathology=p,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this pathology observed.",
                        evidence_quotes=[],
                    )
                )

        order = {p: i for i, p in enumerate(PATHOLOGIES)}
        evidence.sort(key=lambda e: order.get(e.pathology, len(PATHOLOGIES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: MultiAgentDebateTrace,
        debate_text: str,
        evidence: list[PathologyEvidence],
        dominant: str,
        quality: str,
    ) -> list[DebateIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            quality=quality,
            evidence=evidence_text,
            debate=debate_text,
        )
        raw = self._complete(prompt, system=DEBATE_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[DebateIntervention] = []
        for entry in data:
            try:
                interventions.append(DebateIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DebateIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _build_scores(self, evidence: list[PathologyEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {p: 0.0 for p in PATHOLOGIES}
        for ev in evidence:
            scores[ev.pathology] = max(scores.get(ev.pathology, 0.0), ev.score)
        return scores

    def _dominant_pathology(
        self, scores: dict[str, float]
    ) -> Literal["groupthink", "polarization", "contagion", "none-observed"]:
        """Pick the dominant pathology.

        Tie-breaking favors `groupthink` — it has the cleanest, most replicated
        intervention literature, and is the most common dynamic.
        """
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for p in PATHOLOGIES:
            if scores.get(p, 0.0) >= max_score - 0.05:
                return p  # type: ignore[return-value]
        return "none-observed"

    def _debate_quality(
        self, scores: dict[str, float]
    ) -> Literal["healthy", "at-risk", "pathological"]:
        max_score = max(scores.values(), default=0.0)
        if max_score > 0.6:
            return "pathological"
        if max_score > 0.3:
            return "at-risk"
        return "healthy"

    def _convergence_round(self, trace: MultiAgentDebateTrace) -> int | None:
        """Heuristic: the round in which all agents share the same `position` value.

        Returns None if positions never converge (or are unspecified).
        """
        by_round: dict[int, dict[str, str]] = {}
        for m in trace.messages:
            round_positions = by_round.setdefault(m.round, {})
            if m.position.strip():
                round_positions[m.from_agent] = m.position.strip().lower()

        for round_num in sorted(by_round.keys()):
            agents_in_round = by_round[round_num]
            if len(agents_in_round) < 2:
                continue
            positions = set(agents_in_round.values())
            if len(positions) == 1:
                return round_num
        return None

    # --- Debate serialization ------------------------------------------

    def _serialize_debate(self, trace: MultiAgentDebateTrace) -> str:
        header = [
            f"Task being debated: {trace.task}",
            f"Agents: {', '.join(trace.agents)}",
            f"Final decision: {trace.final_decision}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        msg_lines: list[str] = []
        for m in trace.messages:
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else ""
            pos = f" position='{m.position}'" if m.position else ""
            tone = f" tone={m.emotional_tone}" if m.emotional_tone != "unknown" else ""
            msg_lines.append(f"{ts}[round {m.round}] {m.from_agent}{pos}{tone}: {m.content}")
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Debate trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... DEBATE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
