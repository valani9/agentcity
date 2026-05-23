"""EIAuditDetector: diagnose Goleman's 4 EI domains for an AI agent
and identify the weakest domain with sub-competency decomposition.

The detector exposes three pipeline modes:

  - ``quick`` -- one combined LLM call (scoring + top intervention).
    For CI / live ops. ~2s, ~$0.005.
  - ``standard`` -- two LLM calls (domains + interventions).
    For human-driven postmortems. ~5s, ~$0.015.
  - ``forensic`` -- four LLM calls (forensic-domains with competency
    decomposition + Mayer-Salovey overlay + cascade reconcile +
    ranked interventions with composition targets).
    For deep dives. ~15s, ~$0.05.

Each mode wires the v0.1.0 production infrastructure: structured
logging with run-id correlation, token / cost telemetry, input
sanitization + fencing, and an async mirror via composition.

Deterministic synthesis (axis decomposition, profile-pattern
classification, dominant-domain selection, baseline comparison,
composition handoff, playbook attachment) lives in pure Python.
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
    CASCADE_RECONCILE_PROMPT,
    FORENSIC_DOMAINS_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    GOLEMAN_SYSTEM_PROMPT,
    MAYER_SALOVEY_OVERLAY_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_DOMAINS_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    EI_DOMAINS,
    AgentEITrace,
    AttachedPlaybook,
    CascadeAnalysis,
    ComposedPatternHandoff,
    DomainScore,
    EIAxisScores,
    EIDetection,
    EIIntervention,
    EIMode,
    EIProfilePattern,
    MayerSaloveyBranch,
    UserSignal,
    severity_from_score,
)

log = get_logger("agentcity.goleman_ei.generator")


_DEFAULT_COST_PER_1K = {
    "input": 0.003,
    "output": 0.015,
}


class LLMClient(Protocol):
    """Single-method synchronous LLM client contract."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    """Single-method asynchronous LLM client contract."""

    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class EIAuditDetector:
    """Run the 4-Domain EI Audit on an :class:`AgentEITrace`.

    Mode-aware. ``mode`` parameter at construction sets the default;
    individual calls can override via ``.run(trace, mode="...")``.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: EIMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: EIMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(
        self,
        trace: AgentEITrace,
        *,
        mode: EIMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> EIDetection:
        active_mode: EIMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="goleman_ei"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentEITrace],
        *,
        mode: EIMode | None = None,
    ) -> Iterator[EIDetection]:
        active_mode: EIMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="goleman_ei"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    # ------------------------------------------------------------------
    # Pipeline dispatch
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        trace: AgentEITrace,
        mode: EIMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> EIDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        normalized_signals = self._normalize_user_signals(trace.user_signals)

        started = time.monotonic()
        log.info(
            "Running EI Audit (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()

        llm_meta: dict[str, Any] = {}
        if mode == "quick":
            domains, top_intervention, llm_meta = self._pass_quick(trace, normalized_signals, acc)
            interventions = [top_intervention] if top_intervention else []
            mayer_overlay: list[MayerSaloveyBranch] = []
            cascade: CascadeAnalysis | None = None
        elif mode == "standard":
            domains, llm_meta = self._pass_standard_domains(trace, normalized_signals, acc)
            interventions = self._pass_standard_interventions(
                trace, normalized_signals, domains, llm_meta, acc
            )
            mayer_overlay = []
            cascade = None
        elif mode == "forensic":
            domains, llm_meta = self._pass_forensic_domains(trace, normalized_signals, acc)
            mayer_overlay = self._pass_mayer_overlay(trace, normalized_signals, acc)
            cascade = self._pass_cascade_reconcile(domains, mayer_overlay, acc)
            interventions = self._pass_forensic_interventions(
                trace, normalized_signals, domains, cascade, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown EIMode: {mode!r}")

        # Deterministic synthesis. The LLM's claimed ei_quality and
        # weakest_domain are preserved when valid (backward compat).
        axis_scores = self._compute_axis_scores(domains)
        profile_pattern = self._classify_profile_pattern(domains, axis_scores)
        overall_ei_computed = sum(d.score for d in domains) / max(len(domains), 1)
        llm_overall = llm_meta.get("overall_ei")
        if isinstance(llm_overall, (int, float)):
            overall_ei = float(llm_overall)
        else:
            overall_ei = overall_ei_computed
        weakest_domain = self._pick_weakest_domain(
            domains, llm_label=llm_meta.get("weakest_domain", "")
        )
        ei_quality = self._ei_quality(overall_ei, llm_label=llm_meta.get("ei_quality", "") or "")

        composition = (
            self._build_composition_handoff(
                trace, domains, weakest_domain, profile_pattern, interventions
            )
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        if baseline_path:
            try:
                bl = load_baseline(baseline_path)
                provisional = EIDetection(
                    domains=domains,
                    overall_ei=overall_ei,
                    ei_quality=ei_quality,
                    weakest_domain=weakest_domain,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed (%s): %r", type(exc).__name__, exc)
        elif trace.baseline_detection_path:
            try:
                bl = load_baseline(trace.baseline_detection_path)
                provisional = EIDetection(
                    domains=domains,
                    overall_ei=overall_ei,
                    ei_quality=ei_quality,
                    weakest_domain=weakest_domain,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception:
                pass

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = EIDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            interaction_class=trace.interaction_class,
            domains=domains,
            overall_ei=round(overall_ei, 4),
            ei_quality=ei_quality,
            weakest_domain=weakest_domain,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            profile_pattern=profile_pattern,
            axis_scores=axis_scores,
            cascade_analysis=cascade,
            mayer_salovey_overlay=mayer_overlay,
            emotional_covariation=trace.emotional_covariation,
            baseline=baseline,
            composition_handoff=composition,
            attached_playbooks=playbooks,
            cost_usd=acc.cost_usd,
            tokens_total=acc.tokens_total,
            tokens_input=acc.tokens_input,
            tokens_output=acc.tokens_output,
            llm_calls=acc.llm_calls,
            elapsed_ms=elapsed_ms,
            run_id=run_id,
            injection_detected=injection_detected,
        )

        log.info(
            "EI Audit done mode=%s weakest=%s quality=%s profile=%s elapsed=%.0fms tokens=%d cost=$%.4f",
            mode,
            weakest_domain,
            ei_quality,
            profile_pattern,
            elapsed_ms,
            acc.tokens_total,
            acc.cost_usd,
        )
        return detection

    # ------------------------------------------------------------------
    # Validation + sanitization scan
    # ------------------------------------------------------------------

    def _validate_trace(self, trace: AgentEITrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentEITrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentEITrace.outcome cannot be empty.")
        if not (trace.observed_behaviors or trace.user_signals or trace.self_reports):
            raise ValueError(
                "AgentEITrace must have at least one of observed_behaviors, "
                "user_signals, or self_reports."
            )

    def _scan_injection(self, trace: AgentEITrace) -> bool:
        """Run :func:`detect_injection` on every free-text field; log hits."""
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("system_prompt", trace.system_prompt),
        ]
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
        for i, s in enumerate(trace.user_signals):
            text = s.text if isinstance(s, UserSignal) else s
            targets.append((f"user_signals[{i}]", text))
        for i, r in enumerate(trace.self_reports):
            targets.append((f"self_reports[{i}]", r))

        hit_count = 0
        for field, value in targets:
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern detected in trace field",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        if hit_count:
            log.warning("injection scan: %d field(s) flagged", hit_count)
        return hit_count > 0

    def _normalize_user_signals(self, signals: list[UserSignal | str]) -> list[dict[str, Any]]:
        """Convert legacy string signals to UserSignal-shaped dicts."""
        out: list[dict[str, Any]] = []
        for i, s in enumerate(signals):
            if isinstance(s, UserSignal):
                d = s.model_dump()
                if d.get("signal_id") is None:
                    d["signal_id"] = f"sig-{i + 1}"
                out.append(d)
            else:
                out.append(
                    {
                        "signal_id": f"sig-{i + 1}",
                        "text": str(s),
                        "inferred_emotion": "unknown",
                        "inferred_intensity": 0.5,
                    }
                )
        return out

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: EIMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=GOLEMAN_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "goleman_ei"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # ------------------------------------------------------------------
    # Mode: QUICK
    # ------------------------------------------------------------------

    def _pass_quick(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        acc: "_PipelineAcc",
    ) -> tuple[list[DomainScore], EIIntervention | None, dict[str, Any]]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            interaction_class=trace.interaction_class,
            framework=trace.framework or "unspecified",
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt,
            outcome=trace.outcome,
            success=trace.success,
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
            self_reports=trace.self_reports,
        )
        raw = self._call(prompt, pass_name="quick_combined", mode="quick", acc=acc)
        domains = self._parse_domains(raw)
        meta = self._parse_meta(raw)
        top_intervention: EIIntervention | None = None
        try:
            obj = _try_json_object(raw)
            iv_entry = obj.get("top_intervention") if obj else None
            if iv_entry:
                top_intervention = EIIntervention(**iv_entry)
        except Exception as exc:
            log.warning(
                "Quick-mode: failed to parse top_intervention (%s)",
                type(exc).__name__,
            )
        return domains, top_intervention, meta

    # ------------------------------------------------------------------
    # Mode: STANDARD
    # ------------------------------------------------------------------

    def _pass_standard_domains(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        acc: "_PipelineAcc",
    ) -> tuple[list[DomainScore], dict[str, Any]]:
        prompt = assemble_prompt(
            STANDARD_DOMAINS_PROMPT,
            task=trace.task,
            interaction_class=trace.interaction_class,
            framework=trace.framework or "unspecified",
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt,
            outcome=trace.outcome,
            success=trace.success,
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
            self_reports=trace.self_reports,
        )
        raw = self._call(prompt, pass_name="standard_domains", mode="standard", acc=acc)
        return self._parse_domains(raw), self._parse_meta(raw)

    def _pass_standard_interventions(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        domains: list[DomainScore],
        llm_meta: dict[str, Any],
        acc: "_PipelineAcc",
    ) -> list[EIIntervention]:
        weakest = self._pick_weakest_domain(domains, llm_label=llm_meta.get("weakest_domain", ""))
        overall = sum(d.score for d in domains) / max(len(domains), 1)
        llm_overall = llm_meta.get("overall_ei")
        if isinstance(llm_overall, (int, float)):
            overall = float(llm_overall)
        quality = self._ei_quality(overall, llm_label=llm_meta.get("ei_quality", "") or "")
        if quality == "high-ei":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            weakest_domain=weakest,
            ei_quality=quality,
            domains=[d.model_dump() for d in domains],
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Mode: FORENSIC
    # ------------------------------------------------------------------

    def _pass_forensic_domains(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        acc: "_PipelineAcc",
    ) -> tuple[list[DomainScore], dict[str, Any]]:
        prompt = assemble_prompt(
            FORENSIC_DOMAINS_PROMPT,
            task=trace.task,
            interaction_class=trace.interaction_class,
            framework=trace.framework or "unspecified",
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt,
            outcome=trace.outcome,
            success=trace.success,
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
            self_reports=trace.self_reports,
        )
        raw = self._call(prompt, pass_name="forensic_domains", mode="forensic", acc=acc)
        return self._parse_domains(raw), self._parse_meta(raw)

    def _pass_mayer_overlay(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        acc: "_PipelineAcc",
    ) -> list[MayerSaloveyBranch]:
        prompt = assemble_prompt(
            MAYER_SALOVEY_OVERLAY_PROMPT,
            task=trace.task,
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
            self_reports=trace.self_reports,
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="forensic_mayer", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        branches: list[MayerSaloveyBranch] = []
        for entry in data:
            try:
                branches.append(MayerSaloveyBranch(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed MayerSaloveyBranch (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return branches

    def _pass_cascade_reconcile(
        self,
        domains: list[DomainScore],
        mayer_overlay: list[MayerSaloveyBranch],
        acc: "_PipelineAcc",
    ) -> CascadeAnalysis | None:
        prompt = assemble_prompt(
            CASCADE_RECONCILE_PROMPT,
            domain_scores=[d.model_dump() for d in domains],
            mayer_scores=[m.model_dump() for m in mayer_overlay],
        )
        raw = self._call(prompt, pass_name="forensic_cascade", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CascadeAnalysis(**obj)
        except Exception as exc:
            log.warning("Cascade reconcile parse error (%s)", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentEITrace,
        normalized_signals: list[dict[str, Any]],
        domains: list[DomainScore],
        cascade: CascadeAnalysis | None,
        acc: "_PipelineAcc",
    ) -> list[EIIntervention]:
        weakest = self._pick_weakest_domain(domains)
        overall = sum(d.score for d in domains) / max(len(domains), 1)
        quality = self._ei_quality(overall)
        if quality == "high-ei":
            return []
        axis = self._compute_axis_scores(domains)
        profile = self._classify_profile_pattern(domains, axis)
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            weakest_domain=weakest,
            profile_pattern=profile,
            cascade_break_point=cascade.cascade_break_point if cascade else "intact",
            domains=[d.model_dump() for d in domains],
            observed_behaviors=trace.observed_behaviors,
            user_signals=normalized_signals,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_domains(self, raw: str) -> list[DomainScore]:
        data = extract_json_array(raw)
        # Unwrap a single-item list whose only element is a dict with a
        # "domains" key (legacy v0.0.x response shape, or quick-mode wrapper).
        if len(data) == 1 and isinstance(data[0].get("domains"), list):
            data = [x for x in data[0]["domains"] if isinstance(x, dict)]
        if not data:
            obj = _try_json_object(raw)
            if obj and isinstance(obj.get("domains"), list):
                data = [x for x in obj["domains"] if isinstance(x, dict)]

        scores: list[DomainScore] = []
        for entry in data:
            try:
                if entry.get("severity") not in (
                    "none",
                    "trace",
                    "low",
                    "moderate",
                    "medium",
                    "high",
                    "critical",
                ):
                    score = float(entry.get("score", 0.0) or 0.0)
                    entry["severity"] = severity_from_score(score)
                scores.append(DomainScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DomainScore (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {d.domain for d in scores}
        for domain in EI_DOMAINS:
            if domain not in seen:
                scores.append(
                    DomainScore(
                        domain=domain,  # type: ignore[arg-type]
                        score=0.0,
                        severity="critical",
                        confidence=0.5,
                        explanation="No evidence of this domain observed.",
                        evidence_quotes=[],
                    )
                )

        order = {d: i for i, d in enumerate(EI_DOMAINS)}
        scores.sort(key=lambda s: order.get(s.domain, len(EI_DOMAINS)))
        return scores

    def _parse_interventions(self, raw: str) -> list[EIIntervention]:
        data = extract_json_array(raw)
        interventions: list[EIIntervention] = []
        for entry in data:
            try:
                interventions.append(EIIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed EIIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # ------------------------------------------------------------------
    # Deterministic synthesis
    # ------------------------------------------------------------------

    def _compute_axis_scores(self, domains: list[DomainScore]) -> EIAxisScores:
        by_domain = {d.domain: d.score for d in domains}
        sa = by_domain.get("self_awareness", 0.0)
        sm = by_domain.get("self_management", 0.0)
        soa = by_domain.get("social_awareness", 0.0)
        rm = by_domain.get("relationship_management", 0.0)
        self_col = (sa + sm) / 2.0
        other_col = (soa + rm) / 2.0
        rec_row = (sa + soa) / 2.0
        reg_row = (sm + rm) / 2.0
        return EIAxisScores(
            self_column=round(self_col, 4),
            other_column=round(other_col, 4),
            recognition_row=round(rec_row, 4),
            regulation_row=round(reg_row, 4),
            column_gap=round(abs(self_col - other_col), 4),
            row_gap=round(abs(rec_row - reg_row), 4),
        )

    def _classify_profile_pattern(
        self, domains: list[DomainScore], axis: EIAxisScores
    ) -> EIProfilePattern:
        scores = [d.score for d in domains]
        if not scores:
            return "indeterminate"
        if all(s >= 0.7 for s in scores):
            return "balanced_high"
        if all(s < 0.4 for s in scores):
            return "balanced_low"
        if all(0.4 <= s < 0.7 for s in scores):
            return "balanced_developing"
        # Column gap: SELF vs OTHER
        if axis.column_gap >= 0.25:
            if axis.self_column > axis.other_column:
                return "self_strong_other_weak"
            return "other_strong_self_weak"
        # Row gap: RECOGNITION vs REGULATION
        if axis.row_gap >= 0.25:
            if axis.recognition_row > axis.regulation_row:
                return "recognition_strong_regulation_weak"
            return "regulation_strong_recognition_weak"
        return "indeterminate"

    def _pick_weakest_domain(
        self,
        domains: list[DomainScore],
        llm_label: str = "",
    ) -> Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
        "none",
    ]:
        valid = {
            "self_awareness",
            "self_management",
            "social_awareness",
            "relationship_management",
            "none",
        }
        if llm_label and llm_label in valid:
            return cast(
                Literal[
                    "self_awareness",
                    "self_management",
                    "social_awareness",
                    "relationship_management",
                    "none",
                ],
                llm_label,
            )
        if not domains:
            return "none"
        # If all domains are >= 0.7, return 'none' (no weakest to flag).
        if all(d.score >= 0.7 for d in domains):
            return "none"
        weakest = min(domains, key=lambda d: d.score)
        return weakest.domain

    def _parse_meta(self, raw: str) -> dict[str, Any]:
        """Extract LLM-claimed metadata (overall_ei, ei_quality,
        weakest_domain) from a wrapper-object response, when present.
        """
        obj = _try_json_object(raw)
        if obj is None:
            return {}
        meta: dict[str, Any] = {}
        for key in ("overall_ei", "ei_quality", "weakest_domain"):
            if key in obj:
                meta[key] = obj[key]
        return meta

    def _ei_quality(
        self, overall_ei: float, llm_label: str = ""
    ) -> Literal["high-ei", "developing", "low-ei"]:
        """Bucket overall EI. ``llm_label`` is accepted for v0.0.x
        backward compatibility: when the LLM provided a label and it's
        valid, the LLM's choice is preserved.
        """
        valid = {"high-ei", "developing", "low-ei"}
        if llm_label and llm_label in valid:
            return cast(Literal["high-ei", "developing", "low-ei"], llm_label)
        if overall_ei >= 0.75:
            return "high-ei"
        if overall_ei >= 0.4:
            return "developing"
        return "low-ei"

    # ------------------------------------------------------------------
    # Composition + playbooks
    # ------------------------------------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentEITrace,
        domains: list[DomainScore],
        weakest_domain: str,
        profile_pattern: EIProfilePattern,
        interventions: list[EIIntervention],
    ) -> ComposedPatternHandoff:
        provisional = EIDetection(
            domains=domains,
            overall_ei=sum(d.score for d in domains) / max(len(domains), 1),
            ei_quality="developing",
            weakest_domain=weakest_domain,  # type: ignore[arg-type]
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "weakest_domain": weakest_domain,
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

    def _attach_playbooks(self, interventions: list[EIIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            pb = find_playbook_for_intervention(iv.target_domain, iv.intervention_type)
            if pb is not None and (pb.domain, pb.failure_mode) not in attached:
                attached[(pb.domain, pb.failure_mode)] = pb
        return list(attached.values())


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


class EIAuditDetectorAsync:
    """Async mirror of :class:`EIAuditDetector` using composition with the
    sync detector + an async-to-sync shim.
    """

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: EIMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: EIMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentEITrace,
        *,
        mode: EIMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> EIDetection:
        active_mode: EIMode = mode or self.mode

        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))

        sync_detector = EIAuditDetector(
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
            sync_detector.run, trace, mode=active_mode, baseline_path=baseline_path
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _PipelineAcc:
    """Per-run accumulator for token + cost + elapsed telemetry."""

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
    """Wrap an async ``complete`` callable as a synchronous client."""

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


_legacy_log = logging.getLogger("agentcity.goleman_ei.generator")
_legacy_log.addHandler(logging.NullHandler())
