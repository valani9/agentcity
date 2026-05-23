"""PlusDeltaFeedbackGenerator: produce a structured plus/delta inter-agent
feedback artifact. Forward-looking, behavioral, specific.

Pipeline:
  1. Validate the request (non-empty reviewer + subject + task_context +
     contribution_artifact)
  2. Single LLM pass to generate the structured artifact
  3. Post-process: enforce max-items-per-category caps, recompute the
     overall_assessment if the LLM left it out, reconcile the quality score
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._retry import with_retry

from .prompts import PLUS_DELTA_PROMPT, PLUS_DELTA_SYSTEM_PROMPT
from .schema import (
    Commitment,
    DeltaItem,
    FeedbackRequest,
    PlusDeltaFeedback,
    PlusItem,
)

log = logging.getLogger("agentcity.plus_delta.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class PlusDeltaFeedbackGenerator:
    """Generate a plus/delta feedback artifact from a FeedbackRequest."""

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

    def run(self, request: FeedbackRequest) -> PlusDeltaFeedback:
        self._validate_request(request)

        started = time.monotonic()
        log.info(
            "Generating plus/delta feedback for feedback_id=%s (%s -> %s)",
            request.feedback_id or "<unknown>",
            request.reviewer_agent,
            request.subject_agent,
        )

        prompt = PLUS_DELTA_PROMPT.format(
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            success_criteria="\n".join(f"- {c}" for c in request.success_criteria)
            or "(none provided)",
            style=request.style,
            max_items=request.max_items_per_category,
            contribution_artifact=request.contribution_artifact,
        )
        raw = self._complete(prompt, system=PLUS_DELTA_SYSTEM_PROMPT).strip()
        data = self._extract_json_object(raw)

        plus_items = self._parse_plus_items(
            data.get("plus_items", []), request.max_items_per_category
        )
        delta_items = self._parse_delta_items(
            data.get("delta_items", []), request.max_items_per_category
        )
        commitments = self._parse_commitments(data.get("commitments", []))
        overall = self._coerce_overall(data.get("overall_assessment"), delta_items)
        quality = self._coerce_quality(data.get("feedback_quality_score"))

        feedback = PlusDeltaFeedback(
            feedback_id=request.feedback_id,
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            plus_items=plus_items,
            delta_items=delta_items,
            commitments=commitments,
            overall_assessment=overall,
            feedback_quality_score=quality,
            generator_model=self.model,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Plus/delta feedback for feedback_id=%s done in %.2fs (+:%d, Δ:%d, overall=%s)",
            request.feedback_id or "<unknown>",
            elapsed,
            len(plus_items),
            len(delta_items),
            overall,
        )
        return feedback

    # --- Input validation ----------------------------------------------

    def _validate_request(self, request: FeedbackRequest) -> None:
        if not request.reviewer_agent or not request.reviewer_agent.strip():
            raise ValueError("FeedbackRequest.reviewer_agent cannot be empty.")
        if not request.subject_agent or not request.subject_agent.strip():
            raise ValueError("FeedbackRequest.subject_agent cannot be empty.")
        if not request.task_context or not request.task_context.strip():
            raise ValueError("FeedbackRequest.task_context cannot be empty.")
        if not request.contribution_artifact or not request.contribution_artifact.strip():
            raise ValueError("FeedbackRequest.contribution_artifact cannot be empty.")

    # --- Parsers --------------------------------------------------------

    def _parse_plus_items(self, raw: list[Any], cap: int) -> list[PlusItem]:
        items: list[PlusItem] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(PlusItem(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed PlusItem (%s): %r",
                    type(exc).__name__,
                    entry,
                )
            if len(items) >= cap:
                break
        return items

    def _parse_delta_items(self, raw: list[Any], cap: int) -> list[DeltaItem]:
        items: list[DeltaItem] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(DeltaItem(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DeltaItem (%s): %r",
                    type(exc).__name__,
                    entry,
                )
            if len(items) >= cap:
                break
        return items

    def _parse_commitments(self, raw: list[Any]) -> list[Commitment]:
        items: list[Commitment] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(Commitment(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed Commitment (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return items

    def _coerce_overall(
        self, raw: Any, delta_items: list[DeltaItem]
    ) -> Literal["keep-going", "iterate", "rework"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "keep-going",
            "iterate",
            "rework",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        # Fallback: infer from delta severities
        has_critical = any(d.severity == "critical" for d in delta_items)
        has_moderate = any(d.severity == "moderate" for d in delta_items)
        if has_critical:
            return "rework"
        if has_moderate:
            return "iterate"
        return "keep-going"

    def _coerce_quality(self, raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, value))

    # --- JSON object extraction ----------------------------------------

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
