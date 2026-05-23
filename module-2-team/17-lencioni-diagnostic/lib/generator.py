"""LencioniAnalyzer: multi-mode Lencioni Five Dysfunctions diagnostic.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure: structured logging with run-id, token/cost
telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``LencioniDiagnostic`` remains exported as an
alias for ``LencioniAnalyzer``. All legacy private helpers
(``_validate_trace``, ``_pass_1_pyramid_score``, ``_pass_2_interventions``,
``_build_pyramid_score``, ``_dominant_dysfunction``, ``_team_health``,
``_serialize_trace``, ``max_trace_chars`` attr) are preserved.
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
    FORENSIC_CASCADE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PSYCH_SAFETY_PROMPT,
    INTERVENTIONS_PROMPT,
    LENCIONI_SYSTEM_PROMPT,
    PYRAMID_SCORE_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    assemble_prompt,
)
from .schema import (
    DYSFUNCTIONS,
    AttachedPlaybook,
    CascadeAudit,
    ComposedPatternHandoff,
    DysfunctionEvidence,
    Intervention,
    LencioniDiagnosis,
    LencioniMode,
    LencioniProfilePattern,
    MultiAgentTrace,
    PsychSafetyAudit,
    severity_from_score,
)

log = get_logger("agentcity.lencioni.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class LencioniAnalyzer:
    """Run the Lencioni Five Dysfunctions diagnostic on a MultiAgentTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: LencioniMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: LencioniMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: MultiAgentTrace,
        *,
        mode: LencioniMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> LencioniDiagnosis:
        active_mode: LencioniMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="lencioni"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[MultiAgentTrace],
        *,
        mode: LencioniMode | None = None,
    ) -> Iterator[LencioniDiagnosis]:
        active_mode: LencioniMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="lencioni"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: MultiAgentTrace,
        mode: LencioniMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> LencioniDiagnosis:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running Lencioni diagnostic (mode=%s) for team %s "
            "(agents=%d, messages=%d, success=%s)",
            mode,
            trace.team_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
            trace.success,
        )

        acc = _PipelineAcc()
        cascade_audit: CascadeAudit | None = None
        psych_safety_audit: PsychSafetyAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, trace_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_pyramid_score(trace, trace_text, acc=acc)
            pyramid_score = self._build_pyramid_score(evidence)
            dominant = self._dominant_dysfunction(pyramid_score)
            interventions = self._pass_2_interventions(
                trace, trace_text, evidence, dominant, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_pyramid_score(trace, trace_text, acc=acc)
            pyramid_score = self._build_pyramid_score(evidence)
            dominant = self._dominant_dysfunction(pyramid_score)
            cascade_audit = self._pass_forensic_cascade(pyramid_score, acc)
            psych_safety_audit = self._pass_forensic_psych_safety(trace_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence, dominant, cascade_audit, psych_safety_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown LencioniMode: {mode!r}")

        pyramid_score = self._build_pyramid_score(evidence)
        dominant = self._dominant_dysfunction(pyramid_score)
        team_health = self._team_health(pyramid_score)
        profile_pattern = self._classify_profile_pattern(pyramid_score, dominant, team_health)
        severity = severity_from_score(max(pyramid_score.values(), default=0.0))

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
                provisional = LencioniDiagnosis(
                    team_id=trace.team_id,
                    dominant_dysfunction=dominant,
                    pyramid_score=pyramid_score,
                    dysfunctions=evidence,
                    interventions=interventions,
                    overall_team_health=team_health,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return LencioniDiagnosis(
            team_id=trace.team_id,
            dominant_dysfunction=dominant,
            pyramid_score=pyramid_score,
            dysfunctions=evidence,
            interventions=interventions,
            overall_team_health=team_health,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            cascade_audit=cascade_audit,
            psych_safety_audit=psych_safety_audit,
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

    def _validate_trace(self, trace: MultiAgentTrace) -> None:
        if not trace.goal or not trace.goal.strip():
            raise ValueError("MultiAgentTrace.goal cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentTrace.agents must contain at least 2 agents.")
        if not trace.messages:
            raise ValueError("MultiAgentTrace.messages cannot be empty.")

    def _scan_injection(self, trace: MultiAgentTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("goal", trace.goal),
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
                    "prompt-injection pattern in trace field",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_trace(self, trace: MultiAgentTrace) -> str:
        header = [
            f"Goal: {trace.goal}",
            f"Agents: {', '.join(trace.agents)}",
            f"Outcome: {trace.outcome}",
            "",
        ]
        msg_lines = [
            f"[{m.timestamp.isoformat()}] ({m.message_type}) "
            f"{m.from_agent} -> {m.to_agent or 'TEAM'}: {m.content}"
            for m in trace.messages
        ]
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Multi-agent trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )

    def _call(self, prompt: str, *, pass_name: str, mode: LencioniMode, acc: "_PipelineAcc") -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=LENCIONI_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "lencioni"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # Legacy v0.0.x: signature preserves optional `acc` kwarg for new pipeline
    # while still working when called with just (trace, trace_text).
    def _pass_1_pyramid_score(
        self,
        trace: MultiAgentTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[DysfunctionEvidence]:
        prompt = PYRAMID_SCORE_PROMPT.format(
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=LENCIONI_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="pyramid_score", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[DysfunctionEvidence] = []
        for entry in data:
            try:
                evidence.append(DysfunctionEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DysfunctionEvidence (%s)",
                    type(exc).__name__,
                )
        seen = {ev.dysfunction for ev in evidence}
        for d in DYSFUNCTIONS:
            if d not in seen:
                evidence.append(
                    DysfunctionEvidence(
                        dysfunction=d,  # type: ignore[arg-type]
                        severity="none",
                        score=0.0,
                        explanation="No evidence of this dysfunction observed in the trace.",
                        evidence_quotes=[],
                    )
                )
        order = {d: i for i, d in enumerate(DYSFUNCTIONS)}
        evidence.sort(key=lambda e: order.get(e.dysfunction, len(DYSFUNCTIONS)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: MultiAgentTrace,
        trace_text: str,
        evidence: list[DysfunctionEvidence],
        dominant: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[Intervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            evidence=evidence_text,
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=LENCIONI_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[Intervention] = []
        for entry in data:
            try:
                interventions.append(Intervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed Intervention (%s)", type(exc).__name__)
        return interventions

    def _build_pyramid_score(self, evidence: list[DysfunctionEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {d: 0.0 for d in DYSFUNCTIONS}
        for ev in evidence:
            scores[str(ev.dysfunction)] = max(scores.get(str(ev.dysfunction), 0.0), ev.score)
        return scores

    def _dominant_dysfunction(
        self, pyramid_score: dict[str, float]
    ) -> Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
        "none-observed",
    ]:
        max_score = max(pyramid_score.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        for d in DYSFUNCTIONS:
            if pyramid_score.get(d, 0.0) >= max_score - 0.05:
                return d  # type: ignore[return-value]
        return "none-observed"

    def _team_health(
        self, pyramid_score: dict[str, float]
    ) -> Literal["healthy", "stressed", "dysfunctional"]:
        max_score = max(pyramid_score.values(), default=0.0)
        if max_score > 0.6:
            return "dysfunctional"
        if max_score > 0.3:
            return "stressed"
        return "healthy"

    # --- New v0.2.0 mode passes ---------------------------------------

    def _pass_quick(
        self, trace: MultiAgentTrace, trace_text: str, acc: "_PipelineAcc"
    ) -> tuple[list[DysfunctionEvidence], Intervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=trace.agents,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence_raw = obj.get("dysfunctions", [])
        evidence: list[DysfunctionEvidence] = []
        if isinstance(evidence_raw, list):
            for entry in evidence_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(DysfunctionEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed DysfunctionEvidence (%s)",
                        type(exc).__name__,
                    )
        # Fill missing.
        seen = {ev.dysfunction for ev in evidence}
        for d in DYSFUNCTIONS:
            if d not in seen:
                evidence.append(
                    DysfunctionEvidence(
                        dysfunction=d,  # type: ignore[arg-type]
                        severity="none",
                        score=0.0,
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {d: i for i, d in enumerate(DYSFUNCTIONS)}
        evidence.sort(key=lambda e: order.get(e.dysfunction, len(DYSFUNCTIONS)))
        top_iv: Intervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = Intervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_cascade(
        self, pyramid_score: dict[str, float], acc: "_PipelineAcc"
    ) -> CascadeAudit | None:
        prompt = assemble_prompt(
            FORENSIC_CASCADE_PROMPT,
            pyramid_score=pyramid_score,
        )
        raw = self._call(prompt, pass_name="forensic_cascade", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CascadeAudit(**obj)
        except Exception as exc:
            log.warning("CascadeAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_psych_safety(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> PsychSafetyAudit | None:
        prompt = assemble_prompt(
            FORENSIC_PSYCH_SAFETY_PROMPT,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="forensic_psych_safety", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return PsychSafetyAudit(**obj)
        except Exception as exc:
            log.warning("PsychSafetyAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[DysfunctionEvidence],
        dominant: str,
        cascade_audit: CascadeAudit | None,
        psych_safety_audit: PsychSafetyAudit | None,
        acc: "_PipelineAcc",
    ) -> list[Intervention]:
        if dominant == "none-observed":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=dominant,
            evidence=[e.model_dump() for e in evidence],
            cascade_audit=cascade_audit.model_dump() if cascade_audit else None,
            psych_safety_audit=psych_safety_audit.model_dump() if psych_safety_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[Intervention] = []
        for entry in data:
            try:
                interventions.append(Intervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed Intervention (%s)", type(exc).__name__)
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        pyramid_score: dict[str, float],
        dominant: str,
        team_health: str,
    ) -> LencioniProfilePattern:
        if team_health == "healthy":
            return "healthy_team"

        all_high = sum(1 for s in pyramid_score.values() if s >= 0.5)
        if all_high == 5:
            return "full_pyramid_dysfunction"

        bottom_two = (
            sum(pyramid_score.get(d, 0.0) for d in ("absence-of-trust", "fear-of-conflict")) / 2.0
        )
        top_three = (
            sum(
                pyramid_score.get(d, 0.0)
                for d in (
                    "lack-of-commitment",
                    "avoidance-of-accountability",
                    "inattention-to-results",
                )
            )
            / 3.0
        )
        if bottom_two >= 0.5 and top_three < 0.3:
            return "foundation_unstable_top_strong"

        mapping: dict[str, LencioniProfilePattern] = {
            "absence-of-trust": "foundational_trust_collapse",
            "fear-of-conflict": "conflict_avoidance",
            "lack-of-commitment": "commitment_collapse",
            "avoidance-of-accountability": "accountability_void",
            "inattention-to-results": "results_inattention",
        }
        if dominant in mapping:
            return mapping[dominant]
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: MultiAgentTrace,
        dominant: str,
        profile_pattern: LencioniProfilePattern,
        interventions: list[Intervention],
    ) -> ComposedPatternHandoff:
        provisional = LencioniDiagnosis(
            team_id=trace.team_id,
            dominant_dysfunction=cast(Any, dominant),
            pyramid_score={},
            dysfunctions=[],
            interventions=interventions,
            overall_team_health="stressed",
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_dysfunction": dominant,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[Intervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_dysfunction)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.dysfunction, pb.failure_mode) not in attached:
                attached[(pb.dysfunction, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
LencioniDiagnostic = LencioniAnalyzer


class LencioniAnalyzerAsync:
    """Async mirror of :class:`LencioniAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: LencioniMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: LencioniMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: MultiAgentTrace,
        *,
        mode: LencioniMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> LencioniDiagnosis:
        active_mode: LencioniMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = LencioniAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.lencioni.generator")
_legacy_log.addHandler(logging.NullHandler())
