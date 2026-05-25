"""TrustBalanceAnalyzer: multi-mode McAllister Cognitive vs Affective Trust diagnostic.

Three pipeline modes (quick / standard / forensic) with v0.2.0
production infrastructure. Backward-compatible: ``TrustBalanceDetector``
remains exported as alias for ``TrustBalanceAnalyzer``.
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
    DIMENSION_SCORING_PROMPT,
    FORENSIC_CARE_PROMPT,
    FORENSIC_COMPETENCE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    TRUST_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    TRUST_DIMENSIONS,
    AttachedPlaybook,
    CareSignalsAudit,
    ComposedPatternHandoff,
    CompetenceSignalsAudit,
    McAllisterMode,
    McAllisterProfilePattern,
    TrustBalanceDetection,
    TrustConversationTrace,
    TrustDimensionEvidence,
    TrustIntervention,
    severity_from_gap,
)

log = get_logger("vstack.mcallister_trust.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class TrustBalanceAnalyzer:
    """Run the Cognitive/Affective Trust diagnostic on a TrustConversationTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: McAllisterMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: McAllisterMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: TrustConversationTrace,
        *,
        mode: McAllisterMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> TrustBalanceDetection:
        active_mode: McAllisterMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="mcallister_trust"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[TrustConversationTrace],
        *,
        mode: McAllisterMode | None = None,
    ) -> Iterator[TrustBalanceDetection]:
        active_mode: McAllisterMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="mcallister_trust"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: TrustConversationTrace,
        mode: McAllisterMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> TrustBalanceDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        conversation_text = self._serialize_conversation(trace)
        started = time.monotonic()
        log.info(
            "Running McAllister trust diagnostic (mode=%s) for agent %s (turns=%d, success=%s)",
            mode,
            trace.agent_id or "<unknown>",
            len(trace.turns),
            trace.success,
        )

        acc = _PipelineAcc()
        competence_audit: CompetenceSignalsAudit | None = None
        care_audit: CareSignalsAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, conversation_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_dimensions(trace, conversation_text, acc=acc)
            scores = self._build_scores(evidence)
            quality = self._trust_quality(scores)
            interventions = self._pass_2_interventions(
                trace, conversation_text, evidence, scores, quality, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_dimensions(trace, conversation_text, acc=acc)
            scores = self._build_scores(evidence)
            quality = self._trust_quality(scores)
            competence_audit = self._pass_forensic_competence(conversation_text, acc)
            care_audit = self._pass_forensic_care(conversation_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence, scores, quality, competence_audit, care_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown McAllisterMode: {mode!r}")

        scores = self._build_scores(evidence)
        balance = round(scores.get("cognitive", 0.0) - scores.get("affective", 0.0), 2)
        dominant = self._dominant_dimension(scores)
        quality = self._trust_quality(scores)
        profile_pattern = self._classify_profile_pattern(scores, quality)
        max_gap = max(
            (1.0 - s for s in scores.values()),
            default=0.0,
        )
        severity = severity_from_gap(max_gap)

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
                provisional = TrustBalanceDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    dominant_dimension=dominant,
                    dimension_scores=scores,
                    dimensions=evidence,
                    trust_balance=balance,
                    trust_quality=quality,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return TrustBalanceDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_dimension=dominant,
            dimension_scores=scores,
            dimensions=evidence,
            trust_balance=balance,
            trust_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            competence_audit=competence_audit,
            care_audit=care_audit,
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

    # --- Legacy v0.0.x surface preserved -------------------------------

    def _validate_trace(self, trace: TrustConversationTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("TrustConversationTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("TrustConversationTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("TrustConversationTrace.turns cannot be empty.")

    def _scan_injection(self, trace: TrustConversationTrace) -> bool:
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
                    "prompt-injection pattern in conversation field",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_conversation(self, trace: TrustConversationTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        turn_lines: list[str] = []
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
            "Conversation exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... CONVERSATION TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: McAllisterMode,
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
            extra={"pass": pass_name, "mode": mode, "pattern": "mcallister_trust"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_dimensions(
        self,
        trace: TrustConversationTrace,
        conversation_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[TrustDimensionEvidence]:
        prompt = DIMENSION_SCORING_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            user_satisfaction=(
                f"{trace.user_satisfaction:.2f}"
                if trace.user_satisfaction is not None
                else "(not measured)"
            ),
            conversation=conversation_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=TRUST_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="dimensions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[TrustDimensionEvidence] = []
        for entry in data:
            try:
                evidence.append(TrustDimensionEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed TrustDimensionEvidence (%s)",
                    type(exc).__name__,
                )
        seen = {ev.dimension for ev in evidence}
        for dim in TRUST_DIMENSIONS:
            if dim not in seen:
                evidence.append(
                    TrustDimensionEvidence(
                        dimension=dim,  # type: ignore[arg-type]
                        score=0.0,
                        severity_of_gap="high",
                        explanation="No evidence of this dimension built in the conversation.",
                        evidence_quotes=[],
                    )
                )
        order = {dim: i for i, dim in enumerate(TRUST_DIMENSIONS)}
        evidence.sort(key=lambda e: order.get(e.dimension, len(TRUST_DIMENSIONS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: TrustConversationTrace,
        conversation_text: str,
        evidence: list[TrustDimensionEvidence],
        scores: dict[str, float],
        quality: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[TrustIntervention]:
        if quality == "balanced-trust":
            return []
        target = min(scores, key=lambda d: scores[d])
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            target_dimension=target,
            trust_quality=quality,
            evidence=evidence_text,
            conversation=conversation_text,
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

    def _build_scores(self, evidence: list[TrustDimensionEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {dim: 0.0 for dim in TRUST_DIMENSIONS}
        for ev in evidence:
            scores[str(ev.dimension)] = max(scores.get(str(ev.dimension), 0.0), ev.score)
        return scores

    def _dominant_dimension(
        self, scores: dict[str, float]
    ) -> Literal["cognitive", "affective", "balanced", "neither"]:
        cog = scores.get("cognitive", 0.0)
        aff = scores.get("affective", 0.0)
        if cog < 0.2 and aff < 0.2:
            return "neither"
        if abs(cog - aff) < 0.1:
            return "balanced"
        return "cognitive" if cog > aff else "affective"

    def _trust_quality(
        self, scores: dict[str, float]
    ) -> Literal[
        "balanced-trust",
        "cognitive-only",
        "warm-but-incompetent",
        "low-trust",
    ]:
        cog = scores.get("cognitive", 0.0)
        aff = scores.get("affective", 0.0)
        if cog < 0.3 and aff < 0.3:
            return "low-trust"
        if cog >= 0.5 and aff >= 0.5:
            return "balanced-trust"
        if cog >= 0.5 and aff < 0.3:
            return "cognitive-only"
        if aff >= 0.5 and cog < 0.3:
            return "warm-but-incompetent"
        if cog >= aff:
            return "cognitive-only"
        return "warm-but-incompetent"

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: TrustConversationTrace,
        conversation_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[TrustDimensionEvidence], TrustIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            conversation=conversation_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        dims_raw = obj.get("dimensions", [])
        evidence: list[TrustDimensionEvidence] = []
        if isinstance(dims_raw, list):
            for entry in dims_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(TrustDimensionEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed TrustDimensionEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {ev.dimension for ev in evidence}
        for dim in TRUST_DIMENSIONS:
            if dim not in seen:
                evidence.append(
                    TrustDimensionEvidence(
                        dimension=dim,  # type: ignore[arg-type]
                        score=0.0,
                        severity_of_gap="high",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {dim: i for i, dim in enumerate(TRUST_DIMENSIONS)}
        evidence.sort(key=lambda e: order.get(e.dimension, len(TRUST_DIMENSIONS)))
        top_iv: TrustIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = TrustIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_competence(
        self, conversation_text: str, acc: "_PipelineAcc"
    ) -> CompetenceSignalsAudit | None:
        prompt = assemble_prompt(FORENSIC_COMPETENCE_PROMPT, conversation=conversation_text)
        raw = self._call(prompt, pass_name="forensic_competence", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CompetenceSignalsAudit(**obj)
        except Exception as exc:
            log.warning("CompetenceSignalsAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_care(
        self, conversation_text: str, acc: "_PipelineAcc"
    ) -> CareSignalsAudit | None:
        prompt = assemble_prompt(FORENSIC_CARE_PROMPT, conversation=conversation_text)
        raw = self._call(prompt, pass_name="forensic_care", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CareSignalsAudit(**obj)
        except Exception as exc:
            log.warning("CareSignalsAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[TrustDimensionEvidence],
        scores: dict[str, float],
        quality: str,
        competence_audit: CompetenceSignalsAudit | None,
        care_audit: CareSignalsAudit | None,
        acc: "_PipelineAcc",
    ) -> list[TrustIntervention]:
        if quality == "balanced-trust":
            return []
        target = min(scores, key=lambda d: scores[d])
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            target_dimension=target,
            trust_quality=quality,
            evidence=[e.model_dump() for e in evidence],
            competence_audit=competence_audit.model_dump() if competence_audit else None,
            care_audit=care_audit.model_dump() if care_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[TrustIntervention] = []
        for entry in data:
            try:
                interventions.append(TrustIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed TrustIntervention (%s)", type(exc).__name__)
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self, scores: dict[str, float], quality: str
    ) -> McAllisterProfilePattern:
        cog = scores.get("cognitive", 0.0)
        aff = scores.get("affective", 0.0)
        if quality == "balanced-trust":
            return "balanced_high_trust"
        if quality == "cognitive-only":
            if cog >= 0.7 and aff < 0.2:
                return "asymmetric_cognitive_strong"
            if cog >= 0.5 and 0.3 <= aff < 0.5:
                return "cognitive_partial"
            return "cognitive_only"
        if quality == "warm-but-incompetent":
            if aff >= 0.5 and 0.3 <= cog < 0.5:
                return "affective_partial"
            return "warm_but_incompetent"
        if quality == "low-trust":
            return "low_trust"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: TrustConversationTrace,
        dominant: str,
        profile_pattern: McAllisterProfilePattern,
        interventions: list[TrustIntervention],
    ) -> ComposedPatternHandoff:
        provisional = TrustBalanceDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_dimension=cast(Any, dominant),
            dimension_scores={},
            dimensions=[],
            trust_balance=0.0,
            trust_quality="low-trust",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_dimension": dominant,
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
            target: str = cast(str, iv.target_dimension)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.dimension, pb.failure_mode) not in attached:
                attached[(pb.dimension, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
TrustBalanceDetector = TrustBalanceAnalyzer


class TrustBalanceAnalyzerAsync:
    """Async mirror of :class:`TrustBalanceAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: McAllisterMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: McAllisterMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: TrustConversationTrace,
        *,
        mode: McAllisterMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> TrustBalanceDetection:
        active_mode: McAllisterMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = TrustBalanceAnalyzer(
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


_legacy_log = logging.getLogger("vstack.mcallister_trust.generator")
_legacy_log.addHandler(logging.NullHandler())
