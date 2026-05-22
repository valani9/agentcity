"""DecisionProtocolGenerator: pick the appropriate aggregation model from
the facilitator canon (concurring / majority / consensus / fist-to-five /
unanimous) and emit the protocol spec. Optionally tally a supplied vote
set locally (deterministic Python, no second LLM call).

Pipeline:
  1. Validate the request (non-empty title, >=2 options, >=2 agents)
  2. Single LLM pass to recommend model + emit protocol spec
  3. Reconcile any forced_model override
  4. If votes are supplied, run the local tally per the chosen method
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._retry import with_retry

from .prompts import DECISION_PROTOCOL_PROMPT, DECISION_SYSTEM_PROMPT
from .schema import (
    AgentVote,
    DecisionProtocol,
    DecisionRequest,
)
from .tally import tally_votes

log = logging.getLogger("agentcity.group_decision.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class DecisionProtocolGenerator:
    """Generate a decision-aggregation protocol from the facilitator canon."""

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

    def run(
        self,
        request: DecisionRequest,
        votes: list[AgentVote] | None = None,
    ) -> DecisionProtocol:
        self._validate_request(request)

        started = time.monotonic()
        log.info(
            "Generating decision protocol for decision_id=%s (agents=%d, options=%d)",
            request.decision_id or "<unknown>",
            len(request.agents),
            len(request.options),
        )

        prompt = DECISION_PROTOCOL_PROMPT.format(
            title=request.title,
            options=self._format_options(request),
            agents=", ".join(request.agents),
            stakes=request.stakes,
            reversibility=request.reversibility,
            time_pressure=request.time_pressure,
            expertise_asymmetry=request.expertise_asymmetry,
            regulatory_exposure=request.regulatory_exposure,
            buy_in_required=request.buy_in_required,
            forced_model=request.forced_model or "null",
        )
        raw = self._complete(prompt, system=DECISION_SYSTEM_PROMPT).strip()
        data = self._extract_json_object(raw)

        recommended = self._coerce_model(request.forced_model or data.get("recommended_model"))
        rationale = str(data.get("rationale", "")).strip() or (
            "Selected the default model for the given stakes and reversibility."
        )
        protocol_steps = [
            str(s) for s in data.get("protocol_steps", []) if isinstance(s, str)
        ] or self._default_protocol_steps(recommended)
        threshold = str(data.get("threshold", "")).strip() or self._default_threshold(recommended)
        quorum = self._coerce_quorum(data.get("quorum"))
        tie_breaker = str(data.get("tie_breaker", "")).strip()
        fallback = self._coerce_optional_model(data.get("fallback_model"))

        tally_result = (
            tally_votes(method=recommended, votes=votes, quorum=quorum)
            if votes is not None
            else None
        )

        protocol = DecisionProtocol(
            decision_id=request.decision_id,
            title=request.title,
            recommended_model=recommended,
            rationale=rationale,
            protocol_steps=protocol_steps,
            threshold=threshold,
            quorum=quorum,
            tie_breaker=tie_breaker,
            fallback_model=fallback,
            tally_result=tally_result,
            generator_model=self.model,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Decision protocol for decision_id=%s done in %.2fs (model=%s, tally=%s)",
            request.decision_id or "<unknown>",
            elapsed,
            recommended,
            "yes" if tally_result is not None else "no",
        )
        return protocol

    # --- Input validation ----------------------------------------------

    def _validate_request(self, request: DecisionRequest) -> None:
        if not request.title or not request.title.strip():
            raise ValueError("DecisionRequest.title cannot be empty.")
        if len(request.options) < 2:
            raise ValueError("DecisionRequest.options must contain at least 2 options.")
        if len(request.agents) < 2:
            raise ValueError("DecisionRequest.agents must contain at least 2 agents.")

    # --- Coercion + defaults --------------------------------------------

    def _coerce_model(
        self, raw: Any
    ) -> Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "concurring",
            "majority",
            "consensus",
            "fist_to_five",
            "unanimous",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        return "majority"

    def _coerce_optional_model(
        self, raw: Any
    ) -> Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None:
        if raw is None or raw == "null" or raw == "":
            return None
        if isinstance(raw, str) and raw.strip().lower() in (
            "concurring",
            "majority",
            "consensus",
            "fist_to_five",
            "unanimous",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        return None

    def _coerce_quorum(self, raw: Any) -> int | None:
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return max(1, value)

    def _default_protocol_steps(self, model: str) -> list[str]:
        if model == "concurring":
            return [
                "Designate one decisive voter (highest expertise + accountability).",
                "Decisive voter casts the vote; other agents may object explicitly.",
                "If no objection within the time window, the decision is final.",
            ]
        if model == "majority":
            return [
                "Each agent casts one vote for one option (or abstains).",
                "Tally cast votes; option with >50% of cast votes wins.",
                "Record dissenters by name; surface in the postmortem if applicable.",
            ]
        if model == "consensus":
            return [
                "Discuss until objections are surfaced and addressed.",
                "Each agent affirms or formally blocks (a block needs a concrete reason).",
                "If any agent blocks, return to discussion; do not call the decision.",
            ]
        if model == "fist_to_five":
            return [
                "Each agent privately scores their support (0 = block, 5 = champion).",
                "Reveal scores simultaneously.",
                "Any score of 0 blocks the option; otherwise the option with mean >= 3 wins.",
                "If multiple options qualify, the highest mean wins.",
            ]
        if model == "unanimous":
            return [
                "Each agent must positively vote for the same option.",
                "Any abstention or dissent halts the decision.",
                "Return to discussion until unanimous or escalate.",
            ]
        return ["Run the chosen model."]

    def _default_threshold(self, model: str) -> str:
        return {
            "concurring": "Decisive vote with no explicit objection.",
            "majority": ">50% of cast votes.",
            "consensus": "All agents affirm or do not block.",
            "fist_to_five": "Mean score >= 3.0 with no agent at score 0 (block).",
            "unanimous": "All agents vote for the same option.",
        }.get(model, "See protocol steps.")

    def _format_options(self, request: DecisionRequest) -> str:
        return "\n".join(f"  - {o.option_id}: {o.description}" for o in request.options)

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
