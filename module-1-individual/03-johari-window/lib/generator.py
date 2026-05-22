"""
JohariSelfAudit: Luft & Ingham's four-quadrant self-awareness model
applied to AI agents.

Pipeline:
  1. Validate the trace (non-empty task, outcome, turns, self-report)
  2. Pass 1: classify trace + self-report content into the four quadrants;
              extract blind-spot and hidden-content registers
  3. Compute the dominant quadrant + self-awareness score
  4. Pass 2: generate interventions targeting the dominant problematic
              quadrant (BLIND, HIDDEN, or UNKNOWN — not OPEN)

Reuses the AAR Generator's LLMClient protocol, retry helper, and JSON
parser — see agentcity.aar._retry and agentcity.aar._json_parsing.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal, Protocol, cast

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    INTERVENTIONS_PROMPT,
    JOHARI_SYSTEM_PROMPT,
    QUADRANT_ANALYSIS_PROMPT,
)
from .schema import (
    QUADRANTS,
    AgentSelfReportTrace,
    JohariIntervention,
    JohariSelfAudit,
    QuadrantContent,
)

log = logging.getLogger("agentcity.johari.generator")


class LLMClient(Protocol):
    """Minimal LLM interface; matches the AAR Generator's LLMClient."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class JohariSelfAuditor:
    """Run the Johari Window Self-Audit on an AgentSelfReportTrace."""

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

    def run(self, trace: AgentSelfReportTrace) -> JohariSelfAudit:
        """Classify quadrants, score self-awareness, propose interventions.

        Raises:
            ValueError: if the trace fails minimal sanity checks.
        """
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Johari Self-Audit for agent %s (turns=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.turns),
            trace.success,
        )

        analysis = self._pass_1_quadrants(trace, trace_text)
        quadrant_weights = self._build_weights(analysis["quadrants"])
        dominant = self._dominant_quadrant(quadrant_weights)
        self_awareness = self._self_awareness_score(quadrant_weights)
        interventions = self._pass_2_interventions(trace, trace_text, analysis, dominant)

        audit = JohariSelfAudit(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_quadrant=dominant,
            quadrant_weights=quadrant_weights,
            quadrants=analysis["quadrants"],
            self_awareness_score=self_awareness,
            blind_spot_register=analysis["blind_spot_register"],
            hidden_content_register=analysis["hidden_content_register"],
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Johari Self-Audit for agent %s done in %.2fs "
            "(dominant=%s, awareness=%.2f, interventions=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            dominant,
            self_awareness,
            len(interventions),
        )
        return audit

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentSelfReportTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentSelfReportTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentSelfReportTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("AgentSelfReportTrace.turns cannot be empty.")
        if not trace.self_report or not trace.self_report.strip():
            raise ValueError(
                "AgentSelfReportTrace.self_report cannot be empty. The Johari "
                "audit compares the agent's self-report against its actual "
                "trace; without a self-report there is no comparison to make."
            )

    # --- LLM-driven passes ---------------------------------------------

    def _pass_1_quadrants(self, trace: AgentSelfReportTrace, trace_text: str) -> dict[str, Any]:
        prompt = QUADRANT_ANALYSIS_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            self_report=trace.self_report,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=JOHARI_SYSTEM_PROMPT).strip()
        data = self._extract_json_object(raw)

        quadrants: list[QuadrantContent] = []
        for entry in data.get("quadrants", []):
            if not isinstance(entry, dict):
                continue
            try:
                quadrants.append(QuadrantContent(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed QuadrantContent (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        # Ensure all four quadrants are represented.
        seen = {qc.quadrant for qc in quadrants}
        for q in QUADRANTS:
            if q not in seen:
                quadrants.append(
                    QuadrantContent(
                        quadrant=q,  # type: ignore[arg-type]
                        weight=0.0,
                        explanation="No content detected in this quadrant.",
                        evidence_quotes=[],
                    )
                )

        order = {q: i for i, q in enumerate(QUADRANTS)}
        quadrants.sort(key=lambda qc: order.get(qc.quadrant, len(QUADRANTS)))

        blind_register_raw = data.get("blind_spot_register", [])
        hidden_register_raw = data.get("hidden_content_register", [])
        blind_register = [str(x) for x in blind_register_raw if isinstance(x, str)]
        hidden_register = [str(x) for x in hidden_register_raw if isinstance(x, str)]

        return {
            "quadrants": quadrants,
            "blind_spot_register": blind_register,
            "hidden_content_register": hidden_register,
        }

    def _pass_2_interventions(
        self,
        trace: AgentSelfReportTrace,
        trace_text: str,
        analysis: dict[str, Any],
        dominant: str,
    ) -> list[JohariIntervention]:
        if dominant == "open":
            # Healthy case: nothing to intervene on.
            return []

        # Reuse the quadrant list for context.
        analysis_text = json.dumps(
            {
                "quadrants": [qc.model_dump() for qc in analysis["quadrants"]],
                "blind_spot_register": analysis["blind_spot_register"],
                "hidden_content_register": analysis["hidden_content_register"],
            },
            indent=2,
            default=str,
        )
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            analysis=analysis_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=JOHARI_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[JohariIntervention] = []
        for entry in data:
            try:
                interventions.append(JohariIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed JohariIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis helpers ---------------------------------------------

    def _build_weights(self, quadrants: list[QuadrantContent]) -> dict[str, float]:
        weights: dict[str, float] = {q: 0.0 for q in QUADRANTS}
        for qc in quadrants:
            weights[qc.quadrant] = max(weights.get(qc.quadrant, 0.0), qc.weight)
        return weights

    def _dominant_quadrant(
        self, weights: dict[str, float]
    ) -> Literal["open", "blind", "hidden", "unknown"]:
        """Pick the quadrant with the largest weight.

        Tie-breaking favors quadrants in this order: BLIND (most actionable),
        HIDDEN, UNKNOWN, OPEN — diagnostically, BLIND is the most urgent
        finding because the agent doesn't know what it did.
        """
        tiebreak_order = ("blind", "hidden", "unknown", "open")
        max_score = max(weights.values(), default=0.0)
        for q in tiebreak_order:
            if weights.get(q, 0.0) >= max_score - 0.05:
                return cast(
                    Literal["open", "blind", "hidden", "unknown"],
                    q,
                )
        return "open"

    def _self_awareness_score(self, weights: dict[str, float]) -> float:
        """Compute self-awareness in [0.0, 1.0].

        Higher OPEN + HIDDEN (deliberate withholding is OK in moderation),
        lower BLIND + UNKNOWN (the agent doesn't know what it doesn't know).
        Simple weighted blend.
        """
        open_w = weights.get("open", 0.0)
        hidden_w = weights.get("hidden", 0.0)
        blind_w = weights.get("blind", 0.0)
        unknown_w = weights.get("unknown", 0.0)
        # Treat HIDDEN as half-credit; deliberate withholding is acceptable
        # but agents should still surface uncertainty when it matters.
        positive = open_w + 0.5 * hidden_w
        negative = blind_w + 0.3 * unknown_w
        denom = positive + negative
        if denom == 0.0:
            return 0.5
        return round(max(0.0, min(1.0, positive / denom)), 2)

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: AgentSelfReportTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
            "Self-report (the agent's own words):",
            trace.self_report,
            "",
            "Trace (turns):",
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
            "Self-report trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        """Best-effort JSON-object extraction (vs. array) from an LLM response.

        Handles markdown fences, prose wrappers, and naked objects.
        """
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)

        # Find markdown fenced blocks
        import re

        for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE):
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

        log.warning(
            "Failed to parse JSON object from Johari LLM response (len=%d)",
            len(text),
        )
        return {"quadrants": [], "blind_spot_register": [], "hidden_content_register": []}
