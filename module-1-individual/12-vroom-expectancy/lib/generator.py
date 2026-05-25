"""VroomExpectancyAnalyzer: multi-mode Vroom E*I*V diagnostic.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``VroomExpectancyCalculator`` remains exported as
an alias for ``VroomExpectancyAnalyzer``.
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
    FORENSIC_EIV_INTERACTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PROMPT_SIGNAL_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_TERMS_PROMPT,
    VROOM_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    VROOM_TERMS,
    AgentExpectancyTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    EIVInteractionAudit,
    PromptSignalItem,
    VroomDetection,
    VroomIntervention,
    VroomMode,
    VroomProfilePattern,
    VroomTerm,
    VroomTermOrNone,
    VroomTermScore,
    severity_from_motivation,
)

log = get_logger("vstack.vroom_expectancy.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class VroomExpectancyAnalyzer:
    """Run the Vroom E*I*V diagnostic on an AgentExpectancyTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: VroomMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: VroomMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentExpectancyTrace,
        *,
        mode: VroomMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> VroomDetection:
        active_mode: VroomMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="vroom_expectancy"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentExpectancyTrace],
        *,
        mode: VroomMode | None = None,
    ) -> Iterator[VroomDetection]:
        active_mode: VroomMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="vroom_expectancy"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentExpectancyTrace,
        mode: VroomMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> VroomDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Vroom diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        prompt_signals: list[PromptSignalItem] = []
        eiv_audit: EIVInteractionAudit | None = None

        if mode == "quick":
            terms, bottleneck, quality, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            terms, bottleneck, quality = self._pass_standard_terms(trace, acc)
            interventions = self._pass_standard_interventions(
                trace, terms, bottleneck, quality, acc
            )
        elif mode == "forensic":
            terms, bottleneck, quality = self._pass_standard_terms(trace, acc)
            prompt_signals = self._pass_forensic_prompt_signals(trace, acc)
            eiv_audit = self._pass_forensic_eiv_interaction(trace, terms, acc)
            interventions = self._pass_forensic_interventions(
                trace, terms, bottleneck, quality, prompt_signals, eiv_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown VroomMode: {mode!r}")

        # Deterministic motivation score (E * I * V).
        motivation_score = self._compute_motivation(terms)

        # Reconcile bottleneck + quality from the deterministic score if LLM
        # disagrees by a lot.
        bottleneck = self._coerce_bottleneck_post(bottleneck, terms)
        quality = self._motivation_quality(motivation_score, quality)

        profile_pattern = self._classify_profile_pattern(
            terms, bottleneck, quality, motivation_score, prompt_signals, trace
        )
        severity = severity_from_motivation(motivation_score, quality)

        composition = (
            self._build_composition_handoff(trace, bottleneck, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = VroomDetection(
                    task_class=trace.task_class,
                    terms=terms,
                    motivation_score=motivation_score,
                    bottleneck_term=bottleneck,
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

        detection = VroomDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            terms=terms,
            motivation_score=motivation_score,
            bottleneck_term=bottleneck,
            motivation_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            prompt_signals=prompt_signals,
            eiv_interaction_audit=eiv_audit,
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
            "Vroom done mode=%s score=%.2f bottleneck=%s quality=%s profile=%s elapsed=%.0fms",
            mode,
            motivation_score,
            bottleneck,
            quality,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    # --- Validation ----------------------------------------------------

    def _validate_trace(self, trace: AgentExpectancyTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentExpectancyTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentExpectancyTrace.outcome cannot be empty.")
        # Need at least one signal source to score E*I*V.
        if not trace.system_prompt and not trace.observed_behaviors and not trace.effort_signals:
            raise ValueError(
                "AgentExpectancyTrace must include at least one of "
                "system_prompt, observed_behaviors, or effort_signals."
            )

    def _scan_injection(self, trace: AgentExpectancyTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("system_prompt", trace.system_prompt),
        ]
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
        for i, s in enumerate(trace.effort_signals):
            targets.append((f"effort_signals[{i}]", s))
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
        mode: VroomMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=VROOM_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "vroom_expectancy"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(
        self, trace: AgentExpectancyTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[VroomTermScore],
        VroomTermOrNone,
        Literal["motivated", "weak", "collapsed"],
        VroomIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            effort_signals=trace.effort_signals,
            declared_reward=trace.declared_reward,
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        terms = self._parse_terms(obj.get("terms", []))
        bottleneck = self._coerce_bottleneck(obj.get("bottleneck_term"), terms)
        # Quality computed deterministically later.
        quality = self._coerce_quality(obj.get("motivation_quality"))
        top_iv: VroomIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = VroomIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return terms, bottleneck, quality, top_iv

    def _pass_standard_terms(
        self, trace: AgentExpectancyTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[VroomTermScore],
        VroomTermOrNone,
        Literal["motivated", "weak", "collapsed"],
    ]:
        prompt = assemble_prompt(
            STANDARD_TERMS_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            effort_signals=trace.effort_signals,
            declared_reward=trace.declared_reward,
            outcome=trace.outcome,
            success=trace.success,
        )
        raw = self._call(prompt, pass_name="standard_terms", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        terms = self._parse_terms(obj.get("terms", []))
        bottleneck = self._coerce_bottleneck(obj.get("bottleneck_term"), terms)
        quality = self._coerce_quality(obj.get("motivation_quality"))
        return terms, bottleneck, quality

    def _pass_standard_interventions(
        self,
        trace: AgentExpectancyTrace,
        terms: list[VroomTermScore],
        bottleneck: VroomTermOrNone,
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[VroomIntervention]:
        if bottleneck == "none" and quality == "motivated":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            bottleneck_term=bottleneck,
            motivation_quality=quality,
            task_class=trace.task_class,
            evidence=[t.model_dump() for t in terms],
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_prompt_signals(
        self, trace: AgentExpectancyTrace, acc: "_PipelineAcc"
    ) -> list[PromptSignalItem]:
        if not trace.system_prompt and not trace.effort_signals:
            return []
        prompt = assemble_prompt(
            FORENSIC_PROMPT_SIGNAL_PROMPT,
            system_prompt=trace.system_prompt or "(none)",
            effort_signals=trace.effort_signals,
        )
        raw = self._call(prompt, pass_name="forensic_prompt_signals", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        items: list[PromptSignalItem] = []
        for entry in data:
            try:
                items.append(PromptSignalItem(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed PromptSignalItem (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return items

    def _pass_forensic_eiv_interaction(
        self,
        trace: AgentExpectancyTrace,
        terms: list[VroomTermScore],
        acc: "_PipelineAcc",
    ) -> EIVInteractionAudit | None:
        prompt = assemble_prompt(
            FORENSIC_EIV_INTERACTION_PROMPT,
            evidence=[t.model_dump() for t in terms],
        )
        raw = self._call(prompt, pass_name="forensic_eiv_interaction", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return EIVInteractionAudit(**obj)
        except Exception as exc:
            log.warning("EIVInteractionAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentExpectancyTrace,
        terms: list[VroomTermScore],
        bottleneck: VroomTermOrNone,
        quality: str,
        prompt_signals: list[PromptSignalItem],
        eiv_audit: EIVInteractionAudit | None,
        acc: "_PipelineAcc",
    ) -> list[VroomIntervention]:
        provisional_score = self._compute_motivation(terms)
        provisional_profile = self._classify_profile_pattern(
            terms, bottleneck, quality, provisional_score, prompt_signals, trace
        )
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            bottleneck_term=bottleneck,
            motivation_quality=quality,
            profile_pattern=provisional_profile,
            task_class=trace.task_class,
            prompt_signals=[ps.model_dump() for ps in prompt_signals],
            eiv_audit=eiv_audit.model_dump() if eiv_audit else None,
            evidence=[t.model_dump() for t in terms],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # --- Parsers + coercers -------------------------------------------

    def _parse_terms(self, raw: Any) -> list[VroomTermScore]:
        terms: list[VroomTermScore] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    terms.append(VroomTermScore(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed VroomTermScore (%s): %r",
                        type(exc).__name__,
                        entry,
                    )

        seen = {t.term for t in terms}
        for term in VROOM_TERMS:
            if term not in seen:
                terms.append(
                    VroomTermScore(
                        term=term,  # type: ignore[arg-type]
                        score=0.5 if term != "valence" else 0.0,
                        explanation="No evidence observed for this term.",
                        evidence_quotes=[],
                        confidence=0.5,
                    )
                )
        order = {t: i for i, t in enumerate(VROOM_TERMS)}
        terms.sort(key=lambda t: order.get(t.term, len(VROOM_TERMS)))
        return terms

    def _parse_interventions(self, raw: str) -> list[VroomIntervention]:
        data = extract_json_array(raw)
        interventions: list[VroomIntervention] = []
        for entry in data:
            try:
                interventions.append(VroomIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed VroomIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _compute_motivation(self, terms: list[VroomTermScore]) -> float:
        """Deterministic E * I * V product, clipped to [-1, 1]."""
        scores: dict[str, float] = {str(t.term): t.score for t in terms}
        e = scores.get("expectancy", 0.0)
        i = scores.get("instrumentality", 0.0)
        v = scores.get("valence", 0.0)
        product = e * i * v
        return round(max(-1.0, min(1.0, product)), 4)

    def _coerce_bottleneck(self, raw: Any, terms: list[VroomTermScore]) -> VroomTermOrNone:
        valid = set(VROOM_TERMS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return cast(VroomTermOrNone, raw.strip())
        if not terms:
            return "none"

        # Term closest to zero (for V, signed; for E/I, raw).
        def _distance_to_zero(t: VroomTermScore) -> float:
            if t.term == "valence":
                # Negative valence is worst; large positive is best.
                return abs(t.score)
            return t.score

        bottleneck_term = min(terms, key=_distance_to_zero)
        # If all terms are healthy, no bottleneck.
        if all(_distance_to_zero(t) >= 0.7 for t in terms):
            return "none"
        return cast(VroomTermOrNone, bottleneck_term.term)

    def _coerce_bottleneck_post(
        self, current: VroomTermOrNone, terms: list[VroomTermScore]
    ) -> VroomTermOrNone:
        """After LLM parse, reconcile with deterministic minimum."""
        if current != "none":
            return current
        # If LLM said 'none' but a term is actually low, override.
        return self._coerce_bottleneck(None, terms)

    def _coerce_quality(self, raw: Any) -> Literal["motivated", "weak", "collapsed"]:
        if isinstance(raw, str) and raw.strip() in (
            "motivated",
            "weak",
            "collapsed",
        ):
            return cast(Literal["motivated", "weak", "collapsed"], raw.strip())
        return "weak"

    def _motivation_quality(
        self, score: float, raw: str
    ) -> Literal["motivated", "weak", "collapsed"]:
        """Determine quality from deterministic score, respecting explicit raw."""
        if isinstance(raw, str) and raw.strip() in (
            "motivated",
            "weak",
            "collapsed",
        ):
            return cast(Literal["motivated", "weak", "collapsed"], raw.strip())
        s = max(-1.0, min(1.0, float(score)))
        if s >= 0.4:
            return "motivated"
        if s > 0.05:
            return "weak"
        return "collapsed"

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        terms: list[VroomTermScore],
        bottleneck: VroomTermOrNone,
        quality: str,
        motivation_score: float,
        prompt_signals: list[PromptSignalItem],
        trace: AgentExpectancyTrace,
    ) -> VroomProfilePattern:
        scores: dict[str, float] = {str(t.term): t.score for t in terms}
        e = scores.get("expectancy", 0.5)
        i = scores.get("instrumentality", 0.5)
        v = scores.get("valence", 0.5)

        # Negative valence -> avoidance.
        if v < 0:
            return "valence_negative_active_avoidance"

        # Multi-term collapse (2+ near zero).
        low_terms = sum(1 for s in (e, i, v) if s < 0.3)
        if low_terms >= 2:
            return "multi_term_collapse"

        # Misalignment.
        if e >= 0.7 and i >= 0.7 and v < 0.3:
            return "high_E_high_I_low_V_misaligned_task"
        if e >= 0.7 and i < 0.3:
            return "high_E_low_I_pointless_work"

        # Task-class-specific.
        if trace.task_class == "creative" and e < 0.4:
            return "low_E_creative_task_misfit"
        if trace.task_class == "tool_use" and e < 0.4:
            return "low_E_tool_use_capability_gap"

        # Per-bottleneck.
        mapping: dict[str, VroomProfilePattern] = {
            "expectancy": "expectancy_bottleneck",
            "instrumentality": "instrumentality_bottleneck",
            "valence": "valence_bottleneck",
        }
        if bottleneck in mapping:
            return mapping[bottleneck]

        # Healthy.
        if quality == "motivated" or motivation_score >= 0.5:
            return "motivated_balanced"

        if all(0.3 <= s <= 0.6 for s in (e, i, v)):
            return "balanced_but_weak"

        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentExpectancyTrace,
        bottleneck: VroomTermOrNone,
        profile_pattern: VroomProfilePattern,
        interventions: list[VroomIntervention],
    ) -> ComposedPatternHandoff:
        provisional = VroomDetection(
            task_class=trace.task_class,
            terms=[],
            motivation_score=0.0,
            bottleneck_term=bottleneck,
            motivation_quality="weak",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "bottleneck_term": bottleneck,
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

    def _attach_playbooks(self, interventions: list[VroomIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_term)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.term, pb.failure_mode) not in attached:
                attached[(pb.term, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
VroomExpectancyCalculator = VroomExpectancyAnalyzer


class VroomExpectancyAnalyzerAsync:
    """Async mirror of :class:`VroomExpectancyAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: VroomMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: VroomMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentExpectancyTrace,
        *,
        mode: VroomMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> VroomDetection:
        active_mode: VroomMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = VroomExpectancyAnalyzer(
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


_legacy_log = logging.getLogger("vstack.vroom_expectancy.generator")
_legacy_log.addHandler(logging.NullHandler())

_PUBLIC_REEXPORTS: tuple[object, ...] = (VroomTerm,)
