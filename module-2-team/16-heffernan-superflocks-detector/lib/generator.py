"""SuperflocksAnalyzer: multi-mode Heffernan superflocks diagnostic.

Backward-compatible: ``SuperflocksDetector`` remains exported as alias.
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
    FORENSIC_CAPABILITY_AUDIT_PROMPT,
    FORENSIC_FAILURE_AUDIT_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_METRICS_PROMPT,
    SUPERFLOCKS_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    AttachedPlaybook,
    CapabilityComplementarityAudit,
    ComposedPatternHandoff,
    FailureClusteringAudit,
    FragilityIntervention,
    RoutingTrace,
    SuperflocksDetection,
    SuperflocksMetric,
    SuperflocksMode,
    SuperflocksProfilePattern,
    severity_from_fragility,
)

log = get_logger("agentcity.superflocks.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class SuperflocksAnalyzer:
    """Run the Heffernan Superflocks diagnostic on a RoutingTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SuperflocksMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SuperflocksMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: RoutingTrace,
        *,
        mode: SuperflocksMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SuperflocksDetection:
        active_mode: SuperflocksMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="superflocks"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[RoutingTrace],
        *,
        mode: SuperflocksMode | None = None,
    ) -> Iterator[SuperflocksDetection]:
        active_mode: SuperflocksMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="superflocks"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: RoutingTrace,
        mode: SuperflocksMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> SuperflocksDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Superflocks diagnostic (mode=%s) for trace %s",
            mode,
            trace.trace_id or "<unknown>",
        )

        acc = _PipelineAcc()
        capability_audit: CapabilityComplementarityAudit | None = None
        failure_audit: FailureClusteringAudit | None = None

        # Deterministic core compute.
        top_agent, top_agent_share = self._compute_top_agent(trace)
        routing_gini = self._compute_routing_gini(trace)
        fragility_score = self._compute_fragility(routing_gini, top_agent_share)

        if mode == "quick":
            metrics, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            # Legacy v0.0.x: single LLM call returning metrics + interventions.
            metrics, interventions = self._pass_standard_combined(trace, acc)
        elif mode == "forensic":
            metrics, interventions = self._pass_standard_combined(trace, acc)
            capability_audit = self._pass_forensic_capability(trace, acc)
            failure_audit = self._pass_forensic_failure(trace, top_agent, acc)
            fragility_quality = self._fragility_quality(fragility_score, "")
            interventions = self._pass_forensic_interventions(
                metrics, fragility_quality, capability_audit, failure_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown SuperflocksMode: {mode!r}")

        # Fill missing metrics + override computed values.
        all_metrics = self._compute_metrics(trace)
        metrics = self._fill_metrics(
            metrics, top_agent_share, routing_gini, trace_metrics=all_metrics
        )
        fragility_quality = self._fragility_quality(fragility_score, "")
        profile_pattern = self._classify_profile_pattern(
            top_agent_share, routing_gini, fragility_score, capability_audit, failure_audit
        )
        severity = severity_from_fragility(fragility_score)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(interventions, fragility_quality)
            if self.playbooks_enabled
            else []
        )

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = SuperflocksDetection(
                    trace_id=trace.trace_id,
                    top_agent=top_agent,
                    top_agent_share=top_agent_share,
                    routing_gini=routing_gini,
                    fragility_score=fragility_score,
                    fragility_quality=fragility_quality,
                    metrics=metrics,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return SuperflocksDetection(
            trace_id=trace.trace_id,
            top_agent=top_agent,
            top_agent_share=top_agent_share,
            routing_gini=routing_gini,
            fragility_score=fragility_score,
            fragility_quality=fragility_quality,
            metrics=metrics,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            capability_audit=capability_audit,
            failure_audit=failure_audit,
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

    def _validate_trace(self, trace: RoutingTrace) -> None:
        if not trace.window_description or not trace.window_description.strip():
            raise ValueError("RoutingTrace.window_description cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("RoutingTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("RoutingTrace.agents must contain at least 2 agents.")
        if len(trace.routing_decisions) < 2:
            raise ValueError("RoutingTrace.routing_decisions must contain at least 2 decisions.")

    def _scan_injection(self, trace: RoutingTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("window_description", trace.window_description),
            ("outcome", trace.outcome),
        ]
        for i, d in enumerate(trace.routing_decisions):
            targets.append((f"routing_decisions[{i}].reason", d.reason))
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
        mode: SuperflocksMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SUPERFLOCKS_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "superflocks"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_quick(
        self, trace: RoutingTrace, acc: "_PipelineAcc"
    ) -> tuple[list[SuperflocksMetric], FragilityIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            window_description=trace.window_description,
            agents=trace.agents,
            capabilities=[c.model_dump() for c in trace.capabilities],
            routing_decisions=[d.model_dump() for d in trace.routing_decisions],
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        metrics = self._parse_metrics(obj.get("metrics", []))
        top_iv: FragilityIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = FragilityIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return metrics, top_iv

    def _pass_standard_metrics(
        self, trace: RoutingTrace, acc: "_PipelineAcc"
    ) -> list[SuperflocksMetric]:
        prompt = assemble_prompt(
            STANDARD_METRICS_PROMPT,
            window_description=trace.window_description,
            agents=trace.agents,
            capabilities=[c.model_dump() for c in trace.capabilities],
            routing_decisions=[d.model_dump() for d in trace.routing_decisions],
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="standard_metrics", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        return self._parse_metrics(obj.get("metrics", []))

    def _pass_standard_interventions(
        self,
        metrics: list[SuperflocksMetric],
        fragility_quality: str,
        acc: "_PipelineAcc",
    ) -> list[FragilityIntervention]:
        if fragility_quality == "robust":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            metrics=[m.model_dump() for m in metrics],
            fragility_quality=fragility_quality,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_standard_combined(
        self, trace: RoutingTrace, acc: "_PipelineAcc"
    ) -> tuple[list[SuperflocksMetric], list[FragilityIntervention]]:
        """v0.0.x compat: single LLM call returns both metrics and interventions."""
        prompt = assemble_prompt(
            STANDARD_METRICS_PROMPT,
            window_description=trace.window_description,
            agents=trace.agents,
            capabilities=[c.model_dump() for c in trace.capabilities],
            routing_decisions=[d.model_dump() for d in trace.routing_decisions],
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="standard_combined", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        metrics = self._parse_metrics(obj.get("metrics", []))
        iv_raw = obj.get("interventions", [])
        interventions: list[FragilityIntervention] = []
        if isinstance(iv_raw, list):
            for entry in iv_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    interventions.append(FragilityIntervention(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed FragilityIntervention (%s)",
                        type(exc).__name__,
                    )
        return metrics, interventions

    def _fill_metrics(
        self,
        metrics: list[SuperflocksMetric],
        top_agent_share: float,
        routing_gini: float,
        trace_metrics: dict[str, float] | None = None,
    ) -> list[SuperflocksMetric]:
        """Fill missing metrics; override computable ones with local values."""
        canonical: tuple[str, ...] = (
            "top_agent_share",
            "routing_gini",
            "complementarity_utilization",
            "fallback_coverage",
            "failure_clustering",
        )
        by_name: dict[str, SuperflocksMetric] = {str(m.name): m for m in metrics}
        local_values: dict[str, float] = trace_metrics or {
            "top_agent_share": top_agent_share,
            "routing_gini": routing_gini,
        }
        out: list[SuperflocksMetric] = []
        for name in canonical:
            if name in local_values:
                m = by_name.get(name)
                if m is not None:
                    m = SuperflocksMetric(
                        name=m.name,
                        value=local_values[name],
                        explanation=m.explanation,
                        severity=m.severity,
                    )
                else:
                    m = SuperflocksMetric(
                        name=name,  # type: ignore[arg-type]
                        value=local_values[name],
                        explanation=f"locally computed: {name}",
                        severity="medium",
                    )
            else:
                m = by_name.get(name) or SuperflocksMetric(
                    name=name,  # type: ignore[arg-type]
                    value=0.0,
                    explanation=f"No evidence observed for {name}.",
                    severity="none",
                )
            out.append(m)
        return out

    def _pass_forensic_capability(
        self, trace: RoutingTrace, acc: "_PipelineAcc"
    ) -> CapabilityComplementarityAudit | None:
        prompt = assemble_prompt(
            FORENSIC_CAPABILITY_AUDIT_PROMPT,
            agents=trace.agents,
            capabilities=[c.model_dump() for c in trace.capabilities],
            routing_decisions=[d.model_dump() for d in trace.routing_decisions],
        )
        raw = self._call(prompt, pass_name="forensic_capability_audit", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CapabilityComplementarityAudit(**obj)
        except Exception as exc:
            log.warning("CapabilityComplementarityAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_failure(
        self,
        trace: RoutingTrace,
        top_agent: str | None,
        acc: "_PipelineAcc",
    ) -> FailureClusteringAudit | None:
        if top_agent is None:
            return None
        prompt = assemble_prompt(
            FORENSIC_FAILURE_AUDIT_PROMPT,
            top_agent=top_agent,
            routing_decisions=[d.model_dump() for d in trace.routing_decisions],
        )
        raw = self._call(prompt, pass_name="forensic_failure_audit", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return FailureClusteringAudit(**obj)
        except Exception as exc:
            log.warning("FailureClusteringAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        metrics: list[SuperflocksMetric],
        fragility_quality: str,
        capability_audit: CapabilityComplementarityAudit | None,
        failure_audit: FailureClusteringAudit | None,
        acc: "_PipelineAcc",
    ) -> list[FragilityIntervention]:
        if fragility_quality == "robust":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            metrics=[m.model_dump() for m in metrics],
            fragility_quality=fragility_quality,
            capability_audit=capability_audit.model_dump() if capability_audit else None,
            failure_audit=failure_audit.model_dump() if failure_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_metrics(self, raw: Any) -> list[SuperflocksMetric]:
        metrics: list[SuperflocksMetric] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    metrics.append(SuperflocksMetric(**entry))
                except Exception as exc:
                    log.warning("Dropping malformed SuperflocksMetric (%s)", type(exc).__name__)
        return metrics

    def _parse_interventions(self, raw: str) -> list[FragilityIntervention]:
        data = extract_json_array(raw)
        interventions: list[FragilityIntervention] = []
        for entry in data:
            try:
                interventions.append(FragilityIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed FragilityIntervention (%s)", type(exc).__name__)
        return interventions

    def _compute_metrics(self, trace: RoutingTrace) -> dict[str, float]:
        """Compute all 5 metrics locally from the trace."""
        top_agent, top_share = self._compute_top_agent(trace)
        gini = self._compute_routing_gini(trace)
        complementarity = round(1.0 - top_share, 4)
        # Failure clustering: of all failures, what fraction hit the top?
        failures = [d for d in trace.routing_decisions if d.outcome == "failure"]
        if failures and top_agent:
            top_failures = sum(1 for d in failures if d.routed_to == top_agent)
            failure_clustering = round(top_failures / len(failures), 4)
        else:
            failure_clustering = 0.0
        # Fallback coverage: per task_class, fraction of qualifying agents > 1.
        if trace.capabilities:
            classes_seen: set[str] = set()
            classes_with_fallback = 0
            for d in trace.routing_decisions:
                classes_seen.add(d.task_class or "default")
            for c in classes_seen:
                if c == "default":
                    qualified = sum(
                        1
                        for cap in trace.capabilities
                        if any(s >= 0.5 for s in cap.capability_scores.values())
                    )
                else:
                    qualified = sum(
                        1 for cap in trace.capabilities if cap.capability_scores.get(c, 0.0) >= 0.5
                    )
                if qualified >= 2:
                    classes_with_fallback += 1
            fallback_coverage = (
                round(classes_with_fallback / len(classes_seen), 4) if classes_seen else 0.0
            )
        else:
            fallback_coverage = 1.0 if len(trace.agents) >= 2 else 0.0
        return {
            "top_agent_share": top_share,
            "routing_gini": gini,
            "complementarity_utilization": complementarity,
            "fallback_coverage": fallback_coverage,
            "failure_clustering": failure_clustering,
        }

    def _compute_top_agent(self, trace: RoutingTrace) -> tuple[str | None, float]:
        counts: dict[str, int] = {}
        for d in trace.routing_decisions:
            counts[d.routed_to] = counts.get(d.routed_to, 0) + 1
        if not counts:
            return None, 0.0
        top_agent = max(counts, key=lambda k: counts[k])
        total = sum(counts.values())
        share = counts[top_agent] / total if total else 0.0
        return top_agent, round(share, 2)

    def _compute_routing_gini(self, trace: RoutingTrace) -> float:
        counts: dict[str, int] = {a: 0 for a in trace.agents}
        for d in trace.routing_decisions:
            counts[d.routed_to] = counts.get(d.routed_to, 0) + 1
        shares = sorted([counts[a] for a in trace.agents])
        n = len(shares)
        if n == 0:
            return 0.0
        cum = 0.0
        for i, s in enumerate(shares):
            cum += (2 * (i + 1) - n - 1) * s
        total = sum(shares)
        if total == 0:
            return 0.0
        gini = cum / (n * total)
        return round(max(0.0, min(1.0, gini)), 4)

    def _compute_fragility(self, routing_gini: float, top_agent_share: float) -> float:
        # Mean of Gini and top-share (both inverse robustness proxies).
        return round((routing_gini + top_agent_share) / 2.0, 4)

    def _coerce_fragility_quality(
        self, fragility_score: float
    ) -> Literal["robust", "concentrated", "superflocks"]:
        return self._fragility_quality(fragility_score, "")

    def _fragility_quality(
        self, fragility_score: float, raw: str
    ) -> Literal["robust", "concentrated", "superflocks"]:
        if isinstance(raw, str) and raw.strip() in ("robust", "concentrated", "superflocks"):
            return cast(Literal["robust", "concentrated", "superflocks"], raw.strip())
        s = max(0.0, min(1.0, float(fragility_score)))
        if s < 0.30:
            return "robust"
        if s < 0.60:
            return "concentrated"
        return "superflocks"

    def _classify_profile_pattern(
        self,
        top_agent_share: float,
        routing_gini: float,
        fragility_score: float,
        capability_audit: CapabilityComplementarityAudit | None,
        failure_audit: FailureClusteringAudit | None,
    ) -> SuperflocksProfilePattern:
        if fragility_score < 0.40:
            return "robust_diversified"
        if top_agent_share > 0.85:
            return "top_agent_monopoly"
        if capability_audit and capability_audit.wasted_capability_count > 0:
            return "complementarity_collapse"
        if failure_audit and failure_audit.cascade_risk == "high":
            return "failure_clustering_risk"
        if routing_gini > 0.70:
            return "superflocks_canonical"
        if routing_gini > 0.40:
            return "concentrated_routing"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: RoutingTrace,
        profile_pattern: SuperflocksProfilePattern,
        interventions: list[FragilityIntervention],
    ) -> ComposedPatternHandoff:
        provisional = SuperflocksDetection(
            trace_id=trace.trace_id,
            top_agent=None,
            top_agent_share=0.0,
            routing_gini=0.0,
            fragility_score=0.0,
            fragility_quality="robust",
            metrics=[],
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
        interventions: list[FragilityIntervention],
        fragility_quality: str,
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        target_pattern = fragility_quality if fragility_quality != "robust" else "robust"
        for iv in interventions:
            pb = find_playbook_for_intervention(target_pattern, iv.intervention_type)
            if pb is not None and (pb.pattern, pb.failure_mode) not in attached:
                attached[(pb.pattern, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
SuperflocksDetector = SuperflocksAnalyzer


class SuperflocksAnalyzerAsync:
    """Async mirror of :class:`SuperflocksAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SuperflocksMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SuperflocksMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: RoutingTrace,
        *,
        mode: SuperflocksMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SuperflocksDetection:
        active_mode: SuperflocksMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = SuperflocksAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.superflocks.generator")
_legacy_log.addHandler(logging.NullHandler())
