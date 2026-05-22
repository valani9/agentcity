"""PsychologicalSafetyDetector — Edmondson's psychological safety
construct applied to multi-agent AI systems.

Pipeline:
  1. Validate trace (≥2 agents, ≥1 message, non-empty goal+outcome)
  2. Pass 1: LLM scores the four observable safety behaviors + extracts
     a register of blocking behaviors observed in the trace
  3. Compute overall safety score (weighted blend of the four behavior
     presence scores) and team-climate label
  4. Pass 2: propose interventions for the lowest-presence behavior
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._retry import with_retry

from .prompts import (
    BEHAVIOR_SCORING_PROMPT,
    INTERVENTIONS_PROMPT,
    SAFETY_SYSTEM_PROMPT,
)
from .schema import (
    BEHAVIORS,
    BehaviorEvidence,
    MultiAgentSafetyTrace,
    PsychologicalSafetyDetection,
    SafetyIntervention,
)

log = logging.getLogger("agentcity.psych_safety.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class PsychologicalSafetyDetector:
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

    def run(self, trace: MultiAgentSafetyTrace) -> PsychologicalSafetyDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Psychological Safety detection for team %s (agents=%d, messages=%d)",
            trace.team_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
        )

        analysis = self._pass_1_behaviors(trace, trace_text)
        behavior_scores = self._build_behavior_scores(analysis["behaviors"])
        lowest = self._lowest_presence(behavior_scores)
        interventions = self._pass_2_interventions(trace, trace_text, analysis["behaviors"], lowest)

        safety_score = self._safety_score(behavior_scores)
        climate = self._climate(safety_score)

        detection = PsychologicalSafetyDetection(
            team_id=trace.team_id,
            safety_score=safety_score,
            team_climate=climate,
            behavior_scores=behavior_scores,
            behaviors=analysis["behaviors"],
            blocking_behaviors=analysis["blocking_behaviors"],
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Psychological Safety detection for team %s done in %.2fs (safety=%.2f, climate=%s)",
            trace.team_id or "<unknown>",
            elapsed,
            safety_score,
            climate,
        )
        return detection

    def _validate_trace(self, trace: MultiAgentSafetyTrace) -> None:
        if not trace.goal or not trace.goal.strip():
            raise ValueError("MultiAgentSafetyTrace.goal cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentSafetyTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentSafetyTrace.agents must contain at least 2 agents.")
        if not trace.messages:
            raise ValueError("MultiAgentSafetyTrace.messages cannot be empty.")

    def _pass_1_behaviors(self, trace: MultiAgentSafetyTrace, trace_text: str) -> dict[str, Any]:
        prompt = BEHAVIOR_SCORING_PROMPT.format(
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            trace=trace_text,
        )
        raw = self._complete(prompt, system=SAFETY_SYSTEM_PROMPT).strip()
        data = self._extract_json_object(raw)

        behaviors: list[BehaviorEvidence] = []
        for entry in data.get("behaviors", []):
            if not isinstance(entry, dict):
                continue
            try:
                behaviors.append(BehaviorEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed BehaviorEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.behavior for ev in behaviors}
        for b in BEHAVIORS:
            if b not in seen:
                behaviors.append(
                    BehaviorEvidence(
                        behavior=b,  # type: ignore[arg-type]
                        presence_score=0.0,
                        severity_of_absence="high",
                        explanation="No evidence of this behavior in the trace.",
                        evidence_quotes=[],
                    )
                )

        order = {b: i for i, b in enumerate(BEHAVIORS)}
        behaviors.sort(key=lambda e: order.get(e.behavior, len(BEHAVIORS)))

        blocking_raw = data.get("blocking_behaviors", [])
        blocking = [str(x) for x in blocking_raw if isinstance(x, str)]

        return {"behaviors": behaviors, "blocking_behaviors": blocking}

    def _pass_2_interventions(
        self,
        trace: MultiAgentSafetyTrace,
        trace_text: str,
        behaviors: list[BehaviorEvidence],
        lowest: str,
    ) -> list[SafetyIntervention]:
        evidence_text = json.dumps([b.model_dump() for b in behaviors], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            lowest_behavior=lowest,
            evidence=evidence_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=SAFETY_SYSTEM_PROMPT).strip()
        data = self._extract_json_array(raw)

        interventions: list[SafetyIntervention] = []
        for entry in data:
            try:
                interventions.append(SafetyIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SafetyIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _build_behavior_scores(self, behaviors: list[BehaviorEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {b: 0.0 for b in BEHAVIORS}
        for ev in behaviors:
            scores[ev.behavior] = max(scores.get(ev.behavior, 0.0), ev.presence_score)
        return scores

    def _lowest_presence(self, scores: dict[str, float]) -> str:
        if not scores:
            return "voice"
        return min(scores, key=lambda b: scores[b])

    def _safety_score(self, scores: dict[str, float]) -> float:
        """Weighted average across the four behaviors."""
        if not scores:
            return 0.0
        return round(sum(scores.values()) / len(scores), 2)

    def _climate(self, safety_score: float) -> Literal["safe", "cautious", "silenced"]:
        if safety_score >= 0.65:
            return "safe"
        if safety_score >= 0.35:
            return "cautious"
        return "silenced"

    def _serialize_trace(self, trace: MultiAgentSafetyTrace) -> str:
        header = [
            f"Goal: {trace.goal}",
            f"Agents: {', '.join(trace.agents)}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        msg_lines = []
        for i, m in enumerate(trace.messages):
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else f"[msg {i + 1}] "
            msg_lines.append(
                f"{ts}({m.message_type}) {m.from_agent} → {m.to_agent or 'TEAM'}: {m.content}"
            )
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning("Safety trace exceeds max_trace_chars; truncating")
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRUNCATED ({len(full) - self.max_trace_chars} chars) ...]\n\n"
            + full[-keep:]
        )

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
        for match in _FENCE_RE.finditer(text):
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
        return {"behaviors": [], "blocking_behaviors": []}

    @staticmethod
    def _extract_json_array(text: str) -> list[dict[str, Any]]:
        from agentcity.aar._json_parsing import extract_json_array

        result: list[dict[str, Any]] = extract_json_array(text)
        return result
