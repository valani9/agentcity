"""BiasStackAnalyzer: multi-mode Kahneman/Tversky bias diagnostic.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``BiasStackDetector`` aliased to
``BiasStackAnalyzer``.
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
    BIAS_SCORING_PROMPT,
    BIAS_SYSTEM_PROMPT,
    FORENSIC_ANCHORING_PROMPT,
    FORENSIC_CALIBRATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    assemble_prompt,
)
from .schema import (
    BIASES,
    AgentReasoningTrace,
    AnchoringTraceAudit,
    AttachedPlaybook,
    BiasEvidence,
    BiasIntervention,
    BiasStackDetection,
    BiasStackMode,
    BiasStackProfilePattern,
    ComposedPatternHandoff,
    ConfidenceCalibrationAudit,
    severity_from_bias,
)

log = get_logger("vstack.bias_stack.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class BiasStackAnalyzer:
    """Run the Kahneman/Tversky bias stack diagnostic on a reasoning trace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: BiasStackMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: BiasStackMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentReasoningTrace,
        *,
        mode: BiasStackMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> BiasStackDetection:
        active_mode: BiasStackMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="bias_stack"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentReasoningTrace],
        *,
        mode: BiasStackMode | None = None,
    ) -> Iterator[BiasStackDetection]:
        active_mode: BiasStackMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="bias_stack"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentReasoningTrace,
        mode: BiasStackMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> BiasStackDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running bias-stack diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        calibration_audit: ConfidenceCalibrationAudit | None = None
        anchoring_audit: AnchoringTraceAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, trace_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_biases(trace, trace_text, acc=acc)
            scores = self._build_scores(evidence)
            dominant = self._dominant_bias(scores)
            interventions = self._pass_2_interventions(
                trace, trace_text, evidence, dominant, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_biases(trace, trace_text, acc=acc)
            scores = self._build_scores(evidence)
            dominant = self._dominant_bias(scores)
            calibration_audit = self._pass_forensic_calibration(
                trace_text, trace.outcome, trace.success, acc
            )
            anchoring_audit = self._pass_forensic_anchoring(trace_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence, dominant, calibration_audit, anchoring_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown BiasStackMode: {mode!r}")

        scores = self._build_scores(evidence)
        dominant = self._dominant_bias(scores)
        quality = self._reasoning_quality(scores)
        profile_pattern = self._classify_profile_pattern(scores, dominant, quality)
        severity = severity_from_bias(max(scores.values(), default=0.0))

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
                provisional = BiasStackDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    dominant_bias=dominant,
                    bias_scores=scores,
                    biases=evidence,
                    interventions=interventions,
                    overall_reasoning_quality=quality,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return BiasStackDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_bias=dominant,
            bias_scores=scores,
            biases=evidence,
            interventions=interventions,
            overall_reasoning_quality=quality,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            calibration_audit=calibration_audit,
            anchoring_audit=anchoring_audit,
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

    def _validate_trace(self, trace: AgentReasoningTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentReasoningTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentReasoningTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("AgentReasoningTrace.steps cannot be empty.")

    def _scan_injection(self, trace: AgentReasoningTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
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
                    "prompt-injection pattern in reasoning trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_trace(self, trace: AgentReasoningTrace) -> str:
        lines = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        for i, s in enumerate(trace.steps):
            conf = f" conf={s.confidence:.2f}" if s.confidence is not None else ""
            lines.append(f"[step {i + 1}] ({s.type}){conf}: {s.content}")
        text = "\n".join(lines)
        if len(text) <= self.max_trace_chars:
            return text
        log.warning("Reasoning trace exceeds max_trace_chars; truncating")
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
        mode: BiasStackMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=BIAS_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "bias_stack"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_biases(
        self,
        trace: AgentReasoningTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[BiasEvidence]:
        prompt = BIAS_SCORING_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=BIAS_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="biases", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[BiasEvidence] = []
        for entry in data:
            try:
                evidence.append(BiasEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed BiasEvidence (%s)", type(exc).__name__)
        seen = {ev.bias for ev in evidence}
        for b in BIASES:
            if b not in seen:
                evidence.append(
                    BiasEvidence(
                        bias=b,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {b: i for i, b in enumerate(BIASES)}
        evidence.sort(key=lambda e: order.get(e.bias, len(BIASES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: AgentReasoningTrace,
        trace_text: str,
        evidence: list[BiasEvidence],
        dominant: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[BiasIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant, evidence=evidence_text, trace=trace_text
        )
        if acc is None:
            raw = self._complete(prompt, system=BIAS_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[BiasIntervention] = []
        for entry in data:
            try:
                interventions.append(BiasIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed BiasIntervention (%s)", type(exc).__name__)
        return interventions

    def _build_scores(self, evidence: list[BiasEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {b: 0.0 for b in BIASES}
        for ev in evidence:
            scores[str(ev.bias)] = max(scores.get(str(ev.bias), 0.0), ev.score)
        return scores

    def _dominant_bias(
        self, scores: dict[str, float]
    ) -> Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
        "none-observed",
    ]:
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        # Anchoring wins tie-breaks: the upstream bias in the stack.
        for b in BIASES:
            if scores.get(b, 0.0) >= max_score - 0.05:
                return b  # type: ignore[return-value]
        return "none-observed"

    def _reasoning_quality(
        self, scores: dict[str, float]
    ) -> Literal["well-calibrated", "bias-prone", "severely-biased"]:
        max_score = max(scores.values(), default=0.0)
        if max_score > 0.6:
            return "severely-biased"
        if max_score > 0.3:
            return "bias-prone"
        return "well-calibrated"

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: AgentReasoningTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[BiasEvidence], BiasIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            outcome=trace.outcome,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        bias_raw = obj.get("biases", [])
        evidence: list[BiasEvidence] = []
        if isinstance(bias_raw, list):
            for entry in bias_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(BiasEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed BiasEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {ev.bias for ev in evidence}
        for b in BIASES:
            if b not in seen:
                evidence.append(
                    BiasEvidence(
                        bias=b,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {b: i for i, b in enumerate(BIASES)}
        evidence.sort(key=lambda e: order.get(e.bias, len(BIASES)))
        top_iv: BiasIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = BiasIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_calibration(
        self,
        trace_text: str,
        outcome: str,
        success: bool,
        acc: "_PipelineAcc",
    ) -> ConfidenceCalibrationAudit | None:
        prompt = assemble_prompt(
            FORENSIC_CALIBRATION_PROMPT,
            trace=trace_text,
            outcome=outcome,
            success=success,
        )
        raw = self._call(prompt, pass_name="forensic_calibration", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ConfidenceCalibrationAudit(**obj)
        except Exception as exc:
            log.warning("ConfidenceCalibrationAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_anchoring(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> AnchoringTraceAudit | None:
        prompt = assemble_prompt(FORENSIC_ANCHORING_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_anchoring", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return AnchoringTraceAudit(**obj)
        except Exception as exc:
            log.warning("AnchoringTraceAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[BiasEvidence],
        dominant: str,
        calibration_audit: ConfidenceCalibrationAudit | None,
        anchoring_audit: AnchoringTraceAudit | None,
        acc: "_PipelineAcc",
    ) -> list[BiasIntervention]:
        if dominant == "none-observed":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=dominant,
            evidence=[e.model_dump() for e in evidence],
            calibration_audit=calibration_audit.model_dump() if calibration_audit else None,
            anchoring_audit=anchoring_audit.model_dump() if anchoring_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[BiasIntervention] = []
        for entry in data:
            try:
                interventions.append(BiasIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed BiasIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        scores: dict[str, float],
        dominant: str,
        quality: str,
    ) -> BiasStackProfilePattern:
        if quality == "well-calibrated":
            return "well_calibrated"
        all_high = sum(1 for s in scores.values() if s >= 0.6)
        if all_high == 4:
            return "full_stack_severe"
        if scores.get("anchoring", 0.0) >= 0.6 and scores.get("overconfidence", 0.0) >= 0.6:
            return "anchoring_overconfidence_pair"
        if (
            scores.get("confirmation", 0.0) >= 0.6
            and scores.get("escalation-of-commitment", 0.0) >= 0.6
        ):
            return "confirmation_escalation_pair"
        mapping: dict[str, BiasStackProfilePattern] = {
            "anchoring": "anchoring_dominant",
            "overconfidence": "overconfidence_dominant",
            "confirmation": "confirmation_dominant",
            "escalation-of-commitment": "escalation_dominant",
        }
        if dominant in mapping:
            return mapping[dominant]
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: AgentReasoningTrace,
        profile_pattern: BiasStackProfilePattern,
        dominant: str,
        interventions: list[BiasIntervention],
    ) -> ComposedPatternHandoff:
        provisional = BiasStackDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_bias=cast(Any, dominant),
            bias_scores={},
            biases=[],
            interventions=interventions,
            overall_reasoning_quality="bias-prone",
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_bias": dominant,
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

    def _attach_playbooks(self, interventions: list[BiasIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_bias)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.bias, pb.failure_mode) not in attached:
                attached[(pb.bias, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
BiasStackDetector = BiasStackAnalyzer


class BiasStackAnalyzerAsync:
    """Async mirror of :class:`BiasStackAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: BiasStackMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: BiasStackMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentReasoningTrace,
        *,
        mode: BiasStackMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> BiasStackDetection:
        active_mode: BiasStackMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = BiasStackAnalyzer(
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


_legacy_log = logging.getLogger("vstack.bias_stack.generator")
_legacy_log.addHandler(logging.NullHandler())
