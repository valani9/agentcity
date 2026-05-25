"""AARAnalyzer: v0.2.0 multi-mode AAR generator with full production infra.

Wraps the legacy AARGenerator pipeline (4 LLM passes: goal extraction +
results extraction + lessons derivation + next-step generation) and
adds:
  - Three pipeline modes (quick / standard / forensic).
  - 7-point severity scale + profile-pattern classification.
  - Forensic-mode audits (Trace Quality, Lesson Groundedness).
  - Composition manifest + calibration + playbooks + async mirror.

The existing AARGenerator class is preserved unchanged; this module
sits alongside it so any downstream code importing AARGenerator
continues to work.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine, Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol, cast

from ._calibration import compare_to_baseline, load_baseline
from ._composition import recommended_downstream, recommended_upstream
from ._guards import detect_injection
from ._logging import get_logger, new_run_id, run_context
from ._playbooks import find_playbook_for_intervention
from ._retry import with_retry
from ._telemetry import record_llm_call, time_call
from .clients import LLMUsage
from .generator import AARGenerator
from .schema import (
    AAR,
    AARMode,
    AARProfilePattern,
    AgentTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    Lesson,
    LessonGroundednessAudit,
    NextStep,
    TraceQualityAudit,
    severity_from_gap,
)

log = get_logger("vstack.aar.analyzer")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class _CountingClient:
    """Wraps an LLM client and counts every call into a PipelineAcc."""

    def __init__(
        self,
        inner: LLMClient,
        acc: "_PipelineAcc",
        model: str,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> None:
        self._inner = inner
        self._acc = acc
        self._model = model
        self._cost_in = cost_per_1k_input
        self._cost_out = cost_per_1k_output
        self.last_usage = getattr(inner, "last_usage", None)

    def complete(self, prompt: str, system: str | None = None) -> str:
        with time_call() as t:
            raw = self._inner.complete(prompt, system=system)
        usage = cast(LLMUsage | None, getattr(self._inner, "last_usage", None))
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        total_tokens = (
            int(getattr(usage, "total_tokens", 0) or 0) if usage else input_tokens + output_tokens
        )
        cost = (input_tokens / 1000.0) * self._cost_in + (output_tokens / 1000.0) * self._cost_out
        record_llm_call(
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            elapsed_ms=t["elapsed_ms"],
            extra={"pattern": "aar"},
        )
        self._acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw


class AARAnalyzer:
    """Multi-mode AAR generator. Backward-compatible with AARGenerator."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: AARMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: AARMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentTrace,
        *,
        mode: AARMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> AAR:
        active_mode: AARMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="aar"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentTrace],
        *,
        mode: AARMode | None = None,
    ) -> Iterator[AAR]:
        active_mode: AARMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="aar"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentTrace,
        mode: AARMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> AAR:
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        acc = _PipelineAcc()
        counting_client = _CountingClient(
            self.llm,
            acc,
            self.model,
            self.cost_per_1k_input,
            self.cost_per_1k_output,
        )
        legacy = AARGenerator(
            llm_client=counting_client,
            model=self.model,
            max_retries=self.max_retries,
            max_trace_chars=self.max_trace_chars,
        )

        if mode == "quick":
            # Quick mode: minimal AAR with limited next-steps.
            aar = legacy.generate(trace)
            aar.next_steps = aar.next_steps[:1]
        elif mode == "standard":
            aar = legacy.generate(trace)
        else:  # forensic
            aar = legacy.generate(trace)
            aar.trace_quality_audit = self._compute_trace_quality_audit(trace)
            aar.lesson_groundedness_audit = self._compute_lesson_groundedness_audit(aar.lessons)

        gap_score = self._compute_gap_score(trace, aar.lessons, aar.next_steps)
        profile_pattern = self._classify_profile_pattern(trace, aar.lessons, gap_score)
        severity = severity_from_gap(gap_score)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, aar.next_steps)
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(profile_pattern, aar.next_steps)
            if self.playbooks_enabled
            else []
        )

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = AAR(
                    goal=aar.goal,
                    results=aar.results,
                    lessons=aar.lessons,
                    next_steps=aar.next_steps,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                    gap_score=gap_score,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        # Mutate v0.2.0 fields on the existing AAR (preserves goal/results/lessons/next_steps).
        aar.mode = mode
        aar.severity = severity
        aar.profile_pattern = profile_pattern
        aar.gap_score = gap_score
        aar.baseline = baseline
        aar.composition_handoff = composition
        aar.attached_playbooks = playbooks
        aar.run_id = run_id
        aar.cost_usd = acc.cost_usd
        aar.tokens_total = acc.tokens_total
        aar.tokens_input = acc.tokens_input
        aar.tokens_output = acc.tokens_output
        aar.llm_calls = acc.llm_calls
        aar.elapsed_ms = elapsed_ms
        aar.injection_detected = injection_detected
        return aar

    # --- Helpers ---------------------------------------------------------

    def _scan_injection(self, trace: AgentTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("goal", trace.goal),
            ("outcome", trace.outcome),
        ]
        for i, s in enumerate(trace.steps):
            targets.append((f"steps[{i}].content", s.content))
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

    def _compute_gap_score(
        self,
        trace: AgentTrace,
        lessons: list[Lesson],
        next_steps: list[NextStep],
    ) -> float:
        # Heuristic: failure + many lessons + many next steps => high gap.
        if trace.success and not lessons:
            return 0.05
        if trace.success and len(lessons) <= 2:
            return 0.25
        if trace.success:
            return 0.4
        # Failure path.
        base = 0.6
        bump = min(0.3, 0.05 * len(lessons) + 0.05 * len(next_steps))
        return round(min(1.0, base + bump), 2)

    def _classify_profile_pattern(
        self,
        trace: AgentTrace,
        lessons: list[Lesson],
        gap_score: float,
    ) -> AARProfilePattern:
        if trace.success and gap_score < 0.2:
            return "success_aligned"
        if trace.success and gap_score < 0.5:
            return "partial_success"
        if not trace.success and gap_score >= 0.8:
            return "total_failure"
        # Examine lesson signatures.
        lesson_text = " ".join(
            (lesson.pattern + " " + lesson.description).lower() for lesson in lessons
        )
        if any(k in lesson_text for k in ("scope", "wrong goal", "different problem", "misread")):
            return "scope_mismatch"
        if any(k in lesson_text for k in ("loop", "retry", "stuck", "thrash", "escalation")):
            return "retry_thrashing"
        if any(k in lesson_text for k in ("cost", "expensive", "token", "budget")):
            return "cost_overrun"
        if any(k in lesson_text for k in ("deadline", "latency", "slow", "timeout")):
            return "deadline_missed"
        if not trace.success:
            return "total_failure"
        return "indeterminate"

    def _compute_trace_quality_audit(self, trace: AgentTrace) -> TraceQualityAudit:
        tool_calls = sum(1 for s in trace.steps if s.type == "tool_call")
        decisions = sum(1 for s in trace.steps if s.type == "decision")
        observations = sum(1 for s in trace.steps if s.type == "observation")
        # Completeness: has goal+outcome+steps, plus optional cost/latency/retries.
        completeness = 0.4  # baseline: goal + outcome
        if trace.steps:
            completeness += 0.2
        if trace.cost_usd is not None:
            completeness += 0.1
        if trace.latency_seconds is not None:
            completeness += 0.1
        if trace.retry_count is not None:
            completeness += 0.1
        if tool_calls > 0 and decisions > 0 and observations > 0:
            completeness += 0.1
        return TraceQualityAudit(
            step_count=len(trace.steps),
            tool_call_count=tool_calls,
            decision_count=decisions,
            observation_count=observations,
            has_cost=trace.cost_usd is not None,
            has_latency=trace.latency_seconds is not None,
            has_retry_count=trace.retry_count is not None,
            completeness_estimate=round(min(1.0, completeness), 2),
            explanation=("Computed from trace metadata; richer traces support richer AARs."),
        )

    def _compute_lesson_groundedness_audit(self, lessons: list[Lesson]) -> LessonGroundednessAudit:
        with_anchor = sum(1 for lesson in lessons if lesson.framework_anchor.strip())
        with_links = sum(1 for lesson in lessons if lesson.cross_pattern_links)
        # Ground = lesson cites a framework anchor (the most concrete signal).
        grounded = with_anchor
        ungrounded = max(0, len(lessons) - grounded)
        estimate = round(min(1.0, with_anchor / max(1, len(lessons))), 2) if lessons else 0.0
        return LessonGroundednessAudit(
            grounded_lesson_count=grounded,
            ungrounded_lesson_count=ungrounded,
            lessons_with_framework_anchor=with_anchor,
            lessons_with_cross_pattern_links=with_links,
            groundedness_estimate=estimate,
            explanation=("Groundedness = fraction of lessons carrying a framework anchor."),
        )

    def _build_composition_handoff(
        self,
        trace: AgentTrace,
        profile_pattern: AARProfilePattern,
        next_steps: list[NextStep],
    ) -> ComposedPatternHandoff:
        provisional = AAR(
            goal=trace.goal,
            results=trace.outcome,
            lessons=[],
            next_steps=next_steps,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "framework": trace.agent_framework,
            "agent_id": trace.agent_id,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self,
        profile_pattern: AARProfilePattern,
        next_steps: list[NextStep],
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for step in next_steps:
            pb = find_playbook_for_intervention(profile_pattern, step.intervention_type)
            if pb is not None and (pb.profile, pb.failure_mode) not in attached:
                attached[(pb.profile, pb.failure_mode)] = pb
        return list(attached.values())


class AARAnalyzerAsync:
    """Async mirror of :class:`AARAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: AARMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: AARMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentTrace,
        *,
        mode: AARMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> AAR:
        active_mode: AARMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = AARAnalyzer(
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


__all__ = [
    "AARAnalyzer",
    "AARAnalyzerAsync",
    "AsyncLLMClient",
    "LLMClient",
]
