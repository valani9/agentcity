"""SocialLoafingAnalyzer: multi-mode Latané et al. social-loafing diagnostic.

Backward-compatible: ``SocialLoafingDetector`` remains exported as
an alias for ``SocialLoafingAnalyzer``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine, Iterable, Iterator
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from agentcity.aar import (
    LLMUsage,
    detect_injection,
    extract_json_array,
    get_logger,
    new_run_id,
    record_llm_call,
    run_context,
    time_call,
    with_retry,
)

from ._calibration import compare_to_baseline, load_baseline
from ._composition import recommended_downstream, recommended_upstream
from ._playbooks import find_playbook_for_intervention
from .prompts import (
    FORENSIC_ANONYMITY_PROMPT,
    FORENSIC_FREE_RIDING_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SOCIAL_LOAFING_SYSTEM_PROMPT,
    STANDARD_CONTRIBUTION_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    AgentContribution,
    AnonymityAudit,
    AttachedPlaybook,
    ComposedPatternHandoff,
    FreeRidingChain,
    LoafingIntervention,
    MultiAgentTaskTrace,
    SocialLoafingDetection,
    SocialLoafingMode,
    SocialLoafingProfilePattern,
    severity_from_gini,
)

log = get_logger("agentcity.social_loafing.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class SocialLoafingAnalyzer:
    """Run the Social Loafing diagnostic on a MultiAgentTaskTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SocialLoafingMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SocialLoafingMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: MultiAgentTaskTrace,
        *,
        mode: SocialLoafingMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SocialLoafingDetection:
        active_mode: SocialLoafingMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="social_loafing"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[MultiAgentTaskTrace],
        *,
        mode: SocialLoafingMode | None = None,
    ) -> Iterator[SocialLoafingDetection]:
        active_mode: SocialLoafingMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="social_loafing"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: MultiAgentTaskTrace,
        mode: SocialLoafingMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> SocialLoafingDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Social Loafing diagnostic (mode=%s) for team %s",
            mode,
            trace.team_id or "<unknown>",
        )

        acc = _PipelineAcc()
        anonymity_audit: AnonymityAudit | None = None
        free_riding_chains: list[FreeRidingChain] = []

        if mode == "quick":
            contributions, gini, quality, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            contributions, gini, quality = self._pass_standard_contributions(trace, acc)
            interventions = self._pass_standard_interventions(trace, contributions, quality, acc)
        elif mode == "forensic":
            contributions, gini, quality = self._pass_standard_contributions(trace, acc)
            anonymity_audit = self._pass_forensic_anonymity(trace, acc)
            free_riding_chains = self._pass_forensic_free_riding(trace, contributions, acc)
            interventions = self._pass_forensic_interventions(
                trace, contributions, quality, anonymity_audit, free_riding_chains, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown SocialLoafingMode: {mode!r}")

        # Fill any missing agents as absent.
        named = {c.agent_name for c in contributions}
        for agent in trace.agents:
            if agent not in named:
                contributions.append(
                    AgentContribution(
                        agent_name=agent,
                        contribution_share=0.0,
                        substantive_work_count=0,
                        cosmetic_work_count=0,
                        loafing_score=1.0,
                        role="absent",
                        explanation="No messages observed from this agent.",
                        evidence_quotes=[],
                    )
                )

        profile_pattern = self._classify_profile_pattern(contributions, gini, quality, trace)
        severity = severity_from_gini(gini)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(interventions, contributions) if self.playbooks_enabled else []
        )

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = SocialLoafingDetection(
                    team_id=trace.team_id,
                    agent_contributions=contributions,
                    gini_coefficient=gini,
                    loafing_quality=quality,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return SocialLoafingDetection(
            team_id=trace.team_id,
            agent_contributions=contributions,
            gini_coefficient=gini,
            loafing_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            anonymity_audit=anonymity_audit,
            free_riding_chains=free_riding_chains,
            baseline=baseline,
            composition_handoff=composition,
            attached_playbooks=playbooks,
            run_id=run_id,
            cost_usd=acc.cost_usd,
            tokens_total=acc.tokens_total,
            tokens_input=acc.tokens_input,
            tokens_output=acc.tokens_output,
            llm_calls=acc.llm_calls,
            elapsed_ms=elapsed_ms,
            injection_detected=injection_detected,
        )

    def _validate_trace(self, trace: MultiAgentTaskTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("MultiAgentTaskTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentTaskTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentTaskTrace.agents must contain at least 2 agents.")
        if not trace.messages:
            raise ValueError("MultiAgentTaskTrace.messages cannot be empty.")

    def _scan_injection(self, trace: MultiAgentTaskTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, m in enumerate(trace.messages):
            targets.append((f"messages[{i}].content", m.content))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in trace field",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: SocialLoafingMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SOCIAL_LOAFING_SYSTEM_PROMPT)
        usage = cast(LLMUsage | None, getattr(self.llm, "last_usage", None))
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        total_tokens = (
            int(getattr(usage, "total_tokens", 0) or 0) if usage else input_tokens + output_tokens
        )
        cost = (input_tokens / 1000.0) * self.cost_per_1k_input + (
            output_tokens / 1000.0
        ) * self.cost_per_1k_output
        record_llm_call(
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            elapsed_ms=t["elapsed_ms"],
            extra={"pass": pass_name, "mode": mode, "pattern": "social_loafing"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_quick(
        self, trace: MultiAgentTaskTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[AgentContribution],
        float,
        Literal["no-loafing", "mild-loafing", "severe-loafing"],
        LoafingIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            agents=trace.agents,
            messages=[m.model_dump() for m in trace.messages],
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        contributions = self._parse_contributions(obj.get("agent_contributions", []))
        gini = self._compute_gini(contributions)
        quality = self._loafing_quality(contributions, gini)
        top_iv: LoafingIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = LoafingIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return contributions, gini, quality, top_iv

    def _pass_standard_contributions(
        self, trace: MultiAgentTaskTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[AgentContribution],
        float,
        Literal["no-loafing", "mild-loafing", "severe-loafing"],
    ]:
        prompt = assemble_prompt(
            STANDARD_CONTRIBUTION_PROMPT,
            task=trace.task,
            agents=trace.agents,
            messages=[m.model_dump() for m in trace.messages],
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="standard_contribution", mode="standard", acc=acc)
        # Accept either a JSON object {"agent_contributions": [...]} or a bare
        # array of contributions (v0.0.x format).
        obj = _try_json_object(raw)
        if obj:
            contributions = self._parse_contributions(obj.get("agent_contributions", []))
        else:
            arr = extract_json_array(raw)
            contributions = self._parse_contributions(arr)
        gini = self._compute_gini(contributions)
        quality = self._loafing_quality(contributions, gini)
        return contributions, gini, quality

    def _pass_standard_interventions(
        self,
        trace: MultiAgentTaskTrace,
        contributions: list[AgentContribution],
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[LoafingIntervention]:
        if quality == "no-loafing":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            agent_contributions=[c.model_dump() for c in contributions],
            loafing_quality=quality,
            task=trace.task,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_anonymity(
        self, trace: MultiAgentTaskTrace, acc: "_PipelineAcc"
    ) -> AnonymityAudit | None:
        prompt = assemble_prompt(
            FORENSIC_ANONYMITY_PROMPT,
            task=trace.task,
            agents=trace.agents,
            has_per_agent_evaluation=trace.has_per_agent_evaluation,
        )
        raw = self._call(prompt, pass_name="forensic_anonymity", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return AnonymityAudit(**obj)
        except Exception as exc:
            log.warning("AnonymityAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_free_riding(
        self,
        trace: MultiAgentTaskTrace,
        contributions: list[AgentContribution],
        acc: "_PipelineAcc",
    ) -> list[FreeRidingChain]:
        if not any(c.role == "loafer" for c in contributions):
            return []
        prompt = assemble_prompt(
            FORENSIC_FREE_RIDING_PROMPT,
            agent_contributions=[c.model_dump() for c in contributions],
            messages=[m.model_dump() for m in trace.messages],
        )
        raw = self._call(prompt, pass_name="forensic_free_riding", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        chains: list[FreeRidingChain] = []
        for entry in data:
            try:
                chains.append(FreeRidingChain(**entry))
            except Exception as exc:
                log.warning("Dropping malformed FreeRidingChain (%s)", type(exc).__name__)
        return chains

    def _pass_forensic_interventions(
        self,
        trace: MultiAgentTaskTrace,
        contributions: list[AgentContribution],
        quality: str,
        anonymity_audit: AnonymityAudit | None,
        free_riding_chains: list[FreeRidingChain],
        acc: "_PipelineAcc",
    ) -> list[LoafingIntervention]:
        if quality == "no-loafing":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            agent_contributions=[c.model_dump() for c in contributions],
            anonymity_audit=anonymity_audit.model_dump() if anonymity_audit else None,
            free_riding_chains=[fc.model_dump() for fc in free_riding_chains],
            loafing_quality=quality,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_contributions(self, raw: Any) -> list[AgentContribution]:
        contributions: list[AgentContribution] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    contributions.append(AgentContribution(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed AgentContribution (%s)",
                        type(exc).__name__,
                    )
        return contributions

    def _parse_interventions(self, raw: str) -> list[LoafingIntervention]:
        data = extract_json_array(raw)
        interventions: list[LoafingIntervention] = []
        for entry in data:
            try:
                interventions.append(LoafingIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LoafingIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    def _gini(self, contributions: list[AgentContribution]) -> float:
        """v0.0.x compat alias."""
        return self._compute_gini(contributions)

    def _compute_gini(self, contributions: list[AgentContribution]) -> float:
        if not contributions:
            return 0.0
        shares = sorted([c.contribution_share for c in contributions])
        n = len(shares)
        cum = 0.0
        for i, s in enumerate(shares):
            cum += (2 * (i + 1) - n - 1) * s
        total = sum(shares)
        if total == 0:
            return 0.0
        gini = cum / (n * total)
        return round(max(0.0, min(1.0, gini)), 4)

    def _loafing_quality(
        self, contributions: list[AgentContribution], gini: float
    ) -> Literal["no-loafing", "mild-loafing", "severe-loafing"]:
        if not contributions:
            return "no-loafing"
        n_loafers = sum(1 for c in contributions if c.role == "loafer")
        loafer_fraction = n_loafers / len(contributions)
        if loafer_fraction >= 0.5 or gini > 0.45:
            return "severe-loafing"
        if n_loafers > 0 or gini > 0.30:
            return "mild-loafing"
        return "no-loafing"

    def _classify_profile_pattern(
        self,
        contributions: list[AgentContribution],
        gini: float,
        quality: str,
        trace: MultiAgentTaskTrace,
    ) -> SocialLoafingProfilePattern:
        if quality == "no-loafing":
            return "balanced_team"

        n_absent = sum(1 for c in contributions if c.role == "absent")
        if n_absent > 0:
            return "absent_agent"

        n_loafers = sum(1 for c in contributions if c.role == "loafer")
        n_primary = sum(1 for c in contributions if c.role == "primary-contributor")
        n_total = len(contributions)

        if n_loafers == n_total:
            return "all_loafers"

        if n_primary == 1 and n_loafers >= n_total - 1:
            return "single_dominant_contributor"

        if n_primary <= 2 and n_loafers >= n_total - 2:
            return "two_contributors_n_loafers"

        # Ringelmann.
        if len(trace.agents) >= 5 and gini > 0.4:
            return "ringelmann_dilution"

        # Rubber-stamp.
        n_cosmetic_dominant = sum(
            1 for c in contributions if c.cosmetic_work_count > c.substantive_work_count
        )
        if n_cosmetic_dominant >= max(1, n_total // 2):
            return "rubber_stamp_pattern"

        if not trace.has_per_agent_evaluation:
            return "anonymous_evaluation_signal"

        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: MultiAgentTaskTrace,
        profile_pattern: SocialLoafingProfilePattern,
        interventions: list[LoafingIntervention],
    ) -> ComposedPatternHandoff:
        provisional = SocialLoafingDetection(
            team_id=trace.team_id,
            agent_contributions=[],
            gini_coefficient=0.0,
            loafing_quality="mild-loafing",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self,
        interventions: list[LoafingIntervention],
        contributions: list[AgentContribution],
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        target_role_by_name = {c.agent_name: c.role for c in contributions}
        for iv in interventions:
            # Determine target role.
            if iv.target_agent == "__team__":
                target_role = "team"
            else:
                target_role = target_role_by_name.get(iv.target_agent, "loafer")
            pb = find_playbook_for_intervention(target_role, iv.intervention_type)
            if pb is not None and (pb.role, pb.failure_mode) not in attached:
                attached[(pb.role, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
SocialLoafingDetector = SocialLoafingAnalyzer


class SocialLoafingAnalyzerAsync:
    """Async mirror of :class:`SocialLoafingAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SocialLoafingMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SocialLoafingMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: MultiAgentTaskTrace,
        *,
        mode: SocialLoafingMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SocialLoafingDetection:
        active_mode: SocialLoafingMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = SocialLoafingAnalyzer(
            llm_client=sync_shim,
            model=self.model,
            mode=active_mode,
            max_retries=self.max_retries,
            cost_per_1k_input=self.cost_per_1k_input,
            cost_per_1k_output=self.cost_per_1k_output,
            composition_enabled=self.composition_enabled,
            playbooks_enabled=self.playbooks_enabled,
        )
        return await asyncio.to_thread(
            sync_analyzer.run, trace, mode=active_mode, baseline_path=baseline_path
        )


class _PipelineAcc:
    __slots__ = (
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "cost_usd",
        "llm_calls",
        "elapsed_ms",
    )

    def __init__(self) -> None:
        self.tokens_input = 0
        self.tokens_output = 0
        self.tokens_total = 0
        self.cost_usd = 0.0
        self.llm_calls = 0
        self.elapsed_ms = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost: float, elapsed_ms: float) -> None:
        self.tokens_input += input_tokens
        self.tokens_output += output_tokens
        self.tokens_total += input_tokens + output_tokens
        self.cost_usd += cost
        self.elapsed_ms += elapsed_ms
        self.llm_calls += 1


class _SyncAdapterFromAsync:
    def __init__(
        self,
        async_complete: Callable[[str, str | None], Coroutine[Any, Any, str]],
        last_usage: LLMUsage | None,
    ) -> None:
        self._async_complete = async_complete
        self.last_usage = last_usage

    def complete(self, prompt: str, system: str | None = None) -> str:
        return asyncio.run(self._async_complete(prompt, system))


def _try_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            v = json.loads(text[start : end + 1])
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    return None


_legacy_log = logging.getLogger("agentcity.social_loafing.generator")
_legacy_log.addHandler(logging.NullHandler())
