"""TrustTriangleAnalyzer: multi-mode Trust Triangle audit.

Three pipeline modes (quick / standard / forensic) with v0.2.0
production infrastructure: structured logging with run-id, token/cost
telemetry, prompt-injection scan, async mirror.

Backward-compatible: ``TrustTriangleAuditor`` remains exported as an
alias for ``TrustTriangleAnalyzer``. Legacy methods (``_validate_trace``,
``_pass_1_leg_scores``, ``_pass_2_interventions``, ``_build_leg_scores``,
``_dominant_wobble``, ``_trust_level``, ``_serialize_trace``,
``max_trace_chars`` attr) are preserved.
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
    FORENSIC_CONTEXT_SENSITIVITY_PROMPT,
    FORENSIC_HALLUCINATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SYCOPHANCY_PROMPT,
    INTERVENTIONS_PROMPT,
    LEG_SCORE_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    TRUST_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    LEGS,
    AgentInteractionTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    ContextSensitivityAudit,
    HallucinationAudit,
    LegEvidence,
    SycophancyAudit,
    TrustIntervention,
    TrustProfilePattern,
    TrustTriangleAudit,
    TrustTriangleMode,
    severity_from_wobble,
)

log = get_logger("vstack.trust_triangle.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class TrustTriangleAnalyzer:
    """Run the Trust Triangle Audit against an AgentInteractionTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: TrustTriangleMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: TrustTriangleMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentInteractionTrace,
        *,
        mode: TrustTriangleMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> TrustTriangleAudit:
        active_mode: TrustTriangleMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="trust_triangle"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentInteractionTrace],
        *,
        mode: TrustTriangleMode | None = None,
    ) -> Iterator[TrustTriangleAudit]:
        active_mode: TrustTriangleMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="trust_triangle"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentInteractionTrace,
        mode: TrustTriangleMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> TrustTriangleAudit:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running Trust Triangle Audit (mode=%s) for agent %s (turns=%d, success=%s)",
            mode,
            trace.agent_id or "<unknown>",
            len(trace.turns),
            trace.success,
        )

        acc = _PipelineAcc()
        hallucination_audit: HallucinationAudit | None = None
        sycophancy_audit: SycophancyAudit | None = None
        context_sensitivity_audit: ContextSensitivityAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, trace_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_leg_scores(trace, trace_text, acc=acc)
            leg_scores = self._build_leg_scores(evidence)
            dominant = self._dominant_wobble(leg_scores)
            interventions = self._pass_2_interventions(
                trace, trace_text, evidence, dominant, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_leg_scores(trace, trace_text, acc=acc)
            leg_scores = self._build_leg_scores(evidence)
            dominant = self._dominant_wobble(leg_scores)
            hallucination_audit = self._pass_forensic_hallucination(trace_text, acc)
            sycophancy_audit = self._pass_forensic_sycophancy(trace_text, acc)
            context_sensitivity_audit = self._pass_forensic_context(trace_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence,
                dominant,
                hallucination_audit,
                sycophancy_audit,
                context_sensitivity_audit,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown TrustTriangleMode: {mode!r}")

        leg_scores = self._build_leg_scores(evidence)
        dominant = self._dominant_wobble(leg_scores)
        trust_level = self._trust_level(leg_scores)
        profile_pattern = self._classify_profile_pattern(leg_scores, dominant, trust_level)
        severity = severity_from_wobble(max(leg_scores.values(), default=0.0))

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
                provisional = TrustTriangleAudit(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    dominant_wobble=dominant,
                    leg_scores=leg_scores,
                    legs=evidence,
                    interventions=interventions,
                    overall_trust_level=trust_level,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return TrustTriangleAudit(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_wobble=dominant,
            leg_scores=leg_scores,
            legs=evidence,
            interventions=interventions,
            overall_trust_level=trust_level,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            hallucination_audit=hallucination_audit,
            sycophancy_audit=sycophancy_audit,
            context_sensitivity_audit=context_sensitivity_audit,
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

    # --- Legacy v0.0.x public API surface preserved -------------------

    def _validate_trace(self, trace: AgentInteractionTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentInteractionTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentInteractionTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("AgentInteractionTrace.turns cannot be empty.")

    def _scan_injection(self, trace: AgentInteractionTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, t in enumerate(trace.turns):
            targets.append((f"turns[{i}].content", t.content))
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

    def _serialize_trace(self, trace: AgentInteractionTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        turn_lines = []
        for i, turn in enumerate(trace.turns):
            ts = (
                f"[{turn.timestamp.isoformat()}] "
                if turn.timestamp is not None
                else f"[turn {i + 1}] "
            )
            turn_lines.append(f"{ts}{turn.role}: {turn.content}")
        full = "\n".join(header + turn_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Interaction trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: TrustTriangleMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "trust_triangle"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_leg_scores(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[LegEvidence]:
        satisfaction = (
            f"{trace.user_satisfaction:.2f}"
            if trace.user_satisfaction is not None
            else "not reported"
        )
        prompt = LEG_SCORE_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            satisfaction=satisfaction,
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="leg_scores", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[LegEvidence] = []
        for entry in data:
            try:
                evidence.append(LegEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed LegEvidence (%s)", type(exc).__name__)
        seen = {ev.leg for ev in evidence}
        for leg in LEGS:
            if leg not in seen:
                evidence.append(
                    LegEvidence(
                        leg=leg,  # type: ignore[arg-type]
                        wobble_score=0.0,
                        severity="none",
                        explanation="No wobble detected on this leg.",
                        evidence_quotes=[],
                    )
                )
        order = {leg: i for i, leg in enumerate(LEGS)}
        evidence.sort(key=lambda e: order.get(e.leg, len(LEGS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        evidence: list[LegEvidence],
        dominant: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[TrustIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant, evidence=evidence_text, trace=trace_text
        )
        if acc is None:
            raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[TrustIntervention] = []
        for entry in data:
            try:
                interventions.append(TrustIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TrustIntervention (%s)", type(exc).__name__)
        return interventions

    def _build_leg_scores(self, evidence: list[LegEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {leg: 0.0 for leg in LEGS}
        for ev in evidence:
            scores[str(ev.leg)] = max(scores.get(str(ev.leg), 0.0), ev.wobble_score)
        return scores

    def _dominant_wobble(
        self, leg_scores: dict[str, float]
    ) -> Literal["logic", "authenticity", "empathy", "none-observed"]:
        max_score = max(leg_scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for leg in LEGS:
            if leg_scores.get(leg, 0.0) >= max_score - 0.05:
                return leg  # type: ignore[return-value]
        return "none-observed"

    def _trust_level(
        self, leg_scores: dict[str, float]
    ) -> Literal["high-trust", "moderate-trust", "low-trust"]:
        max_score = max(leg_scores.values(), default=0.0)
        if max_score > 0.6:
            return "low-trust"
        if max_score > 0.3:
            return "moderate-trust"
        return "high-trust"

    # --- v0.2.0 mode passes -----------------------------------------------

    def _pass_quick(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[LegEvidence], TrustIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        legs_raw = obj.get("legs", [])
        evidence: list[LegEvidence] = []
        if isinstance(legs_raw, list):
            for entry in legs_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(LegEvidence(**entry))
                except Exception as exc:
                    log.warning("Dropping malformed LegEvidence (%s)", type(exc).__name__)
        seen = {ev.leg for ev in evidence}
        for leg in LEGS:
            if leg not in seen:
                evidence.append(
                    LegEvidence(
                        leg=leg,  # type: ignore[arg-type]
                        wobble_score=0.0,
                        severity="none",
                        explanation="No wobble observed.",
                        evidence_quotes=[],
                    )
                )
        order = {leg: i for i, leg in enumerate(LEGS)}
        evidence.sort(key=lambda e: order.get(e.leg, len(LEGS)))
        top_iv: TrustIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = TrustIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_hallucination(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> HallucinationAudit | None:
        prompt = assemble_prompt(FORENSIC_HALLUCINATION_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_hallucination", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return HallucinationAudit(**obj)
        except Exception as exc:
            log.warning("HallucinationAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_sycophancy(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> SycophancyAudit | None:
        prompt = assemble_prompt(FORENSIC_SYCOPHANCY_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_sycophancy", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return SycophancyAudit(**obj)
        except Exception as exc:
            log.warning("SycophancyAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_context(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> ContextSensitivityAudit | None:
        prompt = assemble_prompt(FORENSIC_CONTEXT_SENSITIVITY_PROMPT, trace=trace_text)
        raw = self._call(
            prompt,
            pass_name="forensic_context_sensitivity",
            mode="forensic",
            acc=acc,
        )
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ContextSensitivityAudit(**obj)
        except Exception as exc:
            log.warning("ContextSensitivityAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[LegEvidence],
        dominant: str,
        hallucination_audit: HallucinationAudit | None,
        sycophancy_audit: SycophancyAudit | None,
        context_sensitivity_audit: ContextSensitivityAudit | None,
        acc: "_PipelineAcc",
    ) -> list[TrustIntervention]:
        if dominant == "none-observed":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=dominant,
            evidence=[e.model_dump() for e in evidence],
            hallucination_audit=hallucination_audit.model_dump() if hallucination_audit else None,
            sycophancy_audit=sycophancy_audit.model_dump() if sycophancy_audit else None,
            context_sensitivity_audit=context_sensitivity_audit.model_dump()
            if context_sensitivity_audit
            else None,
        )
        raw = self._call(
            prompt,
            pass_name="forensic_interventions",
            mode="forensic",
            acc=acc,
        )
        data = extract_json_array(raw)
        interventions: list[TrustIntervention] = []
        for entry in data:
            try:
                interventions.append(TrustIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TrustIntervention (%s)", type(exc).__name__)
        return interventions

    # --- Profile classifier + composition + playbooks ---------------------

    def _classify_profile_pattern(
        self,
        leg_scores: dict[str, float],
        dominant: str,
        trust_level: str,
    ) -> TrustProfilePattern:
        if trust_level == "high-trust":
            return "healthy_trust"

        all_high = sum(1 for s in leg_scores.values() if s >= 0.6)
        if all_high == 3:
            return "full_triangle_collapse"

        logic_score = leg_scores.get("logic", 0.0)
        authenticity_score = leg_scores.get("authenticity", 0.0)
        empathy_score = leg_scores.get("empathy", 0.0)
        if logic_score >= 0.5 and authenticity_score >= 0.5 and empathy_score < 0.3:
            return "logic_authenticity_paired"
        if empathy_score >= 0.5 and logic_score < 0.3 and authenticity_score < 0.3:
            return "empathy_isolated_wobble"

        mapping: dict[str, TrustProfilePattern] = {
            "logic": "logic_wobble_dominant",
            "authenticity": "authenticity_wobble_dominant",
            "empathy": "empathy_wobble_dominant",
        }
        if dominant in mapping:
            return mapping[dominant]
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: AgentInteractionTrace,
        dominant: str,
        profile_pattern: TrustProfilePattern,
        interventions: list[TrustIntervention],
    ) -> ComposedPatternHandoff:
        provisional = TrustTriangleAudit(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_wobble=cast(Any, dominant),
            leg_scores={},
            legs=[],
            interventions=interventions,
            overall_trust_level="moderate-trust",
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_wobble": dominant,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
            "model_name": trace.model_name,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[TrustIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_leg)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.leg, pb.failure_mode) not in attached:
                attached[(pb.leg, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
TrustTriangleAuditor = TrustTriangleAnalyzer


class TrustTriangleAnalyzerAsync:
    """Async mirror of :class:`TrustTriangleAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: TrustTriangleMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: TrustTriangleMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentInteractionTrace,
        *,
        mode: TrustTriangleMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> TrustTriangleAudit:
        active_mode: TrustTriangleMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = TrustTriangleAnalyzer(
            llm_client=sync_shim,
            model=self.model,
            mode=active_mode,
            max_retries=self.max_retries,
            max_trace_chars=self.max_trace_chars,
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


_legacy_log = logging.getLogger("vstack.trust_triangle.generator")
_legacy_log.addHandler(logging.NullHandler())
