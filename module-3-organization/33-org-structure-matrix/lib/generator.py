"""StructureMatrixAnalyzer: multi-mode Org-Structure Matrix audit.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: legacy class name preserved.
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
    FORENSIC_BOTTLENECK_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_REPORTING_GRAPH_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_STRUCTURE_PROMPT,
    STRUCTURE_PROMPT,
    STRUCTURE_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    STRUCTURE_DIMENSIONS,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CrewStructureTrace,
    DecisionBottleneckAudit,
    ReportingGraphAudit,
    StructureAnalysis,
    StructureArchetype,
    StructureDimensionScore,
    StructureIntervention,
    StructureMode,
    StructureProfilePattern,
    severity_from_misfit,
)

log = get_logger("vstack.org_structure.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}

_VALID_ARCHETYPES = {
    "flat-peer",
    "hierarchical",
    "centralized-functional",
    "decentralized-product",
    "matrix",
    "mixed",
}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


def _roster_lines(trace: CrewStructureTrace) -> str:
    lines: list[str] = []
    for agent in trace.agents:
        reports = ", ".join(agent.reports_to) if agent.reports_to else "(top-level)"
        lines.append(
            f"- {agent.agent_id} | role={agent.role_name} | "
            f"reports_to=[{reports}] | grouped_by={agent.grouped_by} | "
            f"decision_authority={agent.decision_authority}"
        )
    return "\n".join(lines)


class StructureMatrixAnalyzer:
    """Run the Org-Structure Matrix diagnostic on a CrewStructureTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: StructureMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: StructureMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: CrewStructureTrace,
        *,
        mode: StructureMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> StructureAnalysis:
        active_mode: StructureMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="org_structure"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[CrewStructureTrace],
        *,
        mode: StructureMode | None = None,
    ) -> Iterator[StructureAnalysis]:
        active_mode: StructureMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="org_structure"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: CrewStructureTrace,
        mode: StructureMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> StructureAnalysis:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Org-Structure Matrix audit (mode=%s) for crew %s",
            mode,
            trace.crew_id or "<unknown>",
        )

        acc = _PipelineAcc()
        reporting_graph_audit: ReportingGraphAudit | None = None
        decision_bottleneck_audit: DecisionBottleneckAudit | None = None

        if mode == "quick":
            data = self._pass_quick(trace, acc)
        else:
            data = self._pass_structure(trace, acc=acc)

        dimensions = self._coerce_dimensions(data.get("dimensions", []))
        archetype = self._coerce_archetype(data.get("archetype"))
        overall_fit = self._compute_overall_fit(dimensions, data.get("overall_fit"))
        biggest_gap = self._coerce_biggest_gap(data.get("biggest_gap"), dimensions)
        fit_quality = self._fit_quality(
            overall_fit, str(data.get("fit_quality", "")).strip().lower()
        )

        if mode == "quick":
            interventions: list[StructureIntervention] = []
            top_iv_entry = data.get("top_intervention")
            if top_iv_entry:
                try:
                    interventions.append(StructureIntervention(**top_iv_entry))
                except Exception as exc:
                    log.warning(
                        "Quick top_intervention parse error: %s",
                        type(exc).__name__,
                    )
        elif mode == "standard":
            interventions = self._pass_interventions(
                dimensions, archetype, biggest_gap, fit_quality, trace.task_class, acc=acc
            )
        else:  # forensic
            reporting_graph_audit = self._pass_forensic_reporting_graph(trace, acc)
            decision_bottleneck_audit = self._pass_forensic_bottleneck(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                dimensions,
                archetype,
                biggest_gap,
                fit_quality,
                reporting_graph_audit,
                decision_bottleneck_audit,
                acc,
            )

        misfit = 1.0 - overall_fit
        severity = severity_from_misfit(misfit)
        profile_pattern = self._classify_profile_pattern(
            dimensions, biggest_gap, archetype, fit_quality, trace.task_class
        )

        composition = (
            self._build_composition_handoff(
                trace, profile_pattern, biggest_gap, archetype, interventions
            )
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = StructureAnalysis(
                    crew_id=trace.crew_id,
                    task_class=trace.task_class,
                    archetype=archetype,
                    dimensions=dimensions,
                    overall_fit=overall_fit,
                    fit_quality=fit_quality,
                    biggest_gap=biggest_gap,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return StructureAnalysis(
            crew_id=trace.crew_id,
            task_class=trace.task_class,
            archetype=archetype,
            dimensions=dimensions,
            overall_fit=overall_fit,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            reporting_graph_audit=reporting_graph_audit,
            decision_bottleneck_audit=decision_bottleneck_audit,
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

    def _validate_trace(self, trace: CrewStructureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("CrewStructureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("CrewStructureTrace.outcome cannot be empty.")
        if not trace.agents:
            raise ValueError("CrewStructureTrace.agents cannot be empty.")

    def _scan_injection(self, trace: CrewStructureTrace) -> bool:
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
                    "prompt-injection pattern in structure trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    # --- LLM bookkeeping ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: StructureMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=STRUCTURE_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "org_structure"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- LLM passes ---------------------------------------------------

    def _pass_structure(
        self,
        trace: CrewStructureTrace,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = STRUCTURE_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            outcome=trace.outcome,
            success=trace.success,
            n_agents=len(trace.agents),
            roster=_roster_lines(trace),
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
        )
        if acc is None:
            raw = self._complete(prompt, system=STRUCTURE_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="structure", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, trace: CrewStructureTrace, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_STRUCTURE_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            outcome=trace.outcome,
            success=trace.success,
            n_agents=len(trace.agents),
            roster=_roster_lines(trace),
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_interventions(
        self,
        dimensions: list[StructureDimensionScore],
        archetype: str,
        biggest_gap: str,
        fit_quality: str,
        task_class: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[StructureIntervention]:
        if fit_quality == "well-fit":
            return []
        evidence_text = json.dumps([d.model_dump() for d in dimensions], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            task_class=task_class,
            archetype=archetype,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            evidence=evidence_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=STRUCTURE_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_reporting_graph(
        self, trace: CrewStructureTrace, acc: "_PipelineAcc"
    ) -> ReportingGraphAudit | None:
        prompt = assemble_prompt(
            FORENSIC_REPORTING_GRAPH_PROMPT,
            n_agents=len(trace.agents),
            roster=_roster_lines(trace),
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_reporting_graph", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ReportingGraphAudit(**obj)
        except Exception as exc:
            log.warning("ReportingGraphAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_bottleneck(
        self, trace: CrewStructureTrace, acc: "_PipelineAcc"
    ) -> DecisionBottleneckAudit | None:
        prompt = assemble_prompt(
            FORENSIC_BOTTLENECK_PROMPT,
            task_class=trace.task_class,
            roster=_roster_lines(trace),
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_bottleneck", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return DecisionBottleneckAudit(**obj)
        except Exception as exc:
            log.warning("DecisionBottleneckAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: CrewStructureTrace,
        dimensions: list[StructureDimensionScore],
        archetype: str,
        biggest_gap: str,
        fit_quality: str,
        reporting_graph_audit: ReportingGraphAudit | None,
        decision_bottleneck_audit: DecisionBottleneckAudit | None,
        acc: "_PipelineAcc",
    ) -> list[StructureIntervention]:
        if fit_quality == "well-fit":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            task_class=trace.task_class,
            archetype=archetype,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            roster=_roster_lines(trace),
            observed_behaviors=trace.observed_behaviors,
            reporting_graph=reporting_graph_audit.model_dump() if reporting_graph_audit else None,
            decision_bottleneck=decision_bottleneck_audit.model_dump()
            if decision_bottleneck_audit
            else None,
            evidence=[d.model_dump() for d in dimensions],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_interventions(self, raw: str) -> list[StructureIntervention]:
        data = extract_json_array(raw)
        interventions: list[StructureIntervention] = []
        for entry in data:
            try:
                interventions.append(StructureIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StructureIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Coercion helpers ---------------------------------------------

    def _coerce_dimensions(self, raw: list[Any]) -> list[StructureDimensionScore]:
        dims: list[StructureDimensionScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                dims.append(StructureDimensionScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StructureDimensionScore (%s)",
                    type(exc).__name__,
                )

        seen = {d.dimension for d in dims}
        for dim in STRUCTURE_DIMENSIONS:
            if dim not in seen:
                dims.append(
                    StructureDimensionScore(
                        dimension=dim,  # type: ignore[arg-type]
                        observed_score=0.0,
                        target_score=0.5,
                        fit_score=0.5,
                        explanation="No evidence observed for this dimension.",
                        evidence_quotes=[],
                    )
                )
        order = {d: i for i, d in enumerate(STRUCTURE_DIMENSIONS)}
        dims.sort(key=lambda d: order.get(d.dimension, len(STRUCTURE_DIMENSIONS)))
        return dims

    def _compute_overall_fit(self, dimensions: list[StructureDimensionScore], raw: Any) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not dimensions:
            return 0.0
        mean = sum(d.fit_score for d in dimensions) / len(dimensions)
        return round(max(0.0, min(1.0, mean)), 2)

    def _coerce_archetype(self, raw: Any) -> StructureArchetype:
        if isinstance(raw, str) and raw.strip() in _VALID_ARCHETYPES:
            return raw.strip()  # type: ignore[return-value]
        return "mixed"

    def _coerce_biggest_gap(
        self, raw: Any, dimensions: list[StructureDimensionScore]
    ) -> Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
        "none",
    ]:
        valid = set(STRUCTURE_DIMENSIONS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        if not dimensions:
            return "none"
        worst = max(dimensions, key=lambda d: abs(d.observed_score - d.target_score))
        gap = abs(worst.observed_score - worst.target_score)
        if gap < 0.15:
            return "none"
        return worst.dimension

    def _fit_quality(
        self, overall_fit: float, raw_quality: str
    ) -> Literal["well-fit", "partial-fit", "misfit"]:
        if raw_quality in ("well-fit", "partial-fit", "misfit"):
            return raw_quality  # type: ignore[return-value]
        if overall_fit >= 0.8:
            return "well-fit"
        if overall_fit >= 0.5:
            return "partial-fit"
        return "misfit"

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        dimensions: list[StructureDimensionScore],
        biggest_gap: str,
        archetype: str,
        fit_quality: str,
        task_class: str,
    ) -> StructureProfilePattern:
        if fit_quality == "well-fit":
            return "well_fit"

        misaligned = [d for d in dimensions if abs(d.observed_score - d.target_score) >= 0.25]
        if len(misaligned) >= 4:
            return "broadly_misfit"

        by: dict[str, StructureDimensionScore] = {str(d.dimension): d for d in dimensions}

        def under(name: str) -> bool:
            d = by.get(name)
            return bool(d and d.observed_score + 0.15 < d.target_score)

        def over(name: str) -> bool:
            d = by.get(name)
            return bool(d and d.observed_score - 0.15 > d.target_score)

        critical_classes = {
            "incident_response",
            "regulated_workflow",
            "financial_operation",
        }
        creative_classes = {
            "creative_brainstorm",
            "research_exploration",
            "code_review",
        }

        if biggest_gap == "hierarchy":
            if under("hierarchy") and task_class in critical_classes:
                return "too_flat_for_critical_task"
            if over("hierarchy") and task_class in creative_classes:
                return "too_hierarchical_for_creative"
        if biggest_gap == "centralization":
            if over("centralization"):
                return "decision_bottleneck"
            if under("centralization"):
                return "no_clear_authority"
        if biggest_gap == "specialization":
            if over("specialization"):
                return "over_specialized"
            if under("specialization"):
                return "under_specialized"
        if biggest_gap == "departmentalization" and archetype == "matrix":
            return "matrix_overhead"

        # Fallback patterns
        if archetype == "matrix" and len(dimensions) >= 1:
            return "matrix_overhead"
        if over("centralization"):
            return "decision_bottleneck"
        if under("hierarchy") and task_class in critical_classes:
            return "too_flat_for_critical_task"
        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: CrewStructureTrace,
        profile_pattern: StructureProfilePattern,
        biggest_gap: str,
        archetype: StructureArchetype,
        interventions: list[StructureIntervention],
    ) -> ComposedPatternHandoff:
        provisional = StructureAnalysis(
            crew_id=trace.crew_id,
            task_class=trace.task_class,
            archetype=archetype,
            dimensions=[],
            overall_fit=0.5,
            fit_quality="partial-fit",
            biggest_gap=cast(Any, biggest_gap),
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "task_class": trace.task_class,
            "archetype": archetype,
            "biggest_gap": biggest_gap,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self, interventions: list[StructureIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_dimension)
            pb = find_playbook_for_intervention(target, iv.intervention_type, iv.direction)
            if pb is not None and (pb.dimension, pb.failure_mode) not in attached:
                attached[(pb.dimension, pb.failure_mode)] = pb
        return list(attached.values())


class StructureMatrixAnalyzerAsync:
    """Async mirror of :class:`StructureMatrixAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: StructureMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: StructureMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: CrewStructureTrace,
        *,
        mode: StructureMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> StructureAnalysis:
        active_mode: StructureMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = StructureMatrixAnalyzer(
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


_legacy_log = logging.getLogger("vstack.org_structure.generator")
_legacy_log.addHandler(logging.NullHandler())


__all__ = [
    "AsyncLLMClient",
    "LLMClient",
    "StructureMatrixAnalyzer",
    "StructureMatrixAnalyzerAsync",
]
