"""SMARTGoalGenerator: take a vague task description and generate a
structured Doran-style SMART goal spec.

Pipeline:
  1. Validate the request (non-empty vague_goal)
  2. Single LLM pass to generate the full SMART spec as JSON
  3. Parse and post-process: fill missing criteria, recompute overall_smart_score
     if the LLM returned an obviously-wrong number, and reconcile the quality
     bucket with the score.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._retry import with_retry

from .prompts import SMART_GENERATION_PROMPT, SMART_SYSTEM_PROMPT
from .schema import (
    SMART_CRITERIA,
    GoalRequest,
    KillCriterion,
    SMARTCriterion,
    SMARTGoal,
    SuccessMetric,
)

log = logging.getLogger("agentcity.smart_goal.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class SMARTGoalGenerator:
    """Generate a SMART goal spec from a vague task description."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(self, request: GoalRequest) -> SMARTGoal:
        self._validate_request(request)

        started = time.monotonic()
        log.info(
            "Generating SMART goal for goal_id=%s",
            request.goal_id or "<unknown>",
        )

        prompt = SMART_GENERATION_PROMPT.format(
            vague_goal=request.vague_goal,
            context=request.context or "(none)",
            available_resources=", ".join(request.available_resources) or "(unspecified)",
            known_constraints=", ".join(request.known_constraints) or "(unspecified)",
            deadline_hint=request.deadline_hint or "(none)",
            framework=request.framework or "(none)",
        )
        raw = self._complete(prompt, system=SMART_SYSTEM_PROMPT).strip()
        data = self._extract_json_object(raw)

        criteria = self._parse_criteria(data.get("criteria", []))
        success_metrics = self._parse_success_metrics(data.get("success_metrics", []))
        kill_criteria = self._parse_kill_criteria(data.get("kill_criteria", []))
        open_questions = [str(q) for q in data.get("open_questions", []) if isinstance(q, str)]
        completion_criteria = [
            str(c) for c in data.get("completion_criteria", []) if isinstance(c, str)
        ]

        smart_statement = str(data.get("smart_statement", "")).strip() or request.vague_goal
        deadline = str(data.get("deadline", "")).strip() or "(not specified)"

        overall_score = self._coerce_score(data.get("overall_smart_score"))
        if overall_score is None:
            overall_score = self._compute_score_from_criteria(criteria)

        smart_quality = self._reconcile_quality(data.get("smart_quality"), overall_score)

        goal = SMARTGoal(
            goal_id=request.goal_id,
            original_goal=request.vague_goal,
            smart_statement=smart_statement,
            criteria=criteria,
            completion_criteria=completion_criteria,
            success_metrics=success_metrics,
            kill_criteria=kill_criteria,
            deadline=deadline,
            open_questions=open_questions,
            overall_smart_score=overall_score,
            smart_quality=smart_quality,
            generator_model=self.model,
            framework=request.framework,
        )

        elapsed = time.monotonic() - started
        log.info(
            "SMART goal generation for goal_id=%s done in %.2fs (quality=%s, score=%.2f)",
            request.goal_id or "<unknown>",
            elapsed,
            smart_quality,
            overall_score,
        )
        return goal

    # --- Input validation ----------------------------------------------

    def _validate_request(self, request: GoalRequest) -> None:
        if not request.vague_goal or not request.vague_goal.strip():
            raise ValueError("GoalRequest.vague_goal cannot be empty.")

    # --- Parsers --------------------------------------------------------

    def _parse_criteria(self, raw: list[Any]) -> list[SMARTCriterion]:
        criteria: list[SMARTCriterion] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                criteria.append(SMARTCriterion(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SMARTCriterion (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {c.criterion for c in criteria}
        for name in SMART_CRITERIA:
            if name not in seen:
                criteria.append(
                    SMARTCriterion(
                        criterion=name,  # type: ignore[arg-type]
                        statement="Not addressed by the generator.",
                        quality_score=0.0,
                    )
                )

        order = {name: i for i, name in enumerate(SMART_CRITERIA)}
        criteria.sort(key=lambda c: order.get(c.criterion, len(SMART_CRITERIA)))
        return criteria

    def _parse_success_metrics(self, raw: list[Any]) -> list[SuccessMetric]:
        metrics: list[SuccessMetric] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                metrics.append(SuccessMetric(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SuccessMetric (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return metrics

    def _parse_kill_criteria(self, raw: list[Any]) -> list[KillCriterion]:
        kills: list[KillCriterion] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                kills.append(KillCriterion(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed KillCriterion (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return kills

    def _coerce_score(self, raw: Any) -> float | None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, value))

    def _compute_score_from_criteria(self, criteria: list[SMARTCriterion]) -> float:
        if not criteria:
            return 0.0
        return round(sum(c.quality_score for c in criteria) / len(criteria), 2)

    def _reconcile_quality(
        self, raw: Any, overall_score: float
    ) -> Literal["strong", "acceptable", "weak"]:
        if isinstance(raw, str) and raw.strip().lower() in ("strong", "acceptable", "weak"):
            return raw.strip().lower()  # type: ignore[return-value]
        if overall_score >= 0.8:
            return "strong"
        if overall_score >= 0.5:
            return "acceptable"
        return "weak"

    # --- JSON object extraction (single object, not array) -------------

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
        return {}
