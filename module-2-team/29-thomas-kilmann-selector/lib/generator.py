"""ConflictStyleAnalyzer: multi-mode Thomas-Kilmann conflict style selector.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``ConflictStyleSelector`` aliased
to ``ConflictStyleAnalyzer``.
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
    FORENSIC_CONSISTENCY_PROMPT,
    FORENSIC_RECOMMENDATIONS_PROMPT,
    FORENSIC_STYLE_FIT_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    RECOMMENDATIONS_PROMPT,
    TK_ANALYSIS_PROMPT,
    TK_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    STYLES,
    AgentInteractionTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    ConflictStyleSelection,
    PatternConsistencyAudit,
    StyleFitAudit,
    StyleRecommendation,
    StyleScore,
    ThomasKilmannMode,
    ThomasKilmannProfilePattern,
    severity_from_mismatch,
)

log = get_logger("vstack.thomas_kilmann.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class ConflictStyleAnalyzer:
    """Run the Thomas-Kilmann conflict-style selector on an interaction trace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ThomasKilmannMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ThomasKilmannMode = mode
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
        mode: ThomasKilmannMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> ConflictStyleSelection:
        active_mode: ThomasKilmannMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="thomas_kilmann"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentInteractionTrace],
        *,
        mode: ThomasKilmannMode | None = None,
    ) -> Iterator[ConflictStyleSelection]:
        active_mode: ThomasKilmannMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="thomas_kilmann"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentInteractionTrace,
        mode: ThomasKilmannMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> ConflictStyleSelection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running thomas-kilmann diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        style_fit_audit: StyleFitAudit | None = None
        pattern_consistency_audit: PatternConsistencyAudit | None = None
        recommendations: list[StyleRecommendation] = []

        if mode == "quick":
            data = self._pass_quick(trace, trace_text, acc)
        elif mode == "standard":
            data = self._pass_analysis(trace, trace_text, acc=acc)
        else:  # forensic
            data = self._pass_analysis(trace, trace_text, acc=acc)

        observed = self._coerce_observed(data.get("observed_style"))
        optimal = self._coerce_style(data.get("optimal_style"))
        mismatch = self._coerce_float(data.get("style_mismatch"))
        assertiveness = self._coerce_float(data.get("assertiveness_score"))
        cooperativeness = self._coerce_float(data.get("cooperativeness_score"))
        scores = self._coerce_scores(data.get("observed_style_scores"))
        evidence = self._coerce_evidence(data.get("style_evidence", []))
        rationale = str(data.get("rationale", "")).strip() or "No rationale provided."

        if mode == "quick":
            top_iv_entry = data.get("top_recommendation")
            if top_iv_entry:
                try:
                    recommendations.append(StyleRecommendation(**top_iv_entry))
                except Exception as exc:
                    log.warning(
                        "Quick top_recommendation parse error: %s",
                        type(exc).__name__,
                    )
        elif mode == "standard":
            if observed != optimal:
                recommendations = self._pass_recommendations(
                    trace_text,
                    observed,
                    optimal,
                    mismatch,
                    acc=acc,
                )
        else:  # forensic
            style_fit_audit = self._pass_forensic_style_fit(
                trace.task, trace.outcome, trace_text, acc
            )
            pattern_consistency_audit = self._pass_forensic_consistency(trace_text, acc)
            if observed != optimal:
                recommendations = self._pass_forensic_recommendations(
                    observed,
                    optimal,
                    style_fit_audit,
                    pattern_consistency_audit,
                    acc,
                )

        severity = severity_from_mismatch(mismatch)
        profile_pattern = self._classify_profile_pattern(observed, optimal, mismatch, scores)

        composition = (
            self._build_composition_handoff(
                trace, profile_pattern, observed, optimal, recommendations
            )
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(observed, recommendations) if self.playbooks_enabled else []
        )

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = ConflictStyleSelection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    observed_style=observed,
                    optimal_style=optimal,
                    style_mismatch=mismatch,
                    assertiveness_score=assertiveness,
                    cooperativeness_score=cooperativeness,
                    observed_style_scores=scores,
                    style_evidence=evidence,
                    rationale=rationale,
                    recommendations=recommendations,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return ConflictStyleSelection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            observed_style=observed,
            optimal_style=optimal,
            style_mismatch=mismatch,
            assertiveness_score=assertiveness,
            cooperativeness_score=cooperativeness,
            observed_style_scores=scores,
            style_evidence=evidence,
            rationale=rationale,
            recommendations=recommendations,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            style_fit_audit=style_fit_audit,
            pattern_consistency_audit=pattern_consistency_audit,
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

    # --- Legacy surface preserved -------------------------------------

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
                    "prompt-injection pattern in trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_trace(self, trace: AgentInteractionTrace) -> str:
        lines = [
            f"Task: {trace.task}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            f"Task category: {trace.task_category or 'unspecified'}",
            "",
        ]
        for i, t in enumerate(trace.turns):
            lines.append(f"[turn {i + 1}] {t.role}: {t.content}")
        text = "\n".join(lines)
        if len(text) <= self.max_trace_chars:
            return text
        log.warning("Trace exceeds max_trace_chars; truncating")
        keep = self.max_trace_chars // 2 - 200
        return (
            text[:keep]
            + f"\n\n[... TRUNCATED ({len(text) - self.max_trace_chars} chars) ...]\n\n"
            + text[-keep:]
        )

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: ThomasKilmannMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=TK_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "thomas_kilmann"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_analysis(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = TK_ANALYSIS_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            task_category=trace.task_category or "unspecified",
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TK_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="analysis", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(
        self,
        trace: AgentInteractionTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            outcome=trace.outcome,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_recommendations(
        self,
        trace_text: str,
        observed: str,
        optimal: str,
        mismatch: float,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[StyleRecommendation]:
        prompt = RECOMMENDATIONS_PROMPT.format(
            observed_style=observed,
            optimal_style=optimal,
            style_mismatch=mismatch,
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TK_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="recommendations", mode="standard", acc=acc)
        data = extract_json_array(raw)
        recs: list[StyleRecommendation] = []
        for entry in data:
            try:
                recs.append(StyleRecommendation(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StyleRecommendation (%s)",
                    type(exc).__name__,
                )
        return recs

    def _coerce_observed(
        self, raw: Any
    ) -> Literal[
        "competing",
        "accommodating",
        "avoiding",
        "compromising",
        "collaborating",
        "mixed",
    ]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "competing",
            "accommodating",
            "avoiding",
            "compromising",
            "collaborating",
            "mixed",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        return "mixed"

    def _coerce_style(
        self, raw: Any
    ) -> Literal["competing", "accommodating", "avoiding", "compromising", "collaborating"]:
        if isinstance(raw, str) and raw.strip().lower() in STYLES:
            return raw.strip().lower()  # type: ignore[return-value]
        return "collaborating"

    def _coerce_float(self, raw: Any) -> float:
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))

    def _coerce_scores(self, raw: Any) -> dict[str, float]:
        scores: dict[str, float] = {s: 0.0 for s in STYLES}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in scores:
                    try:
                        scores[k] = max(0.0, min(1.0, float(v)))
                    except (TypeError, ValueError):
                        continue
        return scores

    def _coerce_evidence(self, raw: list[Any]) -> list[StyleScore]:
        evidence: list[StyleScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                evidence.append(StyleScore(**entry))
            except Exception as exc:
                log.warning("Dropping malformed StyleScore (%s)", type(exc).__name__)
        seen = {e.style for e in evidence}
        for s in STYLES:
            if s not in seen:
                evidence.append(
                    StyleScore(
                        style=s,  # type: ignore[arg-type]
                        score=0.0,
                        explanation="Not observed in the trace.",
                        evidence_quotes=[],
                    )
                )
        order = {s: i for i, s in enumerate(STYLES)}
        evidence.sort(key=lambda e: order.get(e.style, len(STYLES)))
        return evidence

    # --- v0.2.0 forensic passes ---------------------------------------

    def _pass_forensic_style_fit(
        self, task: str, outcome: str, trace_text: str, acc: "_PipelineAcc"
    ) -> StyleFitAudit | None:
        prompt = assemble_prompt(
            FORENSIC_STYLE_FIT_PROMPT, task=task, outcome=outcome, trace=trace_text
        )
        raw = self._call(prompt, pass_name="forensic_style_fit", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return StyleFitAudit(**obj)
        except Exception as exc:
            log.warning("StyleFitAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_consistency(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> PatternConsistencyAudit | None:
        prompt = assemble_prompt(FORENSIC_CONSISTENCY_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_consistency", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return PatternConsistencyAudit(**obj)
        except Exception as exc:
            log.warning("PatternConsistencyAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_recommendations(
        self,
        observed: str,
        optimal: str,
        style_fit_audit: StyleFitAudit | None,
        pattern_consistency_audit: PatternConsistencyAudit | None,
        acc: "_PipelineAcc",
    ) -> list[StyleRecommendation]:
        prompt = assemble_prompt(
            FORENSIC_RECOMMENDATIONS_PROMPT,
            observed_style=observed,
            optimal_style=optimal,
            style_fit_audit=style_fit_audit.model_dump() if style_fit_audit else None,
            pattern_consistency_audit=pattern_consistency_audit.model_dump()
            if pattern_consistency_audit
            else None,
        )
        raw = self._call(
            prompt,
            pass_name="forensic_recommendations",
            mode="forensic",
            acc=acc,
        )
        data = extract_json_array(raw)
        recs: list[StyleRecommendation] = []
        for entry in data:
            try:
                recs.append(StyleRecommendation(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed StyleRecommendation (%s)",
                    type(exc).__name__,
                )
        return recs

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        observed: str,
        optimal: str,
        mismatch: float,
        scores: dict[str, float],
    ) -> ThomasKilmannProfilePattern:
        if mismatch < 0.15 and observed == optimal:
            return "well_matched"
        if observed == "competing" and optimal == "collaborating":
            return "competing_when_collaborating"
        if observed == "accommodating" and optimal == "competing":
            return "accommodating_when_competing"
        if observed == "avoiding" and optimal == "collaborating":
            return "avoiding_when_collaborating"
        if observed == "compromising":
            return "default_compromising"
        if observed == "mixed":
            return "mixed_inconsistent"
        # Rigid single style: one style >= 0.8 across the board.
        top_score = max(scores.values(), default=0.0)
        if top_score >= 0.8:
            return "rigid_single_style"
        if mismatch >= 0.5:
            return "context_blind"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: AgentInteractionTrace,
        profile_pattern: ThomasKilmannProfilePattern,
        observed: str,
        optimal: str,
        recommendations: list[StyleRecommendation],
    ) -> ComposedPatternHandoff:
        provisional = ConflictStyleSelection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            observed_style=cast(Any, observed),
            optimal_style=cast(Any, optimal),
            style_mismatch=0.5,
            assertiveness_score=0.5,
            cooperativeness_score=0.5,
            observed_style_scores={},
            style_evidence=[],
            rationale="",
            recommendations=recommendations,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "observed_style": observed,
            "optimal_style": optimal,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
            "task_category": trace.task_category,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self,
        observed: str,
        recommendations: list[StyleRecommendation],
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for rec in recommendations:
            pb = find_playbook_for_intervention(observed, rec.intervention_type)
            if pb is not None and (pb.style, pb.failure_mode) not in attached:
                attached[(pb.style, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
ConflictStyleSelector = ConflictStyleAnalyzer


class ConflictStyleAnalyzerAsync:
    """Async mirror of :class:`ConflictStyleAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ThomasKilmannMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ThomasKilmannMode = mode
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
        mode: ThomasKilmannMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> ConflictStyleSelection:
        active_mode: ThomasKilmannMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = ConflictStyleAnalyzer(
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


_legacy_log = logging.getLogger("vstack.thomas_kilmann.generator")
_legacy_log.addHandler(logging.NullHandler())
