"""EIAuditDetector: diagnose Goleman's 4 EI domains for an AI agent
and identify the weakest domain.

Pipeline:
  1. Validate the trace (non-empty task + outcome + observed_behaviors or
     user_signals or self_reports)
  2. Pass 1: LLM scores all 4 domains + identifies weakest + buckets quality
  3. Pass 2: propose interventions (skipped if quality is "high-ei")
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import DOMAINS_PROMPT, GOLEMAN_SYSTEM_PROMPT, INTERVENTIONS_PROMPT
from .schema import (
    EI_DOMAINS,
    AgentEITrace,
    DomainScore,
    EIDetection,
    EIIntervention,
)

log = logging.getLogger("agentcity.goleman_ei.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class EIAuditDetector:
    """Run the Goleman 4-Domain EI Audit diagnostic on an AgentEITrace."""

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

    def run(self, trace: AgentEITrace) -> EIDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Goleman 4-Domain EI Audit for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_domains(trace)
        domains = self._parse_domains(data.get("domains", []))
        overall_ei = self._compute_overall_ei(domains, data.get("overall_ei"))
        weakest = self._coerce_weakest(data.get("weakest_domain"), domains)
        quality = self._ei_quality(overall_ei, str(data.get("ei_quality", "")).strip().lower())

        interventions = (
            []
            if quality == "high-ei"
            else self._pass_2_interventions(domains, weakest, quality, trace.interaction_class)
        )

        detection = EIDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            interaction_class=trace.interaction_class,
            domains=domains,
            overall_ei=overall_ei,
            ei_quality=quality,
            weakest_domain=weakest,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Goleman EI Audit for agent %s done in %.2fs (ei=%.2f, weakest=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            overall_ei,
            weakest,
            quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentEITrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentEITrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentEITrace.outcome cannot be empty.")
        if not trace.observed_behaviors and not trace.user_signals and not trace.self_reports:
            raise ValueError(
                "AgentEITrace must include at least one of observed_behaviors, "
                "user_signals, or self_reports (otherwise there is nothing to audit)."
            )

    # --- LLM passes ----------------------------------------------------

    def _pass_1_domains(self, trace: AgentEITrace) -> dict[str, Any]:
        prompt = DOMAINS_PROMPT.format(
            task=trace.task,
            interaction_class=trace.interaction_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
            user_signals="\n".join(f"- {u}" for u in trace.user_signals) or "(none)",
            self_reports="\n".join(f"- {s}" for s in trace.self_reports) or "(none)",
        )
        raw = self._complete(prompt, system=GOLEMAN_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        domains: list[DomainScore],
        weakest_domain: str,
        ei_quality: str,
        interaction_class: str,
    ) -> list[EIIntervention]:
        evidence_text = json.dumps([d.model_dump() for d in domains], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            weakest_domain=weakest_domain,
            ei_quality=ei_quality,
            interaction_class=interaction_class,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=GOLEMAN_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[EIIntervention] = []
        for entry in data:
            try:
                interventions.append(EIIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed EIIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers + synthesis -------------------------------------------

    def _parse_domains(self, raw: list[Any]) -> list[DomainScore]:
        domains: list[DomainScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                domains.append(DomainScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DomainScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {d.domain for d in domains}
        for dom in EI_DOMAINS:
            if dom not in seen:
                domains.append(
                    DomainScore(
                        domain=dom,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed for this domain.",
                        evidence_quotes=[],
                    )
                )

        order = {d: i for i, d in enumerate(EI_DOMAINS)}
        domains.sort(key=lambda d: order.get(d.domain, len(EI_DOMAINS)))
        return domains

    def _compute_overall_ei(self, domains: list[DomainScore], raw: Any) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not domains:
            return 0.0
        mean = sum(d.score for d in domains) / len(domains)
        return round(max(0.0, min(1.0, mean)), 2)

    def _coerce_weakest(
        self, raw: Any, domains: list[DomainScore]
    ) -> Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
        "none",
    ]:
        valid = set(EI_DOMAINS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        # Fallback: lowest-scoring domain, or "none" if all are >= 0.7
        if not domains:
            return "none"
        bottom = min(domains, key=lambda d: d.score)
        if bottom.score >= 0.7:
            return "none"
        return bottom.domain

    def _ei_quality(
        self, overall_ei: float, raw_quality: str
    ) -> Literal["high-ei", "developing", "low-ei"]:
        if raw_quality in ("high-ei", "developing", "low-ei"):
            return raw_quality  # type: ignore[return-value]
        if overall_ei >= 0.75:
            return "high-ei"
        if overall_ei >= 0.4:
            return "developing"
        return "low-ei"

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
