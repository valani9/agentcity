"""McGregorOrchestratorAnalyzer: multi-mode Theory X/Y diagnostic.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``OrchestratorModeDetector`` remains exported as
an alias for ``McGregorOrchestratorAnalyzer``.
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
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_OPTIMALITY_PROMPT,
    FORENSIC_STEP_AUDIT_PROMPT,
    MCGREGOR_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_MODE_PROMPT,
    assemble_prompt,
)
from .schema import (
    AttachedPlaybook,
    ComposedPatternHandoff,
    McGregorMode,
    McGregorProfilePattern,
    ModeIndicators,
    OptimalityJustification,
    OrchestratorIntervention,
    OrchestratorMode,
    OrchestratorModeDetection,
    OrchestratorTrace,
    StepAudit,
    severity_from_mismatch,
)

log = get_logger("agentcity.mcgregor.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}

_VALID_MODES: set[str] = {"theory_x", "theory_y", "hybrid"}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class McGregorOrchestratorAnalyzer:
    """Run the McGregor Theory X/Y diagnostic on an OrchestratorTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: McGregorMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: McGregorMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: OrchestratorTrace,
        *,
        mode: McGregorMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> OrchestratorModeDetection:
        active_mode: McGregorMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="mcgregor"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[OrchestratorTrace],
        *,
        mode: McGregorMode | None = None,
    ) -> Iterator[OrchestratorModeDetection]:
        active_mode: McGregorMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="mcgregor"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: OrchestratorTrace,
        mode: McGregorMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> OrchestratorModeDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running McGregor diagnostic (mode=%s) for trace %s",
            mode,
            trace.trace_id or "<unknown>",
        )

        acc = _PipelineAcc()
        step_audits: list[StepAudit] = []
        optimality: OptimalityJustification | None = None

        if mode == "quick":
            (
                observed,
                optimal,
                mismatch,
                indicators,
                quality,
                rationale,
                top_iv,
            ) = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            observed, optimal, mismatch, indicators, quality, rationale = self._pass_standard_mode(
                trace, acc
            )
            interventions = self._pass_standard_interventions(
                trace, observed, optimal, mismatch, indicators, quality, acc
            )
        elif mode == "forensic":
            observed, optimal, mismatch, indicators, quality, rationale = self._pass_standard_mode(
                trace, acc
            )
            step_audits = self._pass_forensic_step_audit(trace, acc)
            optimality = self._pass_forensic_optimality(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                observed,
                optimal,
                mismatch,
                indicators,
                quality,
                step_audits,
                optimality,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown McGregorMode: {mode!r}")

        profile_pattern = self._classify_profile_pattern(
            observed, optimal, mismatch, quality, trace
        )
        severity = severity_from_mismatch(mismatch, quality)

        composition = (
            self._build_composition_handoff(trace, observed, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = OrchestratorModeDetection(
                    observed_mode=observed,
                    optimal_mode=optimal,
                    mode_mismatch=mismatch,
                    indicators=indicators,
                    mode_quality=quality,
                    rationale=rationale,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = OrchestratorModeDetection(
            trace_id=trace.trace_id,
            observed_mode=observed,
            optimal_mode=optimal,
            mode_mismatch=mismatch,
            indicators=indicators,
            mode_quality=quality,
            rationale=rationale,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            step_audits=step_audits,
            optimality_justification=optimality,
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
            "McGregor done mode=%s observed=%s optimal=%s mismatch=%.2f profile=%s elapsed=%.0fms",
            mode,
            observed,
            optimal,
            mismatch,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    # --- Validation ----------------------------------------------------

    def _validate_trace(self, trace: OrchestratorTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("OrchestratorTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("OrchestratorTrace.outcome cannot be empty.")
        if not trace.sub_agents:
            raise ValueError("OrchestratorTrace.sub_agents cannot be empty.")
        if not trace.steps:
            raise ValueError("OrchestratorTrace.steps cannot be empty.")

    def _scan_injection(self, trace: OrchestratorTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, step in enumerate(trace.steps):
            targets.append((f"steps[{i}].content", step.content))
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
        if hit_count:
            log.warning("injection scan: %d field(s) flagged", hit_count)
        return hit_count > 0

    def _serialize_trace(self, trace: OrchestratorTrace) -> list[dict[str, Any]]:
        return [
            {
                "index": i,
                "actor": s.actor,
                "step_type": s.step_type,
                "content": s.content,
                "sub_agent": s.sub_agent,
            }
            for i, s in enumerate(trace.steps)
        ]

    # --- LLM call helper ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: McGregorMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=MCGREGOR_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "mcgregor"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(
        self, trace: OrchestratorTrace, acc: "_PipelineAcc"
    ) -> tuple[
        OrchestratorMode,
        OrchestratorMode,
        float,
        ModeIndicators,
        Literal["well-matched", "mild-mismatch", "severe-mismatch"],
        str,
        OrchestratorIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            task_properties=trace.task_properties.model_dump(),
            sub_agents=trace.sub_agents,
            outcome=trace.outcome,
            success=trace.success,
            trace=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        observed = self._coerce_mode(obj.get("observed_mode"))
        optimal = self._coerce_mode(obj.get("optimal_mode"))
        mismatch = self._coerce_fraction(obj.get("mode_mismatch"))
        indicators = self._parse_indicators(obj.get("indicators", {}))
        quality = self._mode_quality(mismatch, str(obj.get("mode_quality", "")).strip().lower())
        rationale = str(obj.get("rationale", "")).strip()
        top_iv: OrchestratorIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = OrchestratorIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return observed, optimal, mismatch, indicators, quality, rationale, top_iv

    def _pass_standard_mode(
        self, trace: OrchestratorTrace, acc: "_PipelineAcc"
    ) -> tuple[
        OrchestratorMode,
        OrchestratorMode,
        float,
        ModeIndicators,
        Literal["well-matched", "mild-mismatch", "severe-mismatch"],
        str,
    ]:
        prompt = assemble_prompt(
            STANDARD_MODE_PROMPT,
            task=trace.task,
            task_properties=trace.task_properties.model_dump(),
            sub_agents=trace.sub_agents,
            outcome=trace.outcome,
            success=trace.success,
            trace=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="standard_mode", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        observed = self._coerce_mode(obj.get("observed_mode"))
        optimal = self._coerce_mode(obj.get("optimal_mode"))
        mismatch = self._coerce_fraction(obj.get("mode_mismatch"))
        indicators = self._parse_indicators(obj.get("indicators", {}))
        quality = self._mode_quality(mismatch, str(obj.get("mode_quality", "")).strip().lower())
        rationale = str(obj.get("rationale", "")).strip()
        return observed, optimal, mismatch, indicators, quality, rationale

    def _pass_standard_interventions(
        self,
        trace: OrchestratorTrace,
        observed: OrchestratorMode,
        optimal: OrchestratorMode,
        mismatch: float,
        indicators: ModeIndicators,
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[OrchestratorIntervention]:
        if quality == "well-matched":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            observed_mode=observed,
            optimal_mode=optimal,
            mode_quality=quality,
            indicators=indicators.model_dump(),
            task_properties=trace.task_properties.model_dump(),
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_step_audit(
        self, trace: OrchestratorTrace, acc: "_PipelineAcc"
    ) -> list[StepAudit]:
        prompt = assemble_prompt(
            FORENSIC_STEP_AUDIT_PROMPT,
            task_properties=trace.task_properties.model_dump(),
            trace=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="forensic_step_audit", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        audits: list[StepAudit] = []
        for entry in data:
            try:
                audits.append(StepAudit(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StepAudit (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return audits

    def _pass_forensic_optimality(
        self, trace: OrchestratorTrace, acc: "_PipelineAcc"
    ) -> OptimalityJustification | None:
        prompt = assemble_prompt(
            FORENSIC_OPTIMALITY_PROMPT,
            task=trace.task,
            task_properties=trace.task_properties.model_dump(),
            sub_agents=trace.sub_agents,
        )
        raw = self._call(prompt, pass_name="forensic_optimality", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return OptimalityJustification(**obj)
        except Exception as exc:
            log.warning("OptimalityJustification parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: OrchestratorTrace,
        observed: OrchestratorMode,
        optimal: OrchestratorMode,
        mismatch: float,
        indicators: ModeIndicators,
        quality: str,
        step_audits: list[StepAudit],
        optimality: OptimalityJustification | None,
        acc: "_PipelineAcc",
    ) -> list[OrchestratorIntervention]:
        if quality == "well-matched":
            return []
        provisional_profile = self._classify_profile_pattern(
            observed, optimal, mismatch, quality, trace
        )
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            observed_mode=observed,
            optimal_mode=optimal,
            profile_pattern=provisional_profile,
            mode_quality=quality,
            step_audits=[sa.model_dump() for sa in step_audits],
            optimality=optimality.model_dump() if optimality else None,
            indicators=indicators.model_dump(),
            task_properties=trace.task_properties.model_dump(),
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # --- Parsers + coercers -------------------------------------------

    def _coerce_mode(self, raw: Any) -> OrchestratorMode:
        if isinstance(raw, str) and raw.strip() in _VALID_MODES:
            return cast(OrchestratorMode, raw.strip())
        return "hybrid"

    def _coerce_fraction(self, raw: Any) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            return 0.0

    def _parse_indicators(self, raw: Any) -> ModeIndicators:
        if isinstance(raw, dict):
            try:
                return ModeIndicators(**raw)
            except Exception as exc:
                log.warning(
                    "Dropping malformed ModeIndicators (%s); using defaults",
                    type(exc).__name__,
                )
        return ModeIndicators(
            check_in_frequency=0.0,
            autonomy_granted=0.0,
            pre_approval_required=0.0,
            intervention_rate=0.0,
            explanation="(no indicators parsed)",
            evidence_quotes=[],
            confidence=0.5,
        )

    def _parse_interventions(self, raw: str) -> list[OrchestratorIntervention]:
        data = extract_json_array(raw)
        interventions: list[OrchestratorIntervention] = []
        for entry in data:
            try:
                interventions.append(OrchestratorIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed OrchestratorIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _mode_quality(
        self, mismatch: float, raw: str
    ) -> Literal["well-matched", "mild-mismatch", "severe-mismatch"]:
        if isinstance(raw, str) and raw.strip() in (
            "well-matched",
            "mild-mismatch",
            "severe-mismatch",
        ):
            return cast(
                Literal["well-matched", "mild-mismatch", "severe-mismatch"],
                raw.strip(),
            )
        m = max(0.0, min(1.0, float(mismatch)))
        if m <= 0.2:
            return "well-matched"
        if m <= 0.5:
            return "mild-mismatch"
        return "severe-mismatch"

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        observed: OrchestratorMode,
        optimal: OrchestratorMode,
        mismatch: float,
        quality: str,
        trace: OrchestratorTrace,
    ) -> McGregorProfilePattern:
        tp = trace.task_properties

        # Irreversible action under Theory Y is the most dangerous case.
        if observed == "theory_y" and tp.reversibility == "irreversible":
            return "irreversible_action_under_supervision"

        # Regulated workflow under-supervision.
        if tp.regulatory_exposure and observed == "theory_y":
            return "regulated_workflow_under_supervision"

        # Creative task over-supervision.
        if observed == "theory_x" and tp.complexity == "novel" and tp.risk_level == "low":
            return "creative_task_over_supervised"

        # Capability-based.
        if observed == "theory_x" and tp.agent_capability == "proven" and tp.risk_level == "low":
            return "theory_x_on_proven_agent"
        if observed == "theory_y" and tp.agent_capability == "unproven":
            return "theory_y_on_unproven_agent"

        # Risk-based mismatch.
        if observed == "theory_y" and tp.risk_level == "high":
            return "theory_y_on_high_risk"
        if observed == "theory_x" and tp.risk_level == "low":
            return "theory_x_on_low_risk"

        if observed == "hybrid" and quality != "well-matched":
            return "hybrid_misapplied"

        # Well-matched patterns.
        if quality == "well-matched":
            mapping: dict[str, McGregorProfilePattern] = {
                "theory_x": "well_matched_theory_x",
                "theory_y": "well_matched_theory_y",
                "hybrid": "well_matched_hybrid",
            }
            return mapping.get(observed, "indeterminate")

        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: OrchestratorTrace,
        observed: OrchestratorMode,
        profile_pattern: McGregorProfilePattern,
        interventions: list[OrchestratorIntervention],
    ) -> ComposedPatternHandoff:
        provisional = OrchestratorModeDetection(
            trace_id=trace.trace_id,
            observed_mode=observed,
            optimal_mode=observed,
            mode_mismatch=0.0,
            indicators=ModeIndicators(
                check_in_frequency=0.0,
                autonomy_granted=0.0,
                pre_approval_required=0.0,
                intervention_rate=0.0,
                explanation="provisional",
                evidence_quotes=[],
            ),
            mode_quality="mild-mismatch",
            rationale="",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "observed_mode": observed,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
            "intervention_types": [iv.intervention_type for iv in interventions],
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self, interventions: list[OrchestratorIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_mode)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.mode, pb.failure_mode) not in attached:
                attached[(pb.mode, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
OrchestratorModeDetector = McGregorOrchestratorAnalyzer


class McGregorOrchestratorAnalyzerAsync:
    """Async mirror of :class:`McGregorOrchestratorAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: McGregorMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: McGregorMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: OrchestratorTrace,
        *,
        mode: McGregorMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> OrchestratorModeDetection:
        active_mode: McGregorMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = McGregorOrchestratorAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.mcgregor.generator")
_legacy_log.addHandler(logging.NullHandler())
