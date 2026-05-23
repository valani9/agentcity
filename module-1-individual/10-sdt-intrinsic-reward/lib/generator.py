"""SDTRewardDetector: diagnose Deci & Ryan's three basic psychological
needs (autonomy / competence / relatedness) for an AI agent and identify
the most-undermined need.

Pipeline:
  1. Validate the trace (non-empty task + outcome + at least one of
     system_prompt / extrinsic_signals / observed_behaviors)
  2. Pass 1: LLM scores each need + identifies most-undermined + buckets quality
  3. Pass 2: propose interventions (skipped if quality is "intrinsic")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, NEEDS_PROMPT, SDT_SYSTEM_PROMPT
from .schema import (
    SDT_NEEDS,
    AgentSDTTrace,
    NeedScore,
    SDTDetection,
    SDTIntervention,
)

log = logging.getLogger("agentcity.sdt_reward.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class SDTRewardDetector:
    """Run the SDT Intrinsic Reward Shaping diagnostic on an AgentSDTTrace."""

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

    def run(self, trace: AgentSDTTrace) -> SDTDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running SDT Intrinsic Reward diagnostic for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_needs(trace)
        evidence = self._parse_evidence(data.get("need_evidence", []))
        score = self._compute_intrinsic_score(evidence, data.get("intrinsic_motivation_score"))
        undermined = self._coerce_undermined(data.get("most_undermined_need"), evidence)
        quality = self._motivation_quality(
            score, str(data.get("motivation_quality", "")).strip().lower()
        )

        interventions = (
            []
            if quality == "intrinsic"
            else self._pass_2_interventions(evidence, undermined, quality, trace.task_class)
        )

        detection = SDTDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            need_evidence=evidence,
            intrinsic_motivation_score=score,
            motivation_quality=quality,
            most_undermined_need=undermined,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "SDT diagnostic for agent %s done in %.2fs (score=%.2f, undermined=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            score,
            undermined,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentSDTTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentSDTTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentSDTTrace.outcome cannot be empty.")
        if not trace.system_prompt and not trace.extrinsic_signals and not trace.observed_behaviors:
            raise ValueError(
                "AgentSDTTrace must include at least one of system_prompt, "
                "extrinsic_signals, or observed_behaviors (otherwise there "
                "is nothing to diagnose)."
            )

    # --- LLM passes ----------------------------------------------------

    def _pass_1_needs(self, trace: AgentSDTTrace) -> dict[str, Any]:
        prompt = NEEDS_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            extrinsic_signals="\n".join(f"- {s}" for s in trace.extrinsic_signals) or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
        )
        raw = self._complete(prompt, system=SDT_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        evidence: list[NeedScore],
        undermined: str,
        motivation_quality: str,
        task_class: str,
    ) -> list[SDTIntervention]:
        evidence_text = json.dumps([ev.model_dump() for ev in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            most_undermined_need=undermined,
            motivation_quality=motivation_quality,
            task_class=task_class,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=SDT_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[SDTIntervention] = []
        for entry in data:
            try:
                interventions.append(SDTIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SDTIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_evidence(self, raw: list[Any]) -> list[NeedScore]:
        evidence: list[NeedScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(NeedScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed NeedScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.need for ev in evidence}
        for need in SDT_NEEDS:
            if need not in seen:
                evidence.append(
                    NeedScore(
                        need=need,  # type: ignore[arg-type]
                        score=0.5,
                        explanation="No evidence observed for this need.",
                        evidence_quotes=[],
                    )
                )

        order = {n: i for i, n in enumerate(SDT_NEEDS)}
        evidence.sort(key=lambda ev: order.get(ev.need, len(SDT_NEEDS)))
        return evidence

    def _compute_intrinsic_score(self, evidence: list[NeedScore], raw: Any) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not evidence:
            return 0.5
        mean = sum(ev.score for ev in evidence) / len(evidence)
        return round(max(0.0, min(1.0, mean)), 2)

    def _coerce_undermined(
        self, raw: Any, evidence: list[NeedScore]
    ) -> Literal["autonomy", "competence", "relatedness", "none"]:
        valid = set(SDT_NEEDS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        if not evidence:
            return "none"
        bottom = min(evidence, key=lambda ev: ev.score)
        if bottom.score >= 0.7:
            return "none"
        return bottom.need

    def _motivation_quality(
        self, score: float, raw_quality: str
    ) -> Literal["intrinsic", "mixed", "controlled"]:
        if raw_quality in ("intrinsic", "mixed", "controlled"):
            return raw_quality  # type: ignore[return-value]
        if score >= 0.7:
            return "intrinsic"
        if score >= 0.4:
            return "mixed"
        return "controlled"

    # --- JSON object extraction -----------------------------------------

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
