"""FeedbackTriggerAnalyzer: multi-mode Stone & Heen 3-trigger diagnostic.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``FeedbackTriggerDetector`` aliased
to ``FeedbackTriggerAnalyzer``.
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
    FORENSIC_DEFENSE_PATTERN_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SOURCE_ATTRIBUTION_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    TRIGGER_SCORING_PROMPT,
    TRIGGER_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    TRIGGERS,
    AttachedPlaybook,
    ComposedPatternHandoff,
    DefensePatternAudit,
    FeedbackInteractionTrace,
    FeedbackProfilePattern,
    FeedbackTriggerDetection,
    FeedbackTriggersMode,
    SourceAttributionAudit,
    TriggerEvidence,
    TriggerIntervention,
    severity_from_trigger,
)

log = get_logger("vstack.feedback_triggers.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class FeedbackTriggerAnalyzer:
    """Run the Stone & Heen 3-trigger diagnostic on a FeedbackInteractionTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: FeedbackTriggersMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: FeedbackTriggersMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: FeedbackInteractionTrace,
        *,
        mode: FeedbackTriggersMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> FeedbackTriggerDetection:
        active_mode: FeedbackTriggersMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="feedback_triggers"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[FeedbackInteractionTrace],
        *,
        mode: FeedbackTriggersMode | None = None,
    ) -> Iterator[FeedbackTriggerDetection]:
        active_mode: FeedbackTriggersMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="feedback_triggers"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: FeedbackInteractionTrace,
        mode: FeedbackTriggersMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> FeedbackTriggerDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        exchange_text = self._serialize_exchange(trace)
        started = time.monotonic()
        log.info(
            "Running Stone & Heen 3-trigger diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        defense_audit: DefensePatternAudit | None = None
        source_audit: SourceAttributionAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, exchange_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_triggers(trace, exchange_text, acc=acc)
            scores = self._build_trigger_scores(evidence)
            dominant = self._dominant_trigger(scores)
            interventions = self._pass_2_interventions(
                trace, exchange_text, evidence, dominant, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_triggers(trace, exchange_text, acc=acc)
            scores = self._build_trigger_scores(evidence)
            dominant = self._dominant_trigger(scores)
            defense_audit = self._pass_forensic_defense_pattern(exchange_text, acc)
            source_audit = self._pass_forensic_source_attribution(exchange_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence, dominant, defense_audit, source_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown FeedbackTriggersMode: {mode!r}")

        scores = self._build_trigger_scores(evidence)
        dominant = self._dominant_trigger(scores)
        quality = self._feedback_intake_quality(scores, trace.feedback_incorporated)
        profile_pattern = self._classify_profile_pattern(
            scores, dominant, quality, trace.feedback_incorporated
        )
        severity = severity_from_trigger(max(scores.values(), default=0.0))

        composition = (
            self._build_composition_handoff(trace, profile_pattern, dominant, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = FeedbackTriggerDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    dominant_trigger=dominant,
                    trigger_scores=scores,
                    triggers=evidence,
                    interventions=interventions,
                    feedback_intake_quality=quality,
                    feedback_incorporated=trace.feedback_incorporated,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return FeedbackTriggerDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_trigger=dominant,
            trigger_scores=scores,
            triggers=evidence,
            interventions=interventions,
            feedback_intake_quality=quality,
            generator_model=self.model,
            feedback_incorporated=trace.feedback_incorporated,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            defense_pattern_audit=defense_audit,
            source_attribution_audit=source_audit,
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

    def _validate_trace(self, trace: FeedbackInteractionTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("FeedbackInteractionTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("FeedbackInteractionTrace.outcome cannot be empty.")
        if not trace.messages:
            raise ValueError("FeedbackInteractionTrace.messages cannot be empty.")

    def _scan_injection(self, trace: FeedbackInteractionTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        for i, m in enumerate(trace.messages):
            targets.append((f"messages[{i}].content", m.content))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in exchange",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_exchange(self, trace: FeedbackInteractionTrace) -> str:
        lines = []
        for i, m in enumerate(trace.messages):
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else f"[msg {i + 1}] "
            tag = " (FEEDBACK)" if m.is_feedback else ""
            lines.append(f"{ts}{m.source}{tag}: {m.content}")
        text = "\n".join(lines)
        if len(text) <= self.max_trace_chars:
            return text
        log.warning("Exchange exceeds max_trace_chars; truncating")
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
        mode: FeedbackTriggersMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=TRIGGER_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "feedback_triggers"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_triggers(
        self,
        trace: FeedbackInteractionTrace,
        exchange_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[TriggerEvidence]:
        prompt = TRIGGER_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            feedback_incorporated=trace.feedback_incorporated,
            exchange=exchange_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TRIGGER_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="triggers", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[TriggerEvidence] = []
        for entry in data:
            try:
                evidence.append(TriggerEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TriggerEvidence (%s)", type(exc).__name__)
        seen = {ev.trigger for ev in evidence}
        for t in TRIGGERS:
            if t not in seen:
                evidence.append(
                    TriggerEvidence(
                        trigger=t,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this trigger in the exchange.",
                        evidence_quotes=[],
                    )
                )
        order = {t: i for i, t in enumerate(TRIGGERS)}
        evidence.sort(key=lambda e: order.get(e.trigger, len(TRIGGERS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: FeedbackInteractionTrace,
        exchange_text: str,
        evidence: list[TriggerEvidence],
        dominant: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[TriggerIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            exchange=exchange_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TRIGGER_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[TriggerIntervention] = []
        for entry in data:
            try:
                interventions.append(TriggerIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TriggerIntervention (%s)", type(exc).__name__)
        return interventions

    def _build_trigger_scores(self, evidence: list[TriggerEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {t: 0.0 for t in TRIGGERS}
        for ev in evidence:
            scores[str(ev.trigger)] = max(scores.get(str(ev.trigger), 0.0), ev.score)
        return scores

    def _dominant_trigger(
        self, scores: dict[str, float]
    ) -> Literal["truth", "relationship", "identity", "none-observed"]:
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        # Truth wins ties (cleanest interventions).
        for t in TRIGGERS:
            if scores.get(t, 0.0) >= max_score - 0.05:
                return t  # type: ignore[return-value]
        return "none-observed"

    def _feedback_intake_quality(
        self, scores: dict[str, float], feedback_incorporated: bool
    ) -> Literal["absorbs-feedback", "trigger-prone", "feedback-rejecting"]:
        max_score = max(scores.values(), default=0.0)
        if feedback_incorporated and max_score <= 0.3:
            return "absorbs-feedback"
        if max_score >= 0.6:
            return "feedback-rejecting"
        return "trigger-prone"

    # v0.0.x legacy alias for the intake-quality classifier.
    def _intake_quality(
        self, scores: dict[str, float], feedback_incorporated: bool
    ) -> Literal["absorbs-feedback", "trigger-prone", "feedback-rejecting"]:
        return self._feedback_intake_quality(scores, feedback_incorporated)

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: FeedbackInteractionTrace,
        exchange_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[TriggerEvidence], TriggerIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            feedback_incorporated=trace.feedback_incorporated,
            exchange=exchange_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        triggers_raw = obj.get("triggers", [])
        evidence: list[TriggerEvidence] = []
        if isinstance(triggers_raw, list):
            for entry in triggers_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(TriggerEvidence(**entry))
                except Exception as exc:
                    log.warning("Dropping malformed TriggerEvidence (%s)", type(exc).__name__)
        seen = {ev.trigger for ev in evidence}
        for t in TRIGGERS:
            if t not in seen:
                evidence.append(
                    TriggerEvidence(
                        trigger=t,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {t: i for i, t in enumerate(TRIGGERS)}
        evidence.sort(key=lambda e: order.get(e.trigger, len(TRIGGERS)))
        top_iv: TriggerIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = TriggerIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_defense_pattern(
        self, exchange_text: str, acc: "_PipelineAcc"
    ) -> DefensePatternAudit | None:
        prompt = assemble_prompt(FORENSIC_DEFENSE_PATTERN_PROMPT, exchange=exchange_text)
        raw = self._call(prompt, pass_name="forensic_defense", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return DefensePatternAudit(**obj)
        except Exception as exc:
            log.warning("DefensePatternAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_source_attribution(
        self, exchange_text: str, acc: "_PipelineAcc"
    ) -> SourceAttributionAudit | None:
        prompt = assemble_prompt(FORENSIC_SOURCE_ATTRIBUTION_PROMPT, exchange=exchange_text)
        raw = self._call(prompt, pass_name="forensic_source_attribution", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return SourceAttributionAudit(**obj)
        except Exception as exc:
            log.warning("SourceAttributionAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[TriggerEvidence],
        dominant: str,
        defense_audit: DefensePatternAudit | None,
        source_audit: SourceAttributionAudit | None,
        acc: "_PipelineAcc",
    ) -> list[TriggerIntervention]:
        if dominant == "none-observed":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=dominant,
            evidence=[e.model_dump() for e in evidence],
            defense_pattern_audit=defense_audit.model_dump() if defense_audit else None,
            source_attribution_audit=source_audit.model_dump() if source_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[TriggerIntervention] = []
        for entry in data:
            try:
                interventions.append(TriggerIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TriggerIntervention (%s)", type(exc).__name__)
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        scores: dict[str, float],
        dominant: str,
        quality: str,
        feedback_incorporated: bool,
    ) -> FeedbackProfilePattern:
        if quality == "absorbs-feedback":
            return "absorbing_baseline"
        all_high = sum(1 for s in scores.values() if s >= 0.6)
        if all_high >= 2:
            return "multi_triggered_resistant"
        if quality == "feedback-rejecting":
            mapping: dict[str, FeedbackProfilePattern] = {
                "truth": "truth_triggered_defensive",
                "relationship": "relationship_triggered_rejection",
                "identity": "identity_triggered_collapse",
            }
            if dominant in mapping:
                return mapping[dominant]
        if feedback_incorporated and max(scores.values(), default=0.0) >= 0.4:
            return "performative_acknowledgement"
        if dominant in ("truth", "relationship") and scores.get(dominant, 0.0) >= 0.5:
            return "deflection_pattern"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: FeedbackInteractionTrace,
        profile_pattern: FeedbackProfilePattern,
        dominant: str,
        interventions: list[TriggerIntervention],
    ) -> ComposedPatternHandoff:
        provisional = FeedbackTriggerDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_trigger=cast(Any, dominant),
            trigger_scores={},
            triggers=[],
            interventions=interventions,
            feedback_intake_quality="trigger-prone",
            feedback_incorporated=trace.feedback_incorporated,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_trigger": dominant,
            "profile_pattern": profile_pattern,
            "feedback_incorporated": trace.feedback_incorporated,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[TriggerIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_trigger)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.trigger, pb.failure_mode) not in attached:
                attached[(pb.trigger, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
FeedbackTriggerDetector = FeedbackTriggerAnalyzer


class FeedbackTriggerAnalyzerAsync:
    """Async mirror of :class:`FeedbackTriggerAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: FeedbackTriggersMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: FeedbackTriggersMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: FeedbackInteractionTrace,
        *,
        mode: FeedbackTriggersMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> FeedbackTriggerDetection:
        active_mode: FeedbackTriggersMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = FeedbackTriggerAnalyzer(
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


_legacy_log = logging.getLogger("vstack.feedback_triggers.generator")
_legacy_log.addHandler(logging.NullHandler())
