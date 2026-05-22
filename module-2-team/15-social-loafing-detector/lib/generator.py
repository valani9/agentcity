"""SocialLoafingDetector: diagnose Latané et al.'s social loafing in a
multi-agent execution trace.

Pipeline:
  1. Validate the trace (>=2 agents, >=1 message, non-empty task + outcome)
  2. Pass 1: LLM scores per-agent contribution share + loafing score
  3. Compute Gini coefficient of contribution shares
  4. Determine loafing-quality bucket (no / mild / severe)
  5. Pass 2: propose interventions targeting loafing agents
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    CONTRIBUTION_PROMPT,
    INTERVENTIONS_PROMPT,
    LOAFING_SYSTEM_PROMPT,
)
from .schema import (
    AgentContribution,
    LoafingIntervention,
    MultiAgentTaskTrace,
    SocialLoafingDetection,
)

log = logging.getLogger("agentcity.social_loafing.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class SocialLoafingDetector:
    """Run the Social Loafing diagnostic on a MultiAgentTaskTrace."""

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

    def run(self, trace: MultiAgentTaskTrace) -> SocialLoafingDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Social Loafing detection for team %s (agents=%d, messages=%d)",
            trace.team_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
        )

        contributions = self._pass_1_contributions(trace, trace_text)
        gini = self._gini(contributions)
        quality = self._loafing_quality(contributions, gini)
        interventions = self._pass_2_interventions(trace, trace_text, contributions, quality, gini)

        detection = SocialLoafingDetection(
            team_id=trace.team_id,
            agent_contributions=contributions,
            gini_coefficient=gini,
            loafing_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Social Loafing detection for team %s done in %.2fs (quality=%s, gini=%.2f)",
            trace.team_id or "<unknown>",
            elapsed,
            quality,
            gini,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: MultiAgentTaskTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("MultiAgentTaskTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentTaskTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentTaskTrace.agents must contain at least 2 agents.")
        if not trace.messages:
            raise ValueError("MultiAgentTaskTrace.messages cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_contributions(
        self, trace: MultiAgentTaskTrace, trace_text: str
    ) -> list[AgentContribution]:
        prompt = CONTRIBUTION_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LOAFING_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        contributions: list[AgentContribution] = []
        for entry in data:
            try:
                contributions.append(AgentContribution(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed AgentContribution (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        # Ensure every agent listed in the trace has an entry; absent ones
        # get a stub so downstream consumers don't crash on missing keys.
        seen = {c.agent_name for c in contributions}
        for agent in trace.agents:
            if agent not in seen:
                contributions.append(
                    AgentContribution(
                        agent_name=agent,
                        contribution_share=0.0,
                        substantive_work_count=0,
                        cosmetic_work_count=0,
                        loafing_score=1.0,
                        role="absent",
                        explanation="Agent did not appear in the trace.",
                        evidence_quotes=[],
                    )
                )

        order = {agent: i for i, agent in enumerate(trace.agents)}
        contributions.sort(key=lambda c: order.get(c.agent_name, len(trace.agents)))
        return contributions

    def _pass_2_interventions(
        self,
        trace: MultiAgentTaskTrace,
        trace_text: str,
        contributions: list[AgentContribution],
        quality: str,
        gini: float,
    ) -> list[LoafingIntervention]:
        if quality == "no-loafing":
            return []
        contributions_text = json.dumps(
            [c.model_dump() for c in contributions], indent=2, default=str
        )
        prompt = INTERVENTIONS_PROMPT.format(
            loafing_quality=quality,
            gini_coefficient=f"{gini:.2f}",
            contributions=contributions_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=LOAFING_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[LoafingIntervention] = []
        for entry in data:
            try:
                interventions.append(LoafingIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LoafingIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _gini(self, contributions: list[AgentContribution]) -> float:
        """Gini coefficient of contribution shares.

        0.0 = perfectly equal contribution; 1.0 = one agent does everything.
        """
        shares = sorted(c.contribution_share for c in contributions)
        n = len(shares)
        if n == 0:
            return 0.0
        total = sum(shares)
        if total <= 0:
            return 0.0
        # Standard formula: G = (sum_i (2i - n - 1) * x_i) / (n * sum x_i)
        weighted = sum((2 * i - n - 1) * x for i, x in enumerate(shares, start=1))
        return round(max(0.0, min(1.0, weighted / (n * total))), 2)

    def _loafing_quality(
        self, contributions: list[AgentContribution], gini: float
    ) -> Literal["no-loafing", "mild-loafing", "severe-loafing"]:
        loafer_count = sum(1 for c in contributions if c.role in ("loafer", "absent"))
        n = len(contributions)
        if n == 0:
            return "no-loafing"
        loafer_fraction = loafer_count / n

        if gini >= 0.5 or loafer_fraction >= 0.5:
            return "severe-loafing"
        if gini >= 0.3 or loafer_fraction >= 0.25:
            return "mild-loafing"
        return "no-loafing"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: MultiAgentTaskTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Agents: {', '.join(trace.agents)}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        msg_lines: list[str] = []
        for i, m in enumerate(trace.messages):
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else f"[msg {i + 1}] "
            msg_lines.append(
                f"{ts}({m.message_type}) {m.from_agent} → {m.to_agent or 'TEAM'}: {m.content}"
            )
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
