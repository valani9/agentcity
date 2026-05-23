"""ProcessGainLossAnalyzer: multi-mode Steiner process-gain/loss diagnostic.

Backward-compatible: ``ProcessGainLossDetector`` remains exported as
an alias for ``ProcessGainLossAnalyzer``.
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
    FORENSIC_COUNTERFACTUAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_LOG_AUDIT_PROMPT,
    PROCESS_GAIN_LOSS_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_FACTORS_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    PROCESS_FACTORS,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CounterfactualAudit,
    InteractionLogAudit,
    ProcessFactor,
    ProcessFactorEvidence,
    ProcessGainLossDetection,
    ProcessGainLossMode,
    ProcessIntervention,
    ProcessProfilePattern,
    ProcessTrace,
    severity_from_loss,
)

log = get_logger("agentcity.process_gain_loss.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class ProcessGainLossAnalyzer:
    """Run the Process Gain/Loss diagnostic on a ProcessTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ProcessGainLossMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ProcessGainLossMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: ProcessTrace,
        *,
        mode: ProcessGainLossMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> ProcessGainLossDetection:
        active_mode: ProcessGainLossMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="process_gain_loss"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[ProcessTrace],
        *,
        mode: ProcessGainLossMode | None = None,
    ) -> Iterator[ProcessGainLossDetection]:
        active_mode: ProcessGainLossMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="process_gain_loss"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: ProcessTrace,
        mode: ProcessGainLossMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> ProcessGainLossDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Process Gain/Loss diagnostic (mode=%s) for trace %s",
            mode,
            trace.trace_id or "<unknown>",
        )

        acc = _PipelineAcc()
        log_audit: InteractionLogAudit | None = None
        counterfactual: CounterfactualAudit | None = None

        # Deterministic gain/loss calculation.
        team_quality = trace.team_result.quality_score
        best_baseline = max(trace.individual_baselines, key=lambda b: b.quality_score)
        individual_best_quality = best_baseline.quality_score
        individual_mean = sum(b.quality_score for b in trace.individual_baselines) / max(
            1, len(trace.individual_baselines)
        )
        gain_loss_score = round(team_quality - individual_best_quality, 4)
        process_quality = self._coerce_process_quality(gain_loss_score)

        cost_overhead_ratio: float | None = None
        if (
            trace.team_result.cost_units is not None
            and best_baseline.cost_units is not None
            and best_baseline.cost_units > 0
        ):
            cost_overhead_ratio = round(trace.team_result.cost_units / best_baseline.cost_units, 4)

        # Short-circuit when process-gain: no LLM calls needed; team won.
        factors: list[ProcessFactorEvidence] = []
        interventions: list[ProcessIntervention] = []
        if process_quality == "process-gain":
            pass
        elif mode == "quick":
            factors, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            factors = self._pass_standard_factors(trace, acc)
            interventions = self._pass_standard_interventions(trace, factors, process_quality, acc)
        elif mode == "forensic":
            factors = self._pass_standard_factors(trace, acc)
            log_audit = self._pass_forensic_log_audit(trace, acc)
            counterfactual = self._pass_forensic_counterfactual(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace, factors, process_quality, log_audit, counterfactual, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown ProcessGainLossMode: {mode!r}")

        profile_pattern = self._classify_profile_pattern(
            factors, process_quality, gain_loss_score, cost_overhead_ratio, trace
        )
        severity = severity_from_loss(gain_loss_score)

        composition = (
            self._build_composition_handoff(trace, process_quality, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = ProcessGainLossDetection(
                    trace_id=trace.trace_id,
                    process_quality=process_quality,
                    gain_loss_score=gain_loss_score,
                    individual_best_quality=individual_best_quality,
                    individual_best_agent=best_baseline.agent_name,
                    individual_mean_quality=individual_mean,
                    team_quality=team_quality,
                    contributing_factors=factors,
                    interventions=interventions,
                    cost_overhead_ratio=cost_overhead_ratio,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = ProcessGainLossDetection(
            trace_id=trace.trace_id,
            process_quality=process_quality,
            gain_loss_score=gain_loss_score,
            individual_best_quality=individual_best_quality,
            individual_best_agent=best_baseline.agent_name,
            individual_mean_quality=individual_mean,
            team_quality=team_quality,
            contributing_factors=factors,
            interventions=interventions,
            cost_overhead_ratio=cost_overhead_ratio,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            interaction_log_audit=log_audit,
            counterfactual_audit=counterfactual,
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
        log.info(
            "Process Gain/Loss done mode=%s quality=%s score=%.2f profile=%s elapsed=%.0fms",
            mode,
            process_quality,
            gain_loss_score,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    def _validate_trace(self, trace: ProcessTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("ProcessTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("ProcessTrace.outcome cannot be empty.")
        if len(trace.individual_baselines) < 2:
            raise ValueError("ProcessTrace.individual_baselines must contain at least 2 baselines.")
        if not trace.team_result.agents:
            raise ValueError("ProcessTrace.team_result.agents cannot be empty.")

    def _scan_injection(self, trace: ProcessTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("interaction_log", trace.interaction_log),
            ("team_result.output_summary", trace.team_result.output_summary),
        ]
        for i, b in enumerate(trace.individual_baselines):
            targets.append((f"individual_baselines[{i}].output_summary", b.output_summary))
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
        mode: ProcessGainLossMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=PROCESS_GAIN_LOSS_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "process_gain_loss"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_quick(
        self, trace: ProcessTrace, acc: "_PipelineAcc"
    ) -> tuple[list[ProcessFactorEvidence], ProcessIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            individual_baselines=[b.model_dump() for b in trace.individual_baselines],
            team_result=trace.team_result.model_dump(),
            interaction_log=trace.interaction_log or "(none)",
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        factors = self._parse_factors(obj.get("contributing_factors", []))
        top_iv: ProcessIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = ProcessIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return factors, top_iv

    def _pass_standard_factors(
        self, trace: ProcessTrace, acc: "_PipelineAcc"
    ) -> list[ProcessFactorEvidence]:
        prompt = assemble_prompt(
            STANDARD_FACTORS_PROMPT,
            task=trace.task,
            individual_baselines=[b.model_dump() for b in trace.individual_baselines],
            team_result=trace.team_result.model_dump(),
            interaction_log=trace.interaction_log or "(none)",
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="standard_factors", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        return self._parse_factors(obj.get("contributing_factors", []))

    def _pass_standard_interventions(
        self,
        trace: ProcessTrace,
        factors: list[ProcessFactorEvidence],
        process_quality: str,
        acc: "_PipelineAcc",
    ) -> list[ProcessIntervention]:
        if process_quality == "process-gain":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            contributing_factors=[f.model_dump() for f in factors],
            process_quality=process_quality,
            task=trace.task,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_log_audit(
        self, trace: ProcessTrace, acc: "_PipelineAcc"
    ) -> InteractionLogAudit | None:
        if not trace.interaction_log:
            return None
        prompt = assemble_prompt(
            FORENSIC_LOG_AUDIT_PROMPT,
            interaction_log=trace.interaction_log,
        )
        raw = self._call(prompt, pass_name="forensic_log_audit", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return InteractionLogAudit(**obj)
        except Exception as exc:
            log.warning("InteractionLogAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_counterfactual(
        self, trace: ProcessTrace, acc: "_PipelineAcc"
    ) -> CounterfactualAudit | None:
        prompt = assemble_prompt(
            FORENSIC_COUNTERFACTUAL_PROMPT,
            individual_baselines=[b.model_dump() for b in trace.individual_baselines],
            team_result=trace.team_result.model_dump(),
            task=trace.task,
        )
        raw = self._call(prompt, pass_name="forensic_counterfactual", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CounterfactualAudit(**obj)
        except Exception as exc:
            log.warning("CounterfactualAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: ProcessTrace,
        factors: list[ProcessFactorEvidence],
        process_quality: str,
        log_audit: InteractionLogAudit | None,
        counterfactual: CounterfactualAudit | None,
        acc: "_PipelineAcc",
    ) -> list[ProcessIntervention]:
        if process_quality == "process-gain":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            contributing_factors=[f.model_dump() for f in factors],
            process_quality=process_quality,
            log_audit=log_audit.model_dump() if log_audit else None,
            counterfactual=counterfactual.model_dump() if counterfactual else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_factors(self, raw: Any) -> list[ProcessFactorEvidence]:
        factors: list[ProcessFactorEvidence] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    factors.append(ProcessFactorEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed ProcessFactorEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {f.factor for f in factors}
        for fac in PROCESS_FACTORS:
            if fac not in seen:
                factors.append(
                    ProcessFactorEvidence(
                        factor=fac,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed for this factor.",
                        evidence_quotes=[],
                        confidence=0.5,
                    )
                )
        order = {f: i for i, f in enumerate(PROCESS_FACTORS)}
        factors.sort(key=lambda f: order.get(f.factor, len(PROCESS_FACTORS)))
        return factors

    def _parse_interventions(self, raw: str) -> list[ProcessIntervention]:
        data = extract_json_array(raw)
        interventions: list[ProcessIntervention] = []
        for entry in data:
            try:
                interventions.append(ProcessIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed ProcessIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    def _coerce_process_quality(
        self, gain_loss_score: float
    ) -> Literal["process-gain", "neutral", "process-loss"]:
        if gain_loss_score > 0.05:
            return "process-gain"
        if gain_loss_score < -0.05:
            return "process-loss"
        return "neutral"

    def _process_quality(
        self, gain_loss_score: float
    ) -> Literal["process-gain", "neutral", "process-loss"]:
        """v0.0.x compat alias."""
        return self._coerce_process_quality(gain_loss_score)

    def _classify_profile_pattern(
        self,
        factors: list[ProcessFactorEvidence],
        process_quality: str,
        gain_loss_score: float,
        cost_overhead_ratio: float | None,
        trace: ProcessTrace,
    ) -> ProcessProfilePattern:
        if process_quality == "process-gain":
            return "process_gain_balanced"
        if process_quality == "neutral":
            return "neutral_team"

        # Cost overhead with loss = worst case.
        if cost_overhead_ratio is not None and cost_overhead_ratio > 1.5:
            return "cost_overhead_with_loss"

        # Team too large heuristic.
        if len(trace.team_result.agents) >= 5:
            coord = next((f for f in factors if f.factor == "coordination_cost"), None)
            if coord and coord.score >= 0.5:
                return "team_too_large"

        # Multi-factor loss.
        high_factors = [f for f in factors if f.score >= 0.5]
        if len(high_factors) >= 2:
            return "multi_factor_loss"

        # Dominant single factor.
        if high_factors:
            dominant = max(high_factors, key=lambda f: f.score)
            mapping: dict[str, ProcessProfilePattern] = {
                "coordination_cost": "coordination_dominant_loss",
                "social_loafing": "social_loafing_dominant_loss",
                "groupthink": "groupthink_dominant_loss",
                "handoff_loss": "handoff_dominant_loss",
                "context_dilution": "context_dilution_dominant_loss",
                "consensus_dilution": "consensus_dilution_dominant_loss",
            }
            return mapping.get(dominant.factor, "indeterminate")

        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: ProcessTrace,
        process_quality: str,
        profile_pattern: ProcessProfilePattern,
        interventions: list[ProcessIntervention],
    ) -> ComposedPatternHandoff:
        provisional = ProcessGainLossDetection(
            trace_id=trace.trace_id,
            process_quality=cast(Any, process_quality),
            gain_loss_score=0.0,
            individual_best_quality=0.0,
            individual_best_agent="x",
            individual_mean_quality=0.0,
            team_quality=0.0,
            contributing_factors=[],
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "process_quality": process_quality,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[ProcessIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_factor)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.factor, pb.failure_mode) not in attached:
                attached[(pb.factor, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
ProcessGainLossDetector = ProcessGainLossAnalyzer


class ProcessGainLossAnalyzerAsync:
    """Async mirror of :class:`ProcessGainLossAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ProcessGainLossMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ProcessGainLossMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: ProcessTrace,
        *,
        mode: ProcessGainLossMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> ProcessGainLossDetection:
        active_mode: ProcessGainLossMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = ProcessGainLossAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.process_gain_loss.generator")
_legacy_log.addHandler(logging.NullHandler())

# Silence unused warnings -- public re-export.
_PUBLIC_REEXPORTS: tuple[object, ...] = (ProcessFactor,)
