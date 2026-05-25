"""ReappraisalAnalyzer: Gross's emotion-regulation strategies for AI agents.

Three pipeline modes (quick / standard / forensic) wired with full
v0.1.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine, Iterable, Iterator
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from vstack.aar import (
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
    FORENSIC_PROCESS_MODEL_PROMPT,
    FORENSIC_STRATEGY_CHOICE_PROMPT,
    GROSS_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_STRATEGY_PROMPT,
    assemble_prompt,
)
from .schema import (
    REGULATION_STRATEGIES,
    AgentRegulationTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    ProcessModelPhaseEvidence,
    ReappraisalMode,
    ReappraisalProfilePattern,
    RegulationDetection,
    RegulationIntervention,
    Strategy,
    StrategyChoiceAudit,
    StrategyEvidence,
    severity_from_adaptivity,
)

log = get_logger("vstack.cognitive_reappraisal.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class ReappraisalAnalyzer:
    """Run the Cognitive Reappraisal diagnostic on an AgentRegulationTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ReappraisalMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ReappraisalMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentRegulationTrace,
        *,
        mode: ReappraisalMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> RegulationDetection:
        active_mode: ReappraisalMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="cognitive_reappraisal"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentRegulationTrace],
        *,
        mode: ReappraisalMode | None = None,
    ) -> Iterator[RegulationDetection]:
        active_mode: ReappraisalMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="cognitive_reappraisal"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentRegulationTrace,
        mode: ReappraisalMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> RegulationDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Reappraisal diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        process_model_phases: list[ProcessModelPhaseEvidence] = []
        strategy_choice_audit: StrategyChoiceAudit | None = None

        if mode == "quick":
            evidence, dominant, adaptivity, top_intervention = self._pass_quick(trace, acc)
            interventions = [top_intervention] if top_intervention else []
        elif mode == "standard":
            evidence, dominant, adaptivity = self._pass_standard_strategy(trace, acc)
            interventions = self._pass_standard_interventions(
                trace, evidence, dominant, adaptivity, acc
            )
        elif mode == "forensic":
            evidence, dominant, adaptivity = self._pass_standard_strategy(trace, acc)
            process_model_phases = self._pass_forensic_process_model(trace, acc)
            strategy_choice_audit = self._pass_forensic_strategy_choice(
                trace, evidence, dominant, acc
            )
            interventions = self._pass_forensic_interventions(
                trace, evidence, dominant, strategy_choice_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown ReappraisalMode: {mode!r}")

        profile_pattern = self._classify_profile_pattern(evidence, dominant, adaptivity, trace)
        severity = severity_from_adaptivity(adaptivity, dominant)  # type: ignore[arg-type]

        composition = (
            self._build_composition_handoff(trace, dominant, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = RegulationDetection(
                    strategy_evidence=evidence,
                    dominant_strategy=dominant,
                    adaptivity=adaptivity,  # type: ignore[arg-type]
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = RegulationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            strategy_evidence=evidence,
            dominant_strategy=dominant,
            adaptivity=adaptivity,  # type: ignore[arg-type]
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            process_model_phases=process_model_phases,
            strategy_choice_audit=strategy_choice_audit,
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
            "Reappraisal done mode=%s dominant=%s adaptivity=%s profile=%s elapsed=%.0fms",
            mode,
            dominant,
            adaptivity,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    def _validate_trace(self, trace: AgentRegulationTrace) -> None:
        if not trace.user_input or not trace.user_input.strip():
            raise ValueError("AgentRegulationTrace.user_input cannot be empty.")
        if not trace.agent_response or not trace.agent_response.strip():
            raise ValueError("AgentRegulationTrace.agent_response cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentRegulationTrace.outcome cannot be empty.")

    def _scan_injection(self, trace: AgentRegulationTrace) -> bool:
        targets = [
            ("user_input", trace.user_input),
            ("agent_response", trace.agent_response),
            ("agent_internal_state", trace.agent_internal_state),
            ("outcome", trace.outcome),
        ]
        hit_count = 0
        for field, value in targets:
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

    def _serialize_trace(self, trace: AgentRegulationTrace) -> str:
        return (
            f"user_input: {trace.user_input}\n"
            f"user_emotion: {trace.user_emotion_label} (intensity {trace.user_emotion_intensity})\n"
            f"pushback_detected: {trace.pushback_detected}\n"
            f"agent_response: {trace.agent_response}\n"
            f"agent_internal_state: {trace.agent_internal_state}\n"
            f"outcome: {trace.outcome}\n"
            f"success: {trace.success}"
        )

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: ReappraisalMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=GROSS_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "cognitive_reappraisal"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_quick(
        self, trace: AgentRegulationTrace, acc: "_PipelineAcc"
    ) -> tuple[list[StrategyEvidence], Strategy, str, RegulationIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            user_input=trace.user_input,
            user_emotion_label=trace.user_emotion_label,
            user_emotion_intensity=trace.user_emotion_intensity,
            pushback_detected=trace.pushback_detected,
            agent_response=trace.agent_response,
            agent_internal_state=trace.agent_internal_state,
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_strategy_evidence(obj.get("strategy_evidence", []))
        dominant = self._coerce_dominant(obj.get("dominant_strategy"), evidence)
        adaptivity = self._coerce_adaptivity(obj.get("adaptivity"), dominant, evidence)
        top_intervention: RegulationIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_intervention = RegulationIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, dominant, adaptivity, top_intervention

    def _pass_standard_strategy(
        self, trace: AgentRegulationTrace, acc: "_PipelineAcc"
    ) -> tuple[list[StrategyEvidence], Strategy, str]:
        prompt = assemble_prompt(
            STANDARD_STRATEGY_PROMPT,
            user_input=trace.user_input,
            user_emotion_label=trace.user_emotion_label,
            user_emotion_intensity=trace.user_emotion_intensity,
            pushback_detected=trace.pushback_detected,
            agent_response=trace.agent_response,
            agent_internal_state=trace.agent_internal_state,
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._call(prompt, pass_name="standard_strategy", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_strategy_evidence(obj.get("strategy_evidence", []))
        dominant = self._coerce_dominant(obj.get("dominant_strategy"), evidence)
        adaptivity = self._coerce_adaptivity(obj.get("adaptivity"), dominant, evidence)
        return evidence, dominant, adaptivity

    def _pass_standard_interventions(
        self,
        trace: AgentRegulationTrace,
        evidence: list[StrategyEvidence],
        dominant: Strategy,
        adaptivity: str,
        acc: "_PipelineAcc",
    ) -> list[RegulationIntervention]:
        if adaptivity == "adaptive":
            return []
        profile = self._classify_profile_pattern(evidence, dominant, adaptivity, trace)
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            dominant_strategy=dominant,
            adaptivity=adaptivity,
            profile_pattern=profile,
            strategy_evidence=[e.model_dump() for e in evidence],
            trace_summary=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_process_model(
        self, trace: AgentRegulationTrace, acc: "_PipelineAcc"
    ) -> list[ProcessModelPhaseEvidence]:
        prompt = assemble_prompt(
            FORENSIC_PROCESS_MODEL_PROMPT,
            trace_summary=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="forensic_process_model", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        phases: list[ProcessModelPhaseEvidence] = []
        for entry in data:
            try:
                phases.append(ProcessModelPhaseEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed ProcessModelPhaseEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return phases

    def _pass_forensic_strategy_choice(
        self,
        trace: AgentRegulationTrace,
        evidence: list[StrategyEvidence],
        dominant: Strategy,
        acc: "_PipelineAcc",
    ) -> StrategyChoiceAudit | None:
        prompt = assemble_prompt(
            FORENSIC_STRATEGY_CHOICE_PROMPT,
            intensity=trace.user_emotion_intensity,
            dominant_strategy=dominant,
            strategy_evidence=[e.model_dump() for e in evidence],
        )
        raw = self._call(prompt, pass_name="forensic_strategy_choice", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return StrategyChoiceAudit(**obj)
        except Exception as exc:
            log.warning("Forensic strategy_choice parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentRegulationTrace,
        evidence: list[StrategyEvidence],
        dominant: Strategy,
        choice_audit: StrategyChoiceAudit | None,
        acc: "_PipelineAcc",
    ) -> list[RegulationIntervention]:
        profile = self._classify_profile_pattern(evidence, dominant, "maladaptive", trace)
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant_strategy=dominant,
            profile_pattern=profile,
            choice_audit=choice_audit.model_dump() if choice_audit else None,
            strategy_evidence=[e.model_dump() for e in evidence],
            trace_summary=self._serialize_trace(trace),
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_strategy_evidence(self, raw_list: list[Any]) -> list[StrategyEvidence]:
        evidence: list[StrategyEvidence] = []
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(StrategyEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StrategyEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        seen = {e.strategy for e in evidence}
        for s in REGULATION_STRATEGIES:
            if s not in seen:
                evidence.append(
                    StrategyEvidence(
                        strategy=s,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed.",
                        confidence=0.5,
                    )
                )
        order = {s: i for i, s in enumerate(REGULATION_STRATEGIES)}
        evidence.sort(key=lambda e: order.get(e.strategy, len(REGULATION_STRATEGIES)))
        return evidence

    def _parse_interventions(self, raw: str) -> list[RegulationIntervention]:
        data = extract_json_array(raw)
        interventions: list[RegulationIntervention] = []
        for entry in data:
            try:
                interventions.append(RegulationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RegulationIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _coerce_dominant(self, llm_label: Any, evidence: list[StrategyEvidence]) -> Strategy:
        if isinstance(llm_label, str) and llm_label in REGULATION_STRATEGIES:
            return cast(Strategy, llm_label)
        if not evidence:
            return "none"
        top = max(evidence, key=lambda e: e.score)
        if top.score < 0.3:
            return "none"
        return top.strategy

    def _coerce_adaptivity(
        self,
        llm_label: Any,
        dominant: Strategy,
        evidence: list[StrategyEvidence],
    ) -> Literal["adaptive", "mixed", "maladaptive"]:
        if isinstance(llm_label, str) and llm_label in {
            "adaptive",
            "mixed",
            "maladaptive",
        }:
            return cast(Literal["adaptive", "mixed", "maladaptive"], llm_label)
        if dominant == "reappraisal":
            return "adaptive"
        if dominant in {"suppression", "rumination", "avoidance"}:
            return "maladaptive"
        return "mixed"

    def _classify_profile_pattern(
        self,
        evidence: list[StrategyEvidence],
        dominant: Strategy,
        adaptivity: str,
        trace: AgentRegulationTrace,
    ) -> ReappraisalProfilePattern:
        scores = {e.strategy: e.score for e in evidence}
        reapp = scores.get("reappraisal", 0.0)
        supp = scores.get("suppression", 0.0)
        rum = scores.get("rumination", 0.0)
        avoid = scores.get("avoidance", 0.0)
        expr = scores.get("expression", 0.0)

        if max(reapp, supp, rum, avoid, expr) < 0.2:
            return "no_regulation"

        if trace.pushback_detected and supp >= 0.5:
            return "suppression_under_pushback"

        if supp >= 0.6:
            return "suppression_dominant"

        if rum >= 0.6:
            rum_ev = next((e for e in evidence if e.strategy == "rumination"), None)
            if rum_ev and rum_ev.rumination_flavor == "reflection":
                return "rumination_reflective"
            if rum_ev and rum_ev.rumination_flavor == "brooding":
                return "rumination_brooding"
            return "rumination_loop"

        if avoid >= 0.6:
            return "avoidance_pivot"

        if expr >= 0.6 and reapp < 0.3 and supp < 0.3:
            return "expression_only"

        if reapp >= 0.7 and supp < 0.3 and rum < 0.3 and avoid < 0.3:
            return "reappraisal_skilled"

        if reapp >= 0.3 and supp < 0.4 and rum < 0.4 and avoid < 0.4:
            return "reappraisal_developing"

        above_threshold = sum(1 for s in (reapp, supp, rum, avoid, expr) if s >= 0.4)
        if above_threshold >= 2:
            return "mixed_unstable"

        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: AgentRegulationTrace,
        dominant: Strategy,
        profile_pattern: ReappraisalProfilePattern,
        interventions: list[RegulationIntervention],
    ) -> ComposedPatternHandoff:
        provisional = RegulationDetection(
            strategy_evidence=[],
            dominant_strategy=dominant,
            adaptivity="mixed",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_strategy": dominant,
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
        self, interventions: list[RegulationIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            pb = find_playbook_for_intervention(iv.target_strategy, iv.intervention_type)
            if pb is not None and (pb.strategy, pb.failure_mode) not in attached:
                attached[(pb.strategy, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
ReappraisalDetector = ReappraisalAnalyzer


class ReappraisalAnalyzerAsync:
    """Async mirror of :class:`ReappraisalAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ReappraisalMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ReappraisalMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentRegulationTrace,
        *,
        mode: ReappraisalMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> RegulationDetection:
        active_mode: ReappraisalMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = ReappraisalAnalyzer(
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


_legacy_log = logging.getLogger("vstack.cognitive_reappraisal.generator")
_legacy_log.addHandler(logging.NullHandler())
