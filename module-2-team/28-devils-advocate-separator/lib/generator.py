"""RoleSeparationAnalyzer: multi-mode Devil's Advocate role separator.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``RoleSeparationDetector`` aliased
to ``RoleSeparationAnalyzer``.
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
    FORENSIC_APPROVAL_RATE_PROMPT,
    FORENSIC_CRITIC_VOICE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    ROLE_ANALYSIS_PROMPT,
    SEPARATOR_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    PHASES,
    ApprovalRateAudit,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CriticVoiceAudit,
    DevilsAdvocateMode,
    DevilsAdvocateProfilePattern,
    PhaseEvidence,
    RoleSeparationDetection,
    RoleSeparationIntervention,
    SingleAgentTrace,
    severity_from_separation,
)

log = get_logger("vstack.devils_advocate.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class RoleSeparationAnalyzer:
    """Run the Devil's Advocate role-separator diagnostic on a single-agent trace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DevilsAdvocateMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DevilsAdvocateMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: SingleAgentTrace,
        *,
        mode: DevilsAdvocateMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> RoleSeparationDetection:
        active_mode: DevilsAdvocateMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="devils_advocate"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[SingleAgentTrace],
        *,
        mode: DevilsAdvocateMode | None = None,
    ) -> Iterator[RoleSeparationDetection]:
        active_mode: DevilsAdvocateMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="devils_advocate"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: SingleAgentTrace,
        mode: DevilsAdvocateMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> RoleSeparationDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running devil's advocate diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        approval_rate_audit: ApprovalRateAudit | None = None
        critic_voice_audit: CriticVoiceAudit | None = None

        if mode == "quick":
            evidence, top_iv = self._pass_quick(trace, trace_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence = self._pass_1_phases(trace, trace_text, acc=acc)
            quality_str, locus_str, sep_score = self._compute_separation_metrics(evidence)
            interventions = self._pass_2_interventions(
                trace, trace_text, evidence, quality_str, acc=acc
            )
        elif mode == "forensic":
            evidence = self._pass_1_phases(trace, trace_text, acc=acc)
            quality_str, locus_str, sep_score = self._compute_separation_metrics(evidence)
            approval_rate_audit = self._pass_forensic_approval_rate(trace_text, acc)
            critic_voice_audit = self._pass_forensic_critic_voice(trace_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence,
                quality_str,
                approval_rate_audit,
                critic_voice_audit,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown DevilsAdvocateMode: {mode!r}")

        quality_str, locus_str, sep_score = self._compute_separation_metrics(evidence)
        quality_lit: Literal["well-separated", "partially-conflated", "fully-conflated"] = (
            quality_str  # type: ignore[assignment]
        )
        locus_lit: Literal["self-reviewed", "externally-reviewed", "mixed", "unreviewed"] = (
            locus_str  # type: ignore[assignment]
        )
        self_approval_rate = (
            approval_rate_audit.self_approval_rate
            if approval_rate_audit
            else self._heuristic_self_approval(trace)
        )
        severity = severity_from_separation(sep_score)
        profile_pattern = self._classify_profile_pattern(evidence, quality_str, self_approval_rate)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = RoleSeparationDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    role_separation_quality=quality_lit,
                    role_separation_score=sep_score,
                    locus_of_judgment=locus_lit,
                    phase_evidence=evidence,
                    self_approval_rate=self_approval_rate,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return RoleSeparationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            role_separation_quality=quality_lit,
            role_separation_score=sep_score,
            locus_of_judgment=locus_lit,
            phase_evidence=evidence,
            self_approval_rate=self_approval_rate,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            approval_rate_audit=approval_rate_audit,
            critic_voice_audit=critic_voice_audit,
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

    def _validate_trace(self, trace: SingleAgentTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("SingleAgentTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("SingleAgentTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("SingleAgentTrace.steps cannot be empty.")

    def _scan_injection(self, trace: SingleAgentTrace) -> bool:
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
                    "prompt-injection pattern in trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _serialize_trace(self, trace: SingleAgentTrace) -> str:
        lines = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        for i, s in enumerate(trace.steps):
            conf = f" conf={s.confidence:.2f}" if s.confidence is not None else ""
            lines.append(f"[step {i + 1}] ({s.type}) actor={s.actor}{conf}: {s.content}")
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
        mode: DevilsAdvocateMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SEPARATOR_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "devils_advocate"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_phases(
        self,
        trace: SingleAgentTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[PhaseEvidence]:
        prompt = ROLE_ANALYSIS_PROMPT.format(
            task=trace.task,
            outcome=trace.outcome,
            success=trace.success,
            model_name=trace.model_name or "unspecified",
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=SEPARATOR_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="phases", mode="standard", acc=acc)
        data = extract_json_array(raw)
        evidence: list[PhaseEvidence] = []
        for entry in data:
            try:
                evidence.append(PhaseEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed PhaseEvidence (%s)", type(exc).__name__)
        seen = {ev.phase for ev in evidence}
        for ph in PHASES:
            if ph not in seen:
                evidence.append(
                    PhaseEvidence(
                        phase=ph,  # type: ignore[arg-type]
                        present=False,
                        actor="primary",
                        substantive_score=0.0,
                        explanation="Phase not observed in the trace.",
                        evidence_quotes=[],
                    )
                )
        order = {ph: i for i, ph in enumerate(PHASES)}
        evidence.sort(key=lambda e: order.get(e.phase, len(PHASES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: SingleAgentTrace,
        trace_text: str,
        evidence: list[PhaseEvidence],
        quality: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[RoleSeparationIntervention]:
        if quality == "well-separated":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            quality=quality, evidence=evidence_text, trace=trace_text
        )
        if acc is None:
            raw = self._complete(prompt, system=SEPARATOR_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[RoleSeparationIntervention] = []
        for entry in data:
            try:
                interventions.append(RoleSeparationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RoleSeparationIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    def _compute_separation_metrics(self, evidence: list[PhaseEvidence]) -> tuple[str, str, float]:
        by = {ev.phase: ev for ev in evidence}
        plan = by.get("plan")
        execute = by.get("execute")
        self_eval = by.get("self_evaluate")
        ext = by.get("external_critique")

        actor_plan = plan.actor if plan and plan.present else None
        actor_exec = execute.actor if execute and execute.present else None
        actor_ext = ext.actor if ext and ext.present else None

        ext_present = ext is not None and ext.present
        eval_present = self_eval is not None and self_eval.present

        # Locus of judgment.
        if ext_present and eval_present:
            locus = "mixed"
        elif ext_present:
            locus = "externally-reviewed"
        elif eval_present:
            locus = "self-reviewed"
        else:
            locus = "unreviewed"

        # Separation score: weighted by whether critique was external + substantive.
        score = 0.0
        if ext_present and actor_ext and actor_ext not in (actor_plan, actor_exec, "primary"):
            score += 0.6 * (ext.substantive_score if ext else 0.0)
        if eval_present and self_eval:
            # Self-eval contributes less; only if substantive.
            score += 0.25 * self_eval.substantive_score
        if plan and plan.present:
            score += 0.15
        if execute and execute.present:
            score += 0.10
        score = round(min(1.0, score), 2)

        if score >= 0.6:
            quality = "well-separated"
        elif score >= 0.35:
            quality = "partially-conflated"
        else:
            quality = "fully-conflated"
        return quality, locus, score

    def _heuristic_self_approval(self, trace: SingleAgentTrace) -> float:
        # A self_evaluate step counts as a revision if its content contains
        # revision-language ("revise", "wrong", "redo", "fix", "incorrect")
        # or if the immediately-following step is a fresh plan/execute.
        # Otherwise it counts as an approval.
        approvals = 0
        revisions = 0
        evals_seen = 0
        revision_keywords = ("revise", "wrong", "redo", "fix", "incorrect")
        for i, step in enumerate(trace.steps):
            if step.type != "self_evaluate":
                continue
            evals_seen += 1
            content_lower = step.content.lower()
            looks_like_revision = any(k in content_lower for k in revision_keywords)
            next_is_redo = i + 1 < len(trace.steps) and trace.steps[i + 1].type in (
                "plan",
                "execute",
            )
            if looks_like_revision or next_is_redo:
                revisions += 1
            else:
                approvals += 1
        if evals_seen == 0:
            return 0.0
        return round(approvals / evals_seen, 2)

    # v0.0.x legacy alias.
    def _self_approval_rate(self, trace: SingleAgentTrace) -> float:
        return self._heuristic_self_approval(trace)

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: SingleAgentTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[PhaseEvidence], RoleSeparationIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            outcome=trace.outcome,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        ph_raw = obj.get("phase_evidence", [])
        evidence: list[PhaseEvidence] = []
        if isinstance(ph_raw, list):
            for entry in ph_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(PhaseEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed PhaseEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {ev.phase for ev in evidence}
        for ph in PHASES:
            if ph not in seen:
                evidence.append(
                    PhaseEvidence(
                        phase=ph,  # type: ignore[arg-type]
                        present=False,
                        actor="primary",
                        substantive_score=0.0,
                        explanation="Phase not observed.",
                        evidence_quotes=[],
                    )
                )
        order = {ph: i for i, ph in enumerate(PHASES)}
        evidence.sort(key=lambda e: order.get(e.phase, len(PHASES)))
        top_iv: RoleSeparationIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = RoleSeparationIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, top_iv

    def _pass_forensic_approval_rate(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> ApprovalRateAudit | None:
        prompt = assemble_prompt(FORENSIC_APPROVAL_RATE_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_approval_rate", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ApprovalRateAudit(**obj)
        except Exception as exc:
            log.warning("ApprovalRateAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_critic_voice(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> CriticVoiceAudit | None:
        prompt = assemble_prompt(FORENSIC_CRITIC_VOICE_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_critic_voice", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CriticVoiceAudit(**obj)
        except Exception as exc:
            log.warning("CriticVoiceAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        evidence: list[PhaseEvidence],
        quality: str,
        approval_rate_audit: ApprovalRateAudit | None,
        critic_voice_audit: CriticVoiceAudit | None,
        acc: "_PipelineAcc",
    ) -> list[RoleSeparationIntervention]:
        if quality == "well-separated":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            quality=quality,
            evidence=[e.model_dump() for e in evidence],
            approval_rate_audit=approval_rate_audit.model_dump() if approval_rate_audit else None,
            critic_voice_audit=critic_voice_audit.model_dump() if critic_voice_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[RoleSeparationIntervention] = []
        for entry in data:
            try:
                interventions.append(RoleSeparationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RoleSeparationIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        evidence: list[PhaseEvidence],
        quality: str,
        self_approval_rate: float,
    ) -> DevilsAdvocateProfilePattern:
        by = {ev.phase: ev for ev in evidence}
        plan = by.get("plan")
        ext = by.get("external_critique")
        eval_ = by.get("self_evaluate")
        ext_present = ext is not None and ext.present
        ext_weak = ext_present and (ext.substantive_score < 0.4 if ext else False)
        eval_present = eval_ is not None and eval_.present

        if quality == "well-separated":
            return "well_separated_critique"
        if not ext_present and not eval_present:
            return "fully_conflated_roles"
        if not ext_present and eval_present:
            return "self_review_only"
        if self_approval_rate >= 0.8 and eval_present:
            return "rubber_stamping"
        if not ext_present:
            return "missing_critic_phase"
        if ext_weak:
            return "external_critic_present_weak"
        if plan and plan.present and plan.substantive_score < 0.4:
            # Plan is weak; check sub-pattern.
            return "no_alternative_hypothesis"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: SingleAgentTrace,
        profile_pattern: DevilsAdvocateProfilePattern,
        interventions: list[RoleSeparationIntervention],
    ) -> ComposedPatternHandoff:
        provisional = RoleSeparationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            role_separation_quality="partially-conflated",
            role_separation_score=0.5,
            locus_of_judgment="mixed",
            phase_evidence=[],
            self_approval_rate=0.5,
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
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

    def _attach_playbooks(
        self, interventions: list[RoleSeparationIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_phase)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.phase, pb.failure_mode) not in attached:
                attached[(pb.phase, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
RoleSeparationDetector = RoleSeparationAnalyzer


class RoleSeparationAnalyzerAsync:
    """Async mirror of :class:`RoleSeparationAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DevilsAdvocateMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DevilsAdvocateMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: SingleAgentTrace,
        *,
        mode: DevilsAdvocateMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> RoleSeparationDetection:
        active_mode: DevilsAdvocateMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = RoleSeparationAnalyzer(
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


_legacy_log = logging.getLogger("vstack.devils_advocate.generator")
_legacy_log.addHandler(logging.NullHandler())
