"""MotivationTrapsAnalyzer: multi-mode Saxberg 4-traps diagnostic.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``MotivationTrapsDetector`` remains exported as
an alias for ``MotivationTrapsAnalyzer``.
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
    FORENSIC_ABANDONMENT_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_WEINER_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SAXBERG_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_TRAPS_PROMPT,
    assemble_prompt,
)
from .schema import (
    MOTIVATION_TRAPS,
    AbandonmentLink,
    AgentMotivationTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    DominantTrap,
    MotivationDetection,
    MotivationIntervention,
    MotivationMode,
    MotivationProfilePattern,
    MotivationTrap,
    TrapEvidence,
    WeinerAttributionAxis,
    severity_from_trap_score,
)

log = get_logger("vstack.motivation_traps.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class MotivationTrapsAnalyzer:
    """Run the 4 Motivation Traps diagnostic on an AgentMotivationTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: MotivationMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: MotivationMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentMotivationTrace,
        *,
        mode: MotivationMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> MotivationDetection:
        active_mode: MotivationMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="motivation_traps"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentMotivationTrace],
        *,
        mode: MotivationMode | None = None,
    ) -> Iterator[MotivationDetection]:
        active_mode: MotivationMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="motivation_traps"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentMotivationTrace,
        mode: MotivationMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> MotivationDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Motivation Traps diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        weiner_axis: WeinerAttributionAxis | None = None
        abandonment_chain: list[AbandonmentLink] = []

        if mode == "quick":
            evidence, dominant, quality, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence, dominant, quality = self._pass_standard_traps(trace, acc)
            interventions = self._pass_standard_interventions(
                trace, evidence, dominant, quality, acc
            )
        elif mode == "forensic":
            evidence, dominant, quality = self._pass_standard_traps(trace, acc)
            weiner_axis = self._pass_forensic_weiner(trace, acc)
            abandonment_chain = self._pass_forensic_abandonment(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                evidence,
                dominant,
                quality,
                weiner_axis,
                abandonment_chain,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown MotivationMode: {mode!r}")

        profile_pattern = self._classify_profile_pattern(
            evidence, dominant, quality, weiner_axis, trace
        )
        peak = max((ev.score for ev in evidence), default=0.0)
        severity = severity_from_trap_score(peak, quality)

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
                provisional = MotivationDetection(
                    task_class=trace.task_class,
                    trap_evidence=evidence,
                    dominant_trap=dominant,
                    motivation_quality=quality,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = MotivationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            trap_evidence=evidence,
            dominant_trap=dominant,
            motivation_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            attribution_axis=weiner_axis,
            abandonment_chain=abandonment_chain,
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
            "Motivation Traps done mode=%s dominant=%s quality=%s profile=%s elapsed=%.0fms",
            mode,
            dominant,
            quality,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    # --- Validation ----------------------------------------------------

    def _validate_trace(self, trace: AgentMotivationTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentMotivationTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentMotivationTrace.outcome cannot be empty.")
        if not trace.abandonment_signal or not trace.abandonment_signal.strip():
            raise ValueError("AgentMotivationTrace.abandonment_signal cannot be empty.")

    def _scan_injection(self, trace: AgentMotivationTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("abandonment_signal", trace.abandonment_signal),
            ("system_prompt", trace.system_prompt),
        ]
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
        for i, r in enumerate(trace.self_reports):
            targets.append((f"self_reports[{i}]", r))
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

    # --- LLM call helper ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: MotivationMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SAXBERG_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "motivation_traps"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(
        self, trace: AgentMotivationTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[TrapEvidence],
        DominantTrap,
        Literal["motivated", "at-risk", "abandoning"],
        MotivationIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            abandonment_signal=trace.abandonment_signal,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            self_reports=trace.self_reports,
            prior_failures=trace.prior_failures,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("trap_evidence", []))
        dominant = self._coerce_dominant(obj.get("dominant_trap"), evidence)
        quality = self._coerce_quality(obj.get("motivation_quality"), evidence)
        top_iv: MotivationIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = MotivationIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, dominant, quality, top_iv

    def _pass_standard_traps(
        self, trace: AgentMotivationTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[TrapEvidence],
        DominantTrap,
        Literal["motivated", "at-risk", "abandoning"],
    ]:
        prompt = assemble_prompt(
            STANDARD_TRAPS_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            abandonment_signal=trace.abandonment_signal,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            self_reports=trace.self_reports,
            prior_failures=trace.prior_failures,
        )
        raw = self._call(prompt, pass_name="standard_traps", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("trap_evidence", []))
        dominant = self._coerce_dominant(obj.get("dominant_trap"), evidence)
        quality = self._coerce_quality(obj.get("motivation_quality"), evidence)
        return evidence, dominant, quality

    def _pass_standard_interventions(
        self,
        trace: AgentMotivationTrace,
        evidence: list[TrapEvidence],
        dominant: DominantTrap,
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[MotivationIntervention]:
        if dominant == "none" and quality == "motivated":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            dominant_trap=dominant,
            motivation_quality=quality,
            task_class=trace.task_class,
            evidence=[ev.model_dump() for ev in evidence],
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_weiner(
        self, trace: AgentMotivationTrace, acc: "_PipelineAcc"
    ) -> WeinerAttributionAxis | None:
        if not trace.self_reports and not trace.prior_failures:
            return None
        prompt = assemble_prompt(
            FORENSIC_WEINER_PROMPT,
            self_reports=trace.self_reports,
            prior_failures=trace.prior_failures,
        )
        raw = self._call(prompt, pass_name="forensic_weiner", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return WeinerAttributionAxis(**obj)
        except Exception as exc:
            log.warning("WeinerAttributionAxis parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_abandonment(
        self, trace: AgentMotivationTrace, acc: "_PipelineAcc"
    ) -> list[AbandonmentLink]:
        prompt = assemble_prompt(
            FORENSIC_ABANDONMENT_PROMPT,
            abandonment_signal=trace.abandonment_signal,
            observed_behaviors=trace.observed_behaviors,
            self_reports=trace.self_reports,
        )
        raw = self._call(prompt, pass_name="forensic_abandonment", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        chain: list[AbandonmentLink] = []
        for entry in data:
            try:
                chain.append(AbandonmentLink(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed AbandonmentLink (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return chain

    def _pass_forensic_interventions(
        self,
        trace: AgentMotivationTrace,
        evidence: list[TrapEvidence],
        dominant: DominantTrap,
        quality: str,
        weiner: WeinerAttributionAxis | None,
        abandonment: list[AbandonmentLink],
        acc: "_PipelineAcc",
    ) -> list[MotivationIntervention]:
        provisional_profile = self._classify_profile_pattern(
            evidence, dominant, quality, weiner, trace
        )
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant_trap=dominant,
            motivation_quality=quality,
            profile_pattern=provisional_profile,
            task_class=trace.task_class,
            weiner_audit=weiner.model_dump() if weiner else None,
            abandonment_chain=[a.model_dump() for a in abandonment],
            evidence=[ev.model_dump() for ev in evidence],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # --- Parsers + coercers -------------------------------------------

    def _parse_evidence(self, raw: Any) -> list[TrapEvidence]:
        evidence: list[TrapEvidence] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(TrapEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed TrapEvidence (%s): %r",
                        type(exc).__name__,
                        entry,
                    )

        seen = {ev.trap for ev in evidence}
        for t in MOTIVATION_TRAPS:
            if t not in seen:
                evidence.append(
                    TrapEvidence(
                        trap=t,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="No evidence observed for this trap.",
                        evidence_quotes=[],
                        confidence=0.5,
                    )
                )
        order = {t: i for i, t in enumerate(MOTIVATION_TRAPS)}
        evidence.sort(key=lambda ev: order.get(ev.trap, len(MOTIVATION_TRAPS)))
        return evidence

    def _parse_interventions(self, raw: str) -> list[MotivationIntervention]:
        data = extract_json_array(raw)
        interventions: list[MotivationIntervention] = []
        for entry in data:
            try:
                interventions.append(MotivationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed MotivationIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _coerce_dominant(self, raw: Any, evidence: list[TrapEvidence]) -> DominantTrap:
        valid = set(MOTIVATION_TRAPS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return cast(DominantTrap, raw.strip())
        if not evidence:
            return "none"
        peak = max(evidence, key=lambda ev: ev.score)
        if peak.score < 0.3:
            return "none"
        return cast(DominantTrap, peak.trap)

    def _coerce_quality(
        self, raw: Any, evidence: list[TrapEvidence]
    ) -> Literal["motivated", "at-risk", "abandoning"]:
        if isinstance(raw, str) and raw.strip() in (
            "motivated",
            "at-risk",
            "abandoning",
        ):
            return cast(Literal["motivated", "at-risk", "abandoning"], raw.strip())
        peak = max((ev.score for ev in evidence), default=0.0)
        if peak > 0.6:
            return "abandoning"
        if peak >= 0.3:
            return "at-risk"
        return "motivated"

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        evidence: list[TrapEvidence],
        dominant: DominantTrap,
        quality: str,
        weiner: WeinerAttributionAxis | None,
        trace: AgentMotivationTrace,
    ) -> MotivationProfilePattern:
        scores: dict[str, float] = {str(ev.trap): ev.score for ev in evidence}
        values_s = scores.get("values", 0.0)
        se_s = scores.get("self_efficacy", 0.0)
        emotions_s = scores.get("emotions", 0.0)
        attr_s = scores.get("attribution", 0.0)

        # Multi-trap compounded.
        n_high = sum(1 for v in scores.values() if v >= 0.5)
        if n_high >= 2:
            # Try paired classifications first.
            if values_s >= 0.5 and attr_s >= 0.5:
                return "values_plus_attribution"
            if se_s >= 0.5 and emotions_s >= 0.5:
                return "self_efficacy_plus_emotions"
            if se_s >= 0.5 and attr_s >= 0.5:
                return "self_efficacy_plus_attribution"
            return "multi_trap_compounded"

        # Task-class-specific patterns.
        if trace.task_class in ("tool_use",) and dominant == "self_efficacy":
            return "high_stakes_capability_collapse"
        if trace.task_class == "creative" and dominant == "values":
            return "creative_task_value_misfit"

        # Per-dominant patterns.
        mapping: dict[str, MotivationProfilePattern] = {
            "values": "values_dominant_irrelevance",
            "self_efficacy": "self_efficacy_collapse_uncertainty",
            "emotions": "emotions_post_rejection_cascade",
            "attribution": "attribution_loop_wrong_cause",
        }
        if dominant in mapping:
            return mapping[dominant]

        if quality == "motivated":
            return "motivated_baseline"
        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentMotivationTrace,
        dominant: DominantTrap,
        profile_pattern: MotivationProfilePattern,
        interventions: list[MotivationIntervention],
    ) -> ComposedPatternHandoff:
        provisional = MotivationDetection(
            task_class=trace.task_class,
            trap_evidence=[],
            dominant_trap=dominant,
            motivation_quality="at-risk",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_trap": dominant,
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
        self, interventions: list[MotivationIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_trap)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.trap, pb.failure_mode) not in attached:
                attached[(pb.trap, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
MotivationTrapsDetector = MotivationTrapsAnalyzer


class MotivationTrapsAnalyzerAsync:
    """Async mirror of :class:`MotivationTrapsAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: MotivationMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: MotivationMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentMotivationTrace,
        *,
        mode: MotivationMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> MotivationDetection:
        active_mode: MotivationMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = MotivationTrapsAnalyzer(
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


_legacy_log = logging.getLogger("vstack.motivation_traps.generator")
_legacy_log.addHandler(logging.NullHandler())

# Silence unused warnings -- public surface re-exports.
_PUBLIC_REEXPORTS: tuple[object, ...] = (MotivationTrap,)
