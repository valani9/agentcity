"""DebatePathologyAnalyzer: multi-mode groupthink/polarization/contagion diagnostic.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``DebatePathologyDetector`` aliased
to ``DebatePathologyAnalyzer``.
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
    DEBATE_SYSTEM_PROMPT,
    FORENSIC_CONVERGENCE_TIMELINE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_TONE_CASCADE_PROMPT,
    INTERVENTIONS_PROMPT,
    PATHOLOGY_SCORING_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    assemble_prompt,
)
from .schema import (
    PATHOLOGIES,
    AttachedPlaybook,
    ComposedPatternHandoff,
    ConvergenceTimelineAudit,
    DebateIntervention,
    DebatePathologyDetection,
    DebatePathologyMode,
    DebatePathologyProfilePattern,
    MultiAgentDebateTrace,
    PathologyEvidence,
    ToneCascadeAudit,
    severity_from_pathology,
)

log = get_logger("vstack.debate_pathology.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class DebatePathologyAnalyzer:
    """Run the groupthink/polarization/contagion diagnostic on a debate trace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DebatePathologyMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DebatePathologyMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: MultiAgentDebateTrace,
        *,
        mode: DebatePathologyMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> DebatePathologyDetection:
        active_mode: DebatePathologyMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="debate_pathology"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[MultiAgentDebateTrace],
        *,
        mode: DebatePathologyMode | None = None,
    ) -> Iterator[DebatePathologyDetection]:
        active_mode: DebatePathologyMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="debate_pathology"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: MultiAgentDebateTrace,
        mode: DebatePathologyMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> DebatePathologyDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        debate_text = self._serialize_debate(trace)
        started = time.monotonic()
        log.info(
            "Running debate-pathology diagnostic (mode=%s) for debate %s",
            mode,
            trace.debate_id or "<unknown>",
        )

        acc = _PipelineAcc()
        convergence_audit: ConvergenceTimelineAudit | None = None
        tone_cascade_audit: ToneCascadeAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, debate_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_pathologies(trace, debate_text, acc=acc)
            scores = self._build_scores(evidence)
            dominant = self._dominant_pathology(scores)
            quality = self._debate_quality(scores)
            interventions = self._pass_2_interventions(
                trace, debate_text, evidence, dominant, quality, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_pathologies(trace, debate_text, acc=acc)
            scores = self._build_scores(evidence)
            dominant = self._dominant_pathology(scores)
            quality = self._debate_quality(scores)
            convergence_audit = self._pass_forensic_convergence(debate_text, acc)
            tone_cascade_audit = self._pass_forensic_tone_cascade(debate_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence,
                dominant,
                quality,
                convergence_audit,
                tone_cascade_audit,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown DebatePathologyMode: {mode!r}")

        scores = self._build_scores(evidence)
        dominant = self._dominant_pathology(scores)
        quality = self._debate_quality(scores)
        convergence_round = self._convergence_round(trace)
        profile_pattern = self._classify_profile_pattern(
            scores, dominant, quality, convergence_round
        )
        severity = severity_from_pathology(max(scores.values(), default=0.0))

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
                provisional = DebatePathologyDetection(
                    debate_id=trace.debate_id,
                    dominant_pathology=dominant,
                    pathology_scores=scores,
                    pathologies=evidence,
                    debate_quality=quality,
                    convergence_round=convergence_round,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return DebatePathologyDetection(
            debate_id=trace.debate_id,
            dominant_pathology=dominant,
            pathology_scores=scores,
            pathologies=evidence,
            debate_quality=quality,
            convergence_round=convergence_round,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            convergence_audit=convergence_audit,
            tone_cascade_audit=tone_cascade_audit,
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

    def _validate_trace(self, trace: MultiAgentDebateTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("MultiAgentDebateTrace.task cannot be empty.")
        if not trace.final_decision or not trace.final_decision.strip():
            raise ValueError("MultiAgentDebateTrace.final_decision cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentDebateTrace.agents must contain at least 2 agents.")
        if len(trace.messages) < 2:
            raise ValueError("MultiAgentDebateTrace.messages must contain at least 2 messages.")

    def _scan_injection(self, trace: MultiAgentDebateTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("final_decision", trace.final_decision),
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
                    "prompt-injection pattern in debate",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_debate(self, trace: MultiAgentDebateTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Agents: {', '.join(trace.agents)}",
            f"Final decision: {trace.final_decision}",
            f"Outcome: {trace.outcome}",
            "",
        ]
        msg_lines = []
        for m in trace.messages:
            msg_lines.append(
                f"[round {m.round}] ({m.emotional_tone}) {m.from_agent} "
                f"({m.position or 'no-stated-position'}): {m.content}"
            )
        text = "\n".join(header + msg_lines)
        if len(text) <= self.max_trace_chars:
            return text
        log.warning("Debate trace exceeds max_trace_chars; truncating")
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
        mode: DebatePathologyMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=DEBATE_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "debate_pathology"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_pathologies(
        self,
        trace: MultiAgentDebateTrace,
        debate_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[PathologyEvidence]:
        prompt = PATHOLOGY_SCORING_PROMPT.format(
            task=trace.task,
            agents=", ".join(trace.agents),
            final_decision=trace.final_decision,
            outcome=trace.outcome,
            success=trace.success,
            trace=debate_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=DEBATE_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="pathologies", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[PathologyEvidence] = []
        for entry in data:
            try:
                evidence.append(PathologyEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed PathologyEvidence (%s)", type(exc).__name__)
        seen = {ev.pathology for ev in evidence}
        for p in PATHOLOGIES:
            if p not in seen:
                evidence.append(
                    PathologyEvidence(
                        pathology=p,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {p: i for i, p in enumerate(PATHOLOGIES)}
        evidence.sort(key=lambda e: order.get(e.pathology, len(PATHOLOGIES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: MultiAgentDebateTrace,
        debate_text: str,
        evidence: list[PathologyEvidence],
        dominant: str,
        quality: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[DebateIntervention]:
        if dominant == "none-observed":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant=dominant,
            quality=quality,
            evidence=evidence_text,
            trace=debate_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=DEBATE_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[DebateIntervention] = []
        for entry in data:
            try:
                interventions.append(DebateIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DebateIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    def _build_scores(self, evidence: list[PathologyEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {p: 0.0 for p in PATHOLOGIES}
        for ev in evidence:
            scores[str(ev.pathology)] = max(scores.get(str(ev.pathology), 0.0), ev.score)
        return scores

    def _dominant_pathology(
        self, scores: dict[str, float]
    ) -> Literal["groupthink", "polarization", "contagion", "none-observed"]:
        max_score = max(scores.values(), default=0.0)
        if max_score < 0.2:
            return "none-observed"
        # Groupthink wins tie-breaks: cleanest intervention literature.
        for p in PATHOLOGIES:
            if scores.get(p, 0.0) >= max_score - 0.05:
                return p  # type: ignore[return-value]
        return "none-observed"

    def _debate_quality(
        self, scores: dict[str, float]
    ) -> Literal["healthy", "at-risk", "pathological"]:
        max_score = max(scores.values(), default=0.0)
        if max_score > 0.6:
            return "pathological"
        if max_score > 0.3:
            return "at-risk"
        return "healthy"

    def _convergence_round(self, trace: MultiAgentDebateTrace) -> int | None:
        # Heuristic: first round where all stated positions match.
        positions_by_round: dict[int, dict[str, str]] = {}
        for m in trace.messages:
            if not m.position:
                continue
            positions_by_round.setdefault(m.round, {})[m.from_agent] = m.position
        for r in sorted(positions_by_round.keys()):
            stances = positions_by_round[r]
            if len(stances) >= max(2, len(trace.agents) - 1) and len(set(stances.values())) == 1:
                return r
        return None

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: MultiAgentDebateTrace,
        debate_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[PathologyEvidence], DebateIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            final_decision=trace.final_decision,
            trace=debate_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        path_raw = obj.get("pathologies", [])
        evidence: list[PathologyEvidence] = []
        if isinstance(path_raw, list):
            for entry in path_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(PathologyEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed PathologyEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {ev.pathology for ev in evidence}
        for p in PATHOLOGIES:
            if p not in seen:
                evidence.append(
                    PathologyEvidence(
                        pathology=p,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {p: i for i, p in enumerate(PATHOLOGIES)}
        evidence.sort(key=lambda e: order.get(e.pathology, len(PATHOLOGIES)))
        top_iv: DebateIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = DebateIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_convergence(
        self, debate_text: str, acc: "_PipelineAcc"
    ) -> ConvergenceTimelineAudit | None:
        prompt = assemble_prompt(FORENSIC_CONVERGENCE_TIMELINE_PROMPT, trace=debate_text)
        raw = self._call(prompt, pass_name="forensic_convergence", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ConvergenceTimelineAudit(**obj)
        except Exception as exc:
            log.warning("ConvergenceTimelineAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_tone_cascade(
        self, debate_text: str, acc: "_PipelineAcc"
    ) -> ToneCascadeAudit | None:
        prompt = assemble_prompt(FORENSIC_TONE_CASCADE_PROMPT, trace=debate_text)
        raw = self._call(prompt, pass_name="forensic_tone_cascade", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ToneCascadeAudit(**obj)
        except Exception as exc:
            log.warning("ToneCascadeAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[PathologyEvidence],
        dominant: str,
        quality: str,
        convergence_audit: ConvergenceTimelineAudit | None,
        tone_cascade_audit: ToneCascadeAudit | None,
        acc: "_PipelineAcc",
    ) -> list[DebateIntervention]:
        if dominant == "none-observed":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=dominant,
            quality=quality,
            evidence=[e.model_dump() for e in evidence],
            convergence_audit=convergence_audit.model_dump() if convergence_audit else None,
            tone_cascade_audit=tone_cascade_audit.model_dump() if tone_cascade_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[DebateIntervention] = []
        for entry in data:
            try:
                interventions.append(DebateIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DebateIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        scores: dict[str, float],
        dominant: str,
        quality: str,
        convergence_round: int | None,
    ) -> DebatePathologyProfilePattern:
        if quality == "healthy":
            return "healthy_debate"
        all_high = sum(1 for s in scores.values() if s >= 0.6)
        if all_high >= 2:
            return "multi_pathology_severe"
        if convergence_round is not None and convergence_round <= 2:
            return "premature_convergence"
        if scores.get("groupthink", 0.0) >= 0.6:
            return "groupthink_collapse"
        if scores.get("polarization", 0.0) >= 0.6:
            return "polarization_runaway"
        if scores.get("contagion", 0.0) >= 0.6:
            if scores.get("contagion", 0.0) > scores.get("groupthink", 0.0):
                return "tone_overrides_content"
            return "contagion_dominated"
        if dominant == "groupthink":
            return "dissent_suppressed"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: MultiAgentDebateTrace,
        profile_pattern: DebatePathologyProfilePattern,
        dominant: str,
        interventions: list[DebateIntervention],
    ) -> ComposedPatternHandoff:
        provisional = DebatePathologyDetection(
            debate_id=trace.debate_id,
            dominant_pathology=cast(Any, dominant),
            pathology_scores={},
            pathologies=[],
            debate_quality="at-risk",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_pathology": dominant,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[DebateIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_pathology)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.pathology, pb.failure_mode) not in attached:
                attached[(pb.pathology, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
DebatePathologyDetector = DebatePathologyAnalyzer


class DebatePathologyAnalyzerAsync:
    """Async mirror of :class:`DebatePathologyAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DebatePathologyMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DebatePathologyMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: MultiAgentDebateTrace,
        *,
        mode: DebatePathologyMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> DebatePathologyDetection:
        active_mode: DebatePathologyMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = DebatePathologyAnalyzer(
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


_legacy_log = logging.getLogger("vstack.debate_pathology.generator")
_legacy_log.addHandler(logging.NullHandler())
