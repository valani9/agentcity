"""SpanLoadCalculator: multi-mode deterministic span-of-control diagnostic.

Three pipeline modes:
  - quick: metrics only (0 LLM calls)
  - standard: metrics + 1 LLM call for interventions
  - forensic: metrics + 2 deterministic audits + 1 LLM call for interventions

The deterministic metrics + forensic audits never go through the LLM.
The LLM only generates qualitative interventions on top of locked
numbers. Backward-compatible: legacy class name preserved.
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
from .metrics import (
    composite_load_score,
    compute_all_metrics_payload,
    decision_bottleneck_score,
    detect_structural_anomalies,
    estimate_breaking_rate,
)
from .prompts import (
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    SPAN_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    AttachedPlaybook,
    ComposedPatternHandoff,
    CrewLoadTrace,
    LoadAmplificationAudit,
    SpanIntervention,
    SpanLoadAnalysis,
    SpanMetric,
    SpanMode,
    SpanProfilePattern,
    StructuralAnomalyAudit,
    severity_from_load,
)

log = get_logger("agentcity.span_of_control.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


def _roster_lines(trace: CrewLoadTrace) -> str:
    lines: list[str] = []
    for agent in trace.agents:
        reports = ", ".join(agent.reports_to) if agent.reports_to else "(top-level)"
        lines.append(
            f"- {agent.agent_id} | role={agent.role_name} | "
            f"reports_to=[{reports}] | decision_authority={agent.decision_authority}"
        )
    return "\n".join(lines)


def _metrics_table(metrics_payload: dict[str, tuple[float, float, str]]) -> str:
    return "\n".join(
        f"- {name}: value={value:.2f}, normalized={norm:.2f}"
        for name, (value, norm, _) in metrics_payload.items()
    )


class SpanLoadCalculator:
    """Run the deterministic Span-of-Control / Centralization diagnostic."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SpanMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SpanMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: CrewLoadTrace,
        *,
        mode: SpanMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SpanLoadAnalysis:
        active_mode: SpanMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="span_of_control"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[CrewLoadTrace],
        *,
        mode: SpanMode | None = None,
    ) -> Iterator[SpanLoadAnalysis]:
        active_mode: SpanMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="span_of_control"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: CrewLoadTrace,
        mode: SpanMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> SpanLoadAnalysis:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Span-of-Control diagnostic (mode=%s) for crew %s",
            mode,
            trace.crew_id or "<unknown>",
        )

        acc = _PipelineAcc()

        # All metrics computed DETERMINISTICALLY -- no LLM involvement
        metrics_payload, bottleneck_ids = compute_all_metrics_payload(trace)
        metrics = [
            SpanMetric(
                metric=name,  # type: ignore[arg-type]
                value=value,
                normalized_score=norm,
                explanation=explanation,
            )
            for name, (value, norm, explanation) in metrics_payload.items()
        ]
        load_score = composite_load_score(metrics_payload)
        quality = self._load_quality(load_score)

        structural_anomaly_audit: StructuralAnomalyAudit | None = None
        load_amplification_audit: LoadAmplificationAudit | None = None

        interventions: list[SpanIntervention] = []
        if mode == "quick":
            # 0 LLM calls. No interventions beyond what playbooks attach.
            pass
        elif mode == "standard":
            if quality != "well-balanced":
                interventions = self._pass_interventions(
                    trace, metrics_payload, bottleneck_ids, quality, load_score, acc
                )
        else:  # forensic
            structural_anomaly_audit = self._compute_structural_anomaly(trace)
            load_amplification_audit = self._compute_load_amplification(trace, bottleneck_ids)
            if quality != "well-balanced":
                interventions = self._pass_forensic_interventions(
                    trace,
                    metrics_payload,
                    bottleneck_ids,
                    quality,
                    structural_anomaly_audit,
                    load_amplification_audit,
                    acc,
                )

        severity = severity_from_load(load_score)
        profile_pattern = self._classify_profile_pattern(
            metrics_payload, bottleneck_ids, load_amplification_audit, quality
        )

        composition = (
            self._build_composition_handoff(trace, profile_pattern, bottleneck_ids, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = SpanLoadAnalysis(
                    crew_id=trace.crew_id,
                    metrics=metrics,
                    structural_load_score=load_score,
                    structural_load_quality=quality,
                    bottleneck_agent_ids=bottleneck_ids,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return SpanLoadAnalysis(
            crew_id=trace.crew_id,
            metrics=metrics,
            structural_load_score=load_score,
            structural_load_quality=quality,
            bottleneck_agent_ids=bottleneck_ids,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            structural_anomaly_audit=structural_anomaly_audit,
            load_amplification_audit=load_amplification_audit,
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

    # --- Validation + injection ---------------------------------------

    def _validate_trace(self, trace: CrewLoadTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("CrewLoadTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("CrewLoadTrace.outcome cannot be empty.")
        if not trace.agents:
            raise ValueError("CrewLoadTrace.agents cannot be empty.")

    def _scan_injection(self, trace: CrewLoadTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
        for i, agent in enumerate(trace.agents):
            targets.append((f"agents[{i}].role_name", agent.role_name))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in load trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    # --- LLM bookkeeping ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: SpanMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SPAN_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "span_of_control"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Deterministic forensic audits --------------------------------

    def _compute_structural_anomaly(self, trace: CrewLoadTrace) -> StructuralAnomalyAudit:
        data = detect_structural_anomalies(trace.agents)
        return StructuralAnomalyAudit(
            cycles_detected=bool(data["cycles_detected"]),
            cycle_paths=cast(list[list[str]], data["cycle_paths"]),
            orphans=cast(list[str], data["orphans"]),
            multi_parent_agents=cast(list[str], data["multi_parent_agents"]),
            dangling_reports_to=cast(list[str], data["dangling_reports_to"]),
            explanation=(
                "Cycle in reports_to graph -- redesign required."
                if data["cycles_detected"]
                else "No structural anomalies in reports_to graph."
            ),
        )

    def _compute_load_amplification(
        self, trace: CrewLoadTrace, bottleneck_ids: list[str]
    ) -> LoadAmplificationAudit:
        base_score, _ = decision_bottleneck_score(trace.agents, 0.0)
        amplified_score, _ = decision_bottleneck_score(trace.agents, trace.incoming_request_rate)
        breaking_rate = estimate_breaking_rate(
            trace.agents, trace.incoming_request_rate, amplified_score
        )
        return LoadAmplificationAudit(
            incoming_request_rate=trace.incoming_request_rate,
            base_bottleneck_score=base_score,
            amplified_bottleneck_score=amplified_score,
            breaking_rate_estimate=breaking_rate,
            explanation=(
                f"Bottleneck score climbs from {base_score:.2f} (no load) to "
                f"{amplified_score:.2f} at {trace.incoming_request_rate:.1f}/min."
                + (f" Estimated breaking rate: {breaking_rate:.1f}/min." if breaking_rate else "")
                + (
                    f" Bottleneck agents under load: {', '.join(bottleneck_ids)}."
                    if bottleneck_ids
                    else ""
                )
            ),
        )

    # --- LLM passes ---------------------------------------------------

    def _pass_interventions(
        self,
        trace: CrewLoadTrace,
        metrics_payload: dict[str, tuple[float, float, str]],
        bottleneck_ids: list[str],
        load_quality: str,
        load_score: float,
        acc: "_PipelineAcc",
    ) -> list[SpanIntervention]:
        prompt = INTERVENTIONS_PROMPT.format(
            metrics_table=_metrics_table(metrics_payload),
            bottleneck_ids=", ".join(bottleneck_ids) or "(none)",
            load_quality=load_quality,
            load_score=f"{load_score:.2f}",
            roster=_roster_lines(trace),
        )
        raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_interventions(
        self,
        trace: CrewLoadTrace,
        metrics_payload: dict[str, tuple[float, float, str]],
        bottleneck_ids: list[str],
        load_quality: str,
        structural_anomaly: StructuralAnomalyAudit,
        load_amplification: LoadAmplificationAudit,
        acc: "_PipelineAcc",
    ) -> list[SpanIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            roster=_roster_lines(trace),
            metrics_table=_metrics_table(metrics_payload),
            observed_behaviors=trace.observed_behaviors,
            bottleneck_ids=", ".join(bottleneck_ids) or "(none)",
            load_quality=load_quality,
            structural_anomaly=structural_anomaly.model_dump(),
            load_amplification=load_amplification.model_dump(),
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_interventions(self, raw: str) -> list[SpanIntervention]:
        data = extract_json_array(raw)
        interventions: list[SpanIntervention] = []
        for entry in data:
            try:
                interventions.append(SpanIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SpanIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Quality + profile classifier ---------------------------------

    def _load_quality(
        self, load_score: float
    ) -> Literal["well-balanced", "under-stress", "overloaded"]:
        if load_score < 0.3:
            return "well-balanced"
        if load_score < 0.6:
            return "under-stress"
        return "overloaded"

    def _classify_profile_pattern(
        self,
        metrics_payload: dict[str, tuple[float, float, str]],
        bottleneck_ids: list[str],
        load_amplification: LoadAmplificationAudit | None,
        quality: str,
    ) -> SpanProfilePattern:
        if quality == "well-balanced":
            return "well_balanced"

        # Sort metrics by normalized score (worst first)
        sorted_metrics = sorted(metrics_payload.items(), key=lambda kv: kv[1][1], reverse=True)
        severe = [name for name, (_, norm, _) in sorted_metrics if norm >= 0.5]
        worst_name = sorted_metrics[0][0]
        worst_norm = sorted_metrics[0][1][1]

        # Load-amplification is the more specific diagnosis when present
        if (
            load_amplification
            and load_amplification.amplified_bottleneck_score
            > load_amplification.base_bottleneck_score + 0.2
            and bottleneck_ids
        ):
            return "load_amplified_bottleneck"

        if len(severe) >= 4:
            return "broadly_overloaded"

        if worst_name == "decision_bottleneck" and bottleneck_ids:
            return "single_bottleneck"
        if worst_name == "max_span" and worst_norm >= 0.5:
            return "wide_span_orchestrator"
        if worst_name == "hierarchy_depth" and worst_norm >= 0.4:
            return "deep_hierarchy"
        if worst_name == "span_gini" and worst_norm >= 0.4:
            return "imbalanced_supervisors"
        if worst_name == "centralization_index":
            value = metrics_payload["centralization_index"][0]
            if value >= 0.6:
                return "over_centralized"
            if value <= 0.2:
                return "under_centralized"
        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: CrewLoadTrace,
        profile_pattern: SpanProfilePattern,
        bottleneck_ids: list[str],
        interventions: list[SpanIntervention],
    ) -> ComposedPatternHandoff:
        provisional = SpanLoadAnalysis(
            crew_id=trace.crew_id,
            metrics=[],
            structural_load_score=0.5,
            structural_load_quality="under-stress",
            bottleneck_agent_ids=bottleneck_ids,
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "bottleneck_agent_ids": bottleneck_ids,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[SpanIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_metric)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.metric, pb.failure_mode) not in attached:
                attached[(pb.metric, pb.failure_mode)] = pb
        return list(attached.values())


class SpanLoadCalculatorAsync:
    """Async mirror of :class:`SpanLoadCalculator`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SpanMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SpanMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: CrewLoadTrace,
        *,
        mode: SpanMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SpanLoadAnalysis:
        active_mode: SpanMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = SpanLoadCalculator(
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
        "cost_usd",
        "elapsed_ms",
        "llm_calls",
        "tokens_input",
        "tokens_output",
        "tokens_total",
    )

    def __init__(self) -> None:
        self.tokens_input = 0
        self.tokens_output = 0
        self.tokens_total = 0
        self.cost_usd = 0.0
        self.llm_calls = 0
        self.elapsed_ms = 0.0

    def add(
        self,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        elapsed_ms: float,
    ) -> None:
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
    return None


_legacy_log = logging.getLogger("agentcity.span_of_control.generator")
_legacy_log.addHandler(logging.NullHandler())


__all__ = [
    "AsyncLLMClient",
    "LLMClient",
    "SpanLoadCalculator",
    "SpanLoadCalculatorAsync",
]
