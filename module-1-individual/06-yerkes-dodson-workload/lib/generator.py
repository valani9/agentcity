"""YerkesDodsonAnalyzer: multi-mode workload-pressure diagnostic.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``WorkloadDetector`` remains exported as an alias
for ``YerkesDodsonAnalyzer``.
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
    FORENSIC_COGNITIVE_LOAD_PROMPT,
    FORENSIC_CONTEXT_SATURATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_WORKLOAD_PROMPT,
    YERKES_DODSON_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    WORKLOAD_ZONES,
    AgentPerformanceTrace,
    AttachedPlaybook,
    CognitiveLoadAnalysis,
    ComposedPatternHandoff,
    ContextSaturation,
    WorkloadDetection,
    WorkloadIntervention,
    WorkloadProfilePattern,
    WorkloadZone,
    WorkloadZoneEvidence,
    YerkesDodsonMode,
    severity_from_distance,
)

log = get_logger("agentcity.yerkes_dodson.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}

_VALID_FAILURE_MODES = {
    "wandering",
    "focused",
    "corner_cutting",
    "freezing",
    "hallucinating",
    "refusing",
    "unknown",
}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class YerkesDodsonAnalyzer:
    """Run the Yerkes-Dodson Workload diagnostic on an AgentPerformanceTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: YerkesDodsonMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: YerkesDodsonMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentPerformanceTrace,
        *,
        mode: YerkesDodsonMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> WorkloadDetection:
        active_mode: YerkesDodsonMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="yerkes_dodson"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentPerformanceTrace],
        *,
        mode: YerkesDodsonMode | None = None,
    ) -> Iterator[WorkloadDetection]:
        active_mode: YerkesDodsonMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="yerkes_dodson"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentPerformanceTrace,
        mode: YerkesDodsonMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> WorkloadDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Yerkes-Dodson diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        cognitive_load: CognitiveLoadAnalysis | None = None
        context_saturation: ContextSaturation | None = None

        if mode == "quick":
            evidence, observed_zone, distance, failure_mode, top_intervention = self._pass_quick(
                trace, acc
            )
            interventions = [top_intervention] if top_intervention else []
        elif mode == "standard":
            evidence, observed_zone, distance, failure_mode, interventions = self._pass_standard(
                trace, acc
            )
        elif mode == "forensic":
            evidence, observed_zone, distance, failure_mode, _ = self._pass_standard(trace, acc)
            cognitive_load = self._pass_forensic_cognitive_load(trace, acc)
            context_saturation = self._pass_forensic_context_saturation(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                evidence,
                observed_zone,
                failure_mode,
                cognitive_load,
                context_saturation,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown YerkesDodsonMode: {mode!r}")

        # Deterministic context-saturation augmentation if we have token data
        # and forensic didn't already populate it.
        if context_saturation is None:
            context_saturation = self._compute_context_saturation_from_pressure(trace)

        profile_pattern = self._classify_profile_pattern(
            evidence,
            observed_zone,
            failure_mode,
            cognitive_load,
            context_saturation,
            trace,
        )
        severity = severity_from_distance(distance)

        composition = (
            self._build_composition_handoff(
                trace, observed_zone, failure_mode, profile_pattern, interventions
            )
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(interventions, observed_zone) if self.playbooks_enabled else []
        )

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = WorkloadDetection(
                    observed_zone=observed_zone,
                    zone_evidence=evidence,
                    distance_from_optimal=distance,
                    failure_mode=failure_mode,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = WorkloadDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            observed_zone=observed_zone,
            zone_evidence=evidence,
            distance_from_optimal=distance,
            failure_mode=failure_mode,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            cognitive_load_analysis=cognitive_load,
            context_saturation=context_saturation,
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
            "Yerkes-Dodson done mode=%s zone=%s failure=%s profile=%s distance=%.2f elapsed=%.0fms",
            mode,
            observed_zone,
            failure_mode,
            profile_pattern,
            distance,
            elapsed_ms,
        )
        return detection

    # --- Validation ----------------------------------------------------

    def _validate_trace(self, trace: AgentPerformanceTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentPerformanceTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentPerformanceTrace.outcome cannot be empty.")
        if not trace.observed_behaviors:
            raise ValueError("AgentPerformanceTrace.observed_behaviors cannot be empty.")

    def _scan_injection(self, trace: AgentPerformanceTrace) -> bool:
        targets = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, behavior in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", behavior))
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

    def _serialize_trace(self, trace: AgentPerformanceTrace) -> str:
        p = trace.pressure
        return (
            f"task: {trace.task}\n"
            f"deadline_pressure: {p.deadline_pressure}\n"
            f"budget_pressure: {p.budget_pressure}\n"
            f"task_complexity: {p.task_complexity}\n"
            f"error_visibility: {p.error_visibility}\n"
            f"retry_cap: {p.retry_cap if p.retry_cap is not None else 'unbounded'}\n"
            f"context_size_tokens: {p.context_size_tokens or 'unknown'}\n"
            f"context_window_size: {p.context_window_size or 'unknown'}\n"
            f"interrupt_frequency: {p.interrupt_frequency}\n"
            f"extraneous_load_indicators: {p.extraneous_load_indicators}\n"
            f"observed_behaviors: {trace.observed_behaviors}\n"
            f"outcome: {trace.outcome}\n"
            f"success: {trace.success}"
        )

    # --- LLM call helper ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: YerkesDodsonMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=YERKES_DODSON_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "yerkes_dodson"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(
        self, trace: AgentPerformanceTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[WorkloadZoneEvidence],
        WorkloadZone,
        float,
        Literal[
            "wandering",
            "focused",
            "corner_cutting",
            "freezing",
            "hallucinating",
            "refusing",
            "unknown",
        ],
        WorkloadIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            pressure=trace.pressure.model_dump(),
            observed_behaviors=trace.observed_behaviors,
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("zone_evidence", []))
        observed_zone = self._coerce_zone(obj.get("observed_zone"), evidence)
        distance = self._coerce_fraction(obj.get("distance_from_optimal"), evidence)
        failure_mode = self._coerce_failure_mode(obj.get("failure_mode"), observed_zone)
        top_intervention: WorkloadIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry and observed_zone != "optimal":
            try:
                top_intervention = WorkloadIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, observed_zone, distance, failure_mode, top_intervention

    def _pass_standard(
        self, trace: AgentPerformanceTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[WorkloadZoneEvidence],
        WorkloadZone,
        float,
        Literal[
            "wandering",
            "focused",
            "corner_cutting",
            "freezing",
            "hallucinating",
            "refusing",
            "unknown",
        ],
        list[WorkloadIntervention],
    ]:
        prompt = assemble_prompt(
            STANDARD_WORKLOAD_PROMPT,
            task=trace.task,
            pressure=trace.pressure.model_dump(),
            observed_behaviors=trace.observed_behaviors,
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._call(prompt, pass_name="standard", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("zone_evidence", []))
        observed_zone = self._coerce_zone(obj.get("observed_zone"), evidence)
        distance = self._coerce_fraction(obj.get("distance_from_optimal"), evidence)
        failure_mode = self._coerce_failure_mode(obj.get("failure_mode"), observed_zone)
        interventions = self._parse_interventions(obj.get("interventions", []), observed_zone)
        return evidence, observed_zone, distance, failure_mode, interventions

    def _pass_forensic_cognitive_load(
        self, trace: AgentPerformanceTrace, acc: "_PipelineAcc"
    ) -> CognitiveLoadAnalysis | None:
        p = trace.pressure
        prompt = assemble_prompt(
            FORENSIC_COGNITIVE_LOAD_PROMPT,
            task=trace.task,
            pressure=p.model_dump(),
            context_size_tokens=p.context_size_tokens or 0,
            context_window_size=p.context_window_size or 0,
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_cognitive_load", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CognitiveLoadAnalysis(**obj)
        except Exception as exc:
            log.warning("CognitiveLoadAnalysis parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_context_saturation(
        self, trace: AgentPerformanceTrace, acc: "_PipelineAcc"
    ) -> ContextSaturation | None:
        p = trace.pressure
        prompt = assemble_prompt(
            FORENSIC_CONTEXT_SATURATION_PROMPT,
            context_size_tokens=p.context_size_tokens or 0,
            context_window_size=p.context_window_size or 0,
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_context_saturation", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return self._compute_context_saturation_from_pressure(trace)
        try:
            return ContextSaturation(**obj)
        except Exception as exc:
            log.warning("ContextSaturation parse error: %s", type(exc).__name__)
            return self._compute_context_saturation_from_pressure(trace)

    def _pass_forensic_interventions(
        self,
        trace: AgentPerformanceTrace,
        evidence: list[WorkloadZoneEvidence],
        observed_zone: WorkloadZone,
        failure_mode: str,
        cognitive_load: CognitiveLoadAnalysis | None,
        context_saturation: ContextSaturation | None,
        acc: "_PipelineAcc",
    ) -> list[WorkloadIntervention]:
        if observed_zone == "optimal":
            return []
        profile = self._classify_profile_pattern(
            evidence, observed_zone, failure_mode, cognitive_load, context_saturation, trace
        )
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            observed_zone=observed_zone,
            failure_mode=failure_mode,
            profile_pattern=profile,
            cognitive_load=cognitive_load.model_dump() if cognitive_load else None,
            context_saturation=(context_saturation.model_dump() if context_saturation else None),
            zone_evidence=[e.model_dump() for e in evidence],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw, observed_zone)

    # --- Parsers + coercers -------------------------------------------

    def _parse_evidence(self, raw: Any) -> list[WorkloadZoneEvidence]:
        evidence: list[WorkloadZoneEvidence] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(WorkloadZoneEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed WorkloadZoneEvidence (%s): %r",
                        type(exc).__name__,
                        entry,
                    )

        seen = {ev.zone for ev in evidence}
        for zone in WORKLOAD_ZONES:
            if zone not in seen:
                evidence.append(
                    WorkloadZoneEvidence(
                        zone=zone,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                        confidence=0.5,
                    )
                )
        order = {z: i for i, z in enumerate(WORKLOAD_ZONES)}
        evidence.sort(key=lambda ev: order.get(ev.zone, len(WORKLOAD_ZONES)))
        return evidence

    def _parse_interventions(self, raw: Any, observed_zone: str) -> list[WorkloadIntervention]:
        if observed_zone == "optimal":
            return []
        if isinstance(raw, str):
            data = extract_json_array(raw)
        elif isinstance(raw, list):
            data = raw
        else:
            data = []
        interventions: list[WorkloadIntervention] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            try:
                interventions.append(WorkloadIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed WorkloadIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _coerce_zone(self, raw: Any, evidence: list[WorkloadZoneEvidence]) -> WorkloadZone:
        if isinstance(raw, str) and raw.strip() in WORKLOAD_ZONES:
            return cast(WorkloadZone, raw.strip())
        if not evidence:
            return "optimal"
        max_score = max(ev.score for ev in evidence)
        if max_score == 0.0:
            return "optimal"
        top = max(evidence, key=lambda ev: ev.score)
        return top.zone

    def _coerce_fraction(self, raw: Any, evidence: list[WorkloadZoneEvidence]) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not evidence:
            return 0.0
        max_score = max(ev.score for ev in evidence)
        if max_score == 0.0:
            return 0.0
        optimal_ev = next((ev for ev in evidence if ev.zone == "optimal"), None)
        if optimal_ev is None:
            return 0.5
        return round(max(0.0, min(1.0, 1.0 - optimal_ev.score)), 2)

    def _coerce_failure_mode(
        self, raw: Any, observed_zone: str
    ) -> Literal[
        "wandering",
        "focused",
        "corner_cutting",
        "freezing",
        "hallucinating",
        "refusing",
        "unknown",
    ]:
        if isinstance(raw, str) and raw.strip() in _VALID_FAILURE_MODES:
            return cast(
                Literal[
                    "wandering",
                    "focused",
                    "corner_cutting",
                    "freezing",
                    "hallucinating",
                    "refusing",
                    "unknown",
                ],
                raw.strip(),
            )
        if observed_zone == "optimal":
            return "focused"
        if observed_zone == "under_pressure":
            return "wandering"
        if observed_zone == "over_pressure":
            return "corner_cutting"
        return "unknown"

    # --- Deterministic helpers ----------------------------------------

    def _compute_context_saturation_from_pressure(
        self, trace: AgentPerformanceTrace
    ) -> ContextSaturation | None:
        p = trace.pressure
        if not p.context_window_size or p.context_window_size <= 0:
            return None
        ctx_size = p.context_size_tokens or 0
        ratio = max(0.0, min(1.0, ctx_size / float(p.context_window_size)))
        if ratio >= 0.85:
            risk: Literal["low", "moderate", "high"] = "high"
        elif ratio >= 0.5:
            risk = "moderate"
        else:
            risk = "low"
        # naive split: noise ~ extraneous_load_indicators count, useful ~ rest.
        noise_signal = len(p.extraneous_load_indicators)
        estimated_noise = int(min(ctx_size, noise_signal * 200))
        estimated_useful = max(0, ctx_size - estimated_noise)
        return ContextSaturation(
            saturation_ratio=round(ratio, 4),
            lost_in_middle_risk=risk,
            estimated_useful_tokens=estimated_useful,
            estimated_noise_tokens=estimated_noise,
            notes=(
                "Auto-derived from pressure.context_size_tokens vs "
                "pressure.context_window_size (Liu et al. 2024)."
            ),
        )

    def _classify_profile_pattern(
        self,
        evidence: list[WorkloadZoneEvidence],
        observed_zone: str,
        failure_mode: str,
        cognitive_load: CognitiveLoadAnalysis | None,
        context_saturation: ContextSaturation | None,
        trace: AgentPerformanceTrace,
    ) -> WorkloadProfilePattern:
        scores: dict[str, float] = {str(ev.zone): ev.score for ev in evidence}
        under = scores.get("under_pressure", 0.0)
        opt = scores.get("optimal", 0.0)
        over = scores.get("over_pressure", 0.0)

        # Highest-priority special cases (context + CLT specific patterns).
        if context_saturation and context_saturation.saturation_ratio >= 0.7:
            return "context_saturation"

        if cognitive_load:
            if (
                cognitive_load.extraneous_load >= 0.6
                and cognitive_load.dominant_component == "extraneous"
            ):
                return "extraneous_load_overload"
            if (
                cognitive_load.intrinsic_load >= 0.7
                and cognitive_load.dominant_component == "intrinsic"
            ):
                return "intrinsic_load_overload"

        if observed_zone == "optimal" and opt >= 0.5:
            return "optimal_zone"

        if observed_zone == "under_pressure":
            if failure_mode == "wandering":
                return "under_pressure_wandering"
            return "under_pressure_drift"

        if observed_zone == "over_pressure":
            if failure_mode == "corner_cutting":
                return "over_pressure_corner_cutting"
            if failure_mode == "hallucinating":
                return "over_pressure_hallucinating"
            if failure_mode == "freezing":
                return "over_pressure_freezing"
            if failure_mode == "refusing":
                return "over_pressure_refusing"
            # over_pressure with unrecognised failure mode -- pick by score.
            if over >= 0.6:
                return "over_pressure_corner_cutting"

        # All-zero score response = optimal fallback.
        if max(under, opt, over) < 0.2:
            return "optimal_zone"

        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentPerformanceTrace,
        observed_zone: WorkloadZone,
        failure_mode: str,
        profile_pattern: WorkloadProfilePattern,
        interventions: list[WorkloadIntervention],
    ) -> ComposedPatternHandoff:
        provisional = WorkloadDetection(
            observed_zone=observed_zone,
            zone_evidence=[],
            distance_from_optimal=0.0,
            failure_mode=failure_mode,  # type: ignore[arg-type]
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "observed_zone": observed_zone,
            "failure_mode": failure_mode,
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
        self,
        interventions: list[WorkloadIntervention],
        observed_zone: WorkloadZone,
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            pb = find_playbook_for_intervention(observed_zone, iv.intervention_type)
            if pb is not None and (pb.zone, pb.failure_mode) not in attached:
                attached[(pb.zone, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
WorkloadDetector = YerkesDodsonAnalyzer


class YerkesDodsonAnalyzerAsync:
    """Async mirror of :class:`YerkesDodsonAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: YerkesDodsonMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: YerkesDodsonMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentPerformanceTrace,
        *,
        mode: YerkesDodsonMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> WorkloadDetection:
        active_mode: YerkesDodsonMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = YerkesDodsonAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.yerkes_dodson.generator")
_legacy_log.addHandler(logging.NullHandler())
