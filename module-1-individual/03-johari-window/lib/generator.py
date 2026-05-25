"""JohariSelfAuditor: Luft & Ingham's four-quadrant self-awareness model
applied to AI agents.

The detector exposes three pipeline modes:

  - ``quick`` -- one combined LLM call (quadrants + dominant + top intervention).
    For CI / live ops. ~2s, ~$0.005.
  - ``standard`` -- two LLM calls (quadrants + interventions).
    For human-driven postmortems. ~5-10s, ~$0.02.
  - ``forensic`` -- five LLM calls (forensic-quadrants + feedback opportunities
    + disclosure opportunities + Stone-Heen mechanism diagnosis + ranked
    interventions). For deep dives. ~30s, ~$0.10.

Full v0.1.0 production infrastructure wired: structured logging with
run-id correlation, token / cost telemetry, input sanitization + fencing,
async mirror via composition with the sync detector.

Deterministic synthesis includes the Kadavath-style introspection
ceiling check, tool-receipt cross-reference, profile-pattern
classification, baseline drift, composition handoff, playbook attachment.
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
    FORENSIC_DISCLOSURE_OPPORTUNITY_PROMPT,
    FORENSIC_FEEDBACK_OPPORTUNITY_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_QUADRANT_ANALYSIS_PROMPT,
    JOHARI_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_QUADRANT_ANALYSIS_PROMPT,
    assemble_prompt,
)
from .schema import (
    QUADRANTS,
    AgentSelfReportTrace,
    AttachedPlaybook,
    CapabilityProbe,
    ComposedPatternHandoff,
    DisclosureOpportunity,
    FeedbackOpportunity,
    JohariIntervention,
    JohariMode,
    JohariProfilePattern,
    JohariSelfAudit,
    QuadrantContent,
    QuadrantSizeMetrics,
    severity_from_self_awareness,
)

log = get_logger("vstack.johari.generator")


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


class JohariSelfAuditor:
    """Run the Johari Window self-audit on an :class:`AgentSelfReportTrace`."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: JohariMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: JohariMode = mode
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
        trace: AgentSelfReportTrace,
        *,
        mode: JohariMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> JohariSelfAudit:
        active_mode: JohariMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="johari"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentSelfReportTrace],
        *,
        mode: JohariMode | None = None,
    ) -> Iterator[JohariSelfAudit]:
        active_mode: JohariMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="johari"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    # ------------------------------------------------------------------
    # Pipeline dispatch
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        trace: AgentSelfReportTrace,
        mode: JohariMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> JohariSelfAudit:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)

        started = time.monotonic()
        log.info(
            "Running Johari self-audit (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()

        # Deterministic pre-LLM step: tool-receipt cross-reference.
        receipt_blind_findings = self._cross_check_tool_receipts(trace)

        if mode == "quick":
            quadrants, blind_register, hidden_register, top_intervention = self._pass_quick(
                trace, acc
            )
            feedback_opportunities: list[FeedbackOpportunity] = []
            disclosure_opportunities: list[DisclosureOpportunity] = []
            capability_probes: list[CapabilityProbe] = []
            interventions = [top_intervention] if top_intervention else []
        elif mode == "standard":
            quadrants, blind_register, hidden_register = self._pass_standard_quadrants(trace, acc)
            interventions = self._pass_standard_interventions(
                trace, quadrants, blind_register, hidden_register, acc
            )
            feedback_opportunities = []
            disclosure_opportunities = []
            capability_probes = []
        elif mode == "forensic":
            quadrants, blind_register, hidden_register = self._pass_forensic_quadrants(trace, acc)
            feedback_opportunities = self._pass_forensic_feedback_opportunities(
                trace, blind_register, acc
            )
            disclosure_opportunities = self._pass_forensic_disclosure_opportunities(
                trace, hidden_register, acc
            )
            capability_probes = []
            interventions = self._pass_forensic_interventions(
                trace,
                quadrants,
                feedback_opportunities,
                disclosure_opportunities,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown JohariMode: {mode!r}")

        # Merge deterministic tool-receipt blind findings into blind_register.
        for entry in receipt_blind_findings:
            if entry not in blind_register:
                blind_register.append(entry)

        # Deterministic synthesis.
        weights = self._build_weights(quadrants)
        dominant = self._dominant_quadrant(weights)
        self_awareness = self._self_awareness_score(weights)
        severity = severity_from_self_awareness(self_awareness)
        qsm = self._compute_quadrant_size_metrics(weights, quadrants)
        profile_pattern = self._classify_profile_pattern(weights, quadrants)
        introspection_exceeded = self._check_introspection_ceiling(
            self_awareness, trace.expected_introspection_ceiling
        )

        composition = (
            self._build_composition_handoff(trace, dominant, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_audit_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = JohariSelfAudit(
                    dominant_quadrant=dominant,
                    quadrant_weights=weights,
                    quadrants=quadrants,
                    self_awareness_score=self_awareness,
                    blind_spot_register=blind_register,
                    hidden_content_register=hidden_register,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed (%s): %r", type(exc).__name__, exc)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        audit = JohariSelfAudit(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_quadrant=dominant,
            quadrant_weights=weights,
            quadrants=quadrants,
            self_awareness_score=round(self_awareness, 4),
            blind_spot_register=blind_register,
            hidden_content_register=hidden_register,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            profile_pattern=profile_pattern,
            severity=severity,
            quadrant_size_metrics=qsm,
            feedback_opportunities=feedback_opportunities,
            disclosure_opportunities=disclosure_opportunities,
            capability_probes=capability_probes,
            attached_playbooks=playbooks,
            baseline=baseline,
            composition_handoff=composition,
            subject_introspection_ceiling=trace.expected_introspection_ceiling,
            introspection_ceiling_exceeded=introspection_exceeded,
            run_id=run_id,
            cost_usd=acc.cost_usd,
            tokens_total=acc.tokens_total,
            tokens_input=acc.tokens_input,
            tokens_output=acc.tokens_output,
            llm_calls=acc.llm_calls,
            elapsed_ms=elapsed_ms,
            injection_detected=injection_detected,
        )

        log.info(
            "Johari audit done mode=%s dominant=%s profile=%s self_awareness=%.2f "
            "elapsed=%.0fms tokens=%d cost=$%.4f",
            mode,
            dominant,
            profile_pattern,
            self_awareness,
            elapsed_ms,
            acc.tokens_total,
            acc.cost_usd,
        )
        return audit

    # ------------------------------------------------------------------
    # Validation + sanitization scan + deterministic tool-receipt check
    # ------------------------------------------------------------------

    def _validate_trace(self, trace: AgentSelfReportTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentSelfReportTrace.task cannot be empty.")
        if not trace.self_report or not trace.self_report.strip():
            raise ValueError("AgentSelfReportTrace.self_report cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentSelfReportTrace.outcome cannot be empty.")
        if not trace.turns:
            raise ValueError("AgentSelfReportTrace.turns cannot be empty.")

    def _scan_injection(self, trace: AgentSelfReportTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("self_report", trace.self_report),
            ("outcome", trace.outcome),
        ]
        for i, turn in enumerate(trace.turns):
            targets.append((f"turns[{i}].content", turn.content))
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

    def _cross_check_tool_receipts(self, trace: AgentSelfReportTrace) -> list[str]:
        """Deterministic pre-LLM check: when the agent's self-report or
        trace claims a tool was used but no matching ToolReceipt exists,
        flag as BLIND content. Basu et al. 2026.

        Returns a list of blind-register entries to merge.
        """
        if not trace.tool_receipts:
            return []
        receipt_tools = {r.tool_name for r in trace.tool_receipts}
        findings: list[str] = []
        # Scan turns for tool calls.
        for i, turn in enumerate(trace.turns):
            if turn.role == "tool":
                # The turn.content is typically the tool name or its args.
                # If we have a tool receipt that mentions content tokens,
                # consider it covered. Conservative: only flag when no
                # receipts match at all.
                content_lower = turn.content.lower()
                claimed_tool = next((t for t in receipt_tools if t.lower() in content_lower), None)
                if claimed_tool is None and receipt_tools:
                    findings.append(
                        f"Tool call at turn {i} ({turn.content[:60]}) has no matching "
                        f"ToolReceipt (receipts: {sorted(receipt_tools)}). "
                        f"Possible hallucinated tool call (Basu 2026)."
                    )
        return findings

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: JohariMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=JOHARI_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "johari"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # ------------------------------------------------------------------
    # Mode: QUICK
    # ------------------------------------------------------------------

    def _pass_quick(
        self,
        trace: AgentSelfReportTrace,
        acc: "_PipelineAcc",
    ) -> tuple[list[QuadrantContent], list[str], list[str], JohariIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            expected_introspection_ceiling=trace.expected_introspection_ceiling,
            outcome=trace.outcome,
            success=trace.success,
            self_report=trace.self_report,
            turns=[t.model_dump() for t in trace.turns],
            tool_receipts=[r.model_dump() for r in trace.tool_receipts],
        )
        raw = self._call(prompt, pass_name="quick_combined", mode="quick", acc=acc)

        obj = _try_json_object(raw)
        quadrants = self._parse_quadrants_from_obj(obj or {})
        blind_register = (
            [s for s in obj.get("blind_spot_register", []) if isinstance(s, str)] if obj else []
        )
        hidden_register = (
            [s for s in obj.get("hidden_content_register", []) if isinstance(s, str)] if obj else []
        )

        top_intervention: JohariIntervention | None = None
        if obj:
            iv_entry = obj.get("top_intervention")
            if iv_entry:
                try:
                    top_intervention = JohariIntervention(**iv_entry)
                except Exception as exc:
                    log.warning(
                        "Quick-mode: failed to parse top_intervention (%s)",
                        type(exc).__name__,
                    )
        return quadrants, blind_register, hidden_register, top_intervention

    # ------------------------------------------------------------------
    # Mode: STANDARD
    # ------------------------------------------------------------------

    def _pass_standard_quadrants(
        self,
        trace: AgentSelfReportTrace,
        acc: "_PipelineAcc",
    ) -> tuple[list[QuadrantContent], list[str], list[str]]:
        prompt = assemble_prompt(
            STANDARD_QUADRANT_ANALYSIS_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            expected_introspection_ceiling=trace.expected_introspection_ceiling,
            outcome=trace.outcome,
            success=trace.success,
            self_report=trace.self_report,
            turns=[t.model_dump() for t in trace.turns],
            tool_receipts=[r.model_dump() for r in trace.tool_receipts],
        )
        raw = self._call(prompt, pass_name="standard_quadrants", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        quadrants = self._parse_quadrants_from_obj(obj)
        blind_register = [s for s in obj.get("blind_spot_register", []) if isinstance(s, str)]
        hidden_register = [s for s in obj.get("hidden_content_register", []) if isinstance(s, str)]
        return quadrants, blind_register, hidden_register

    def _pass_standard_interventions(
        self,
        trace: AgentSelfReportTrace,
        quadrants: list[QuadrantContent],
        blind_register: list[str],
        hidden_register: list[str],
        acc: "_PipelineAcc",
    ) -> list[JohariIntervention]:
        weights = self._build_weights(quadrants)
        dominant = self._dominant_quadrant(weights)
        if dominant == "open":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            dominant_quadrant=dominant,
            quadrants=[q.model_dump() for q in quadrants],
            blind_spot_register=blind_register,
            hidden_content_register=hidden_register,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Mode: FORENSIC
    # ------------------------------------------------------------------

    def _pass_forensic_quadrants(
        self,
        trace: AgentSelfReportTrace,
        acc: "_PipelineAcc",
    ) -> tuple[list[QuadrantContent], list[str], list[str]]:
        prompt = assemble_prompt(
            FORENSIC_QUADRANT_ANALYSIS_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            expected_introspection_ceiling=trace.expected_introspection_ceiling,
            outcome=trace.outcome,
            success=trace.success,
            self_report=trace.self_report,
            turns=[t.model_dump() for t in trace.turns],
            tool_receipts=[r.model_dump() for r in trace.tool_receipts],
        )
        raw = self._call(prompt, pass_name="forensic_quadrants", mode="forensic", acc=acc)
        obj = _try_json_object(raw) or {}
        quadrants = self._parse_quadrants_from_obj(obj)
        blind_register = [s for s in obj.get("blind_spot_register", []) if isinstance(s, str)]
        hidden_register = [s for s in obj.get("hidden_content_register", []) if isinstance(s, str)]
        return quadrants, blind_register, hidden_register

    def _pass_forensic_feedback_opportunities(
        self,
        trace: AgentSelfReportTrace,
        blind_register: list[str],
        acc: "_PipelineAcc",
    ) -> list[FeedbackOpportunity]:
        if not blind_register:
            return []
        prompt = assemble_prompt(
            FORENSIC_FEEDBACK_OPPORTUNITY_PROMPT,
            blind_spot_register=blind_register,
            turns=[t.model_dump() for t in trace.turns],
            tool_receipts=[r.model_dump() for r in trace.tool_receipts],
        )
        raw = self._call(prompt, pass_name="forensic_feedback_opps", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        opportunities: list[FeedbackOpportunity] = []
        for entry in data:
            try:
                opportunities.append(FeedbackOpportunity(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed FeedbackOpportunity (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return opportunities

    def _pass_forensic_disclosure_opportunities(
        self,
        trace: AgentSelfReportTrace,
        hidden_register: list[str],
        acc: "_PipelineAcc",
    ) -> list[DisclosureOpportunity]:
        if not hidden_register:
            return []
        prompt = assemble_prompt(
            FORENSIC_DISCLOSURE_OPPORTUNITY_PROMPT,
            hidden_content_register=hidden_register,
            turns=[t.model_dump() for t in trace.turns],
        )
        raw = self._call(prompt, pass_name="forensic_disclosure_opps", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        opportunities: list[DisclosureOpportunity] = []
        for entry in data:
            try:
                opportunities.append(DisclosureOpportunity(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed DisclosureOpportunity (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return opportunities

    def _pass_forensic_interventions(
        self,
        trace: AgentSelfReportTrace,
        quadrants: list[QuadrantContent],
        feedback_opportunities: list[FeedbackOpportunity],
        disclosure_opportunities: list[DisclosureOpportunity],
        acc: "_PipelineAcc",
    ) -> list[JohariIntervention]:
        weights = self._build_weights(quadrants)
        dominant = self._dominant_quadrant(weights)
        if dominant == "open":
            return []
        qsm = self._compute_quadrant_size_metrics(weights, quadrants)
        profile = self._classify_profile_pattern(weights, quadrants)
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant_quadrant=dominant,
            profile_pattern=profile,
            quadrants=[q.model_dump() for q in quadrants],
            feedback_opportunities=[f.model_dump() for f in feedback_opportunities],
            disclosure_opportunities=[d.model_dump() for d in disclosure_opportunities],
            turns=[t.model_dump() for t in trace.turns],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        # Mark qsm usage to avoid linter complaint -- it's used in handoff.
        del qsm
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_quadrants_from_obj(self, obj: dict[str, Any]) -> list[QuadrantContent]:
        raw_quadrants = obj.get("quadrants", [])
        if not isinstance(raw_quadrants, list):
            raw_quadrants = []
        quadrants: list[QuadrantContent] = []
        for entry in raw_quadrants:
            if not isinstance(entry, dict):
                continue
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
                    weight = float(entry.get("weight", 0.0) or 0.0)
                    # For inverse-polarity severity: high weight on
                    # OPEN -> none; high weight on BLIND/HIDDEN/UNKNOWN
                    # -> high severity. We use weight as the score proxy
                    # but invert for the non-open quadrants.
                    if entry.get("quadrant") == "open":
                        entry["severity"] = severity_from_self_awareness(weight)
                    else:
                        entry["severity"] = severity_from_self_awareness(1.0 - weight)
                quadrants.append(QuadrantContent(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed QuadrantContent (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {q.quadrant for q in quadrants}
        for q in QUADRANTS:
            if q not in seen:
                quadrants.append(
                    QuadrantContent(
                        quadrant=q,  # type: ignore[arg-type]
                        weight=0.0,
                        severity="critical" if q in {"blind", "hidden"} else "none",
                        classification_confidence=0.5,
                        explanation="No evidence of this quadrant in trace.",
                        evidence_quotes=[],
                    )
                )
        order = {q: i for i, q in enumerate(QUADRANTS)}
        quadrants.sort(key=lambda x: order.get(x.quadrant, len(QUADRANTS)))
        return quadrants

    def _parse_interventions(self, raw: str) -> list[JohariIntervention]:
        data = extract_json_array(raw)
        interventions: list[JohariIntervention] = []
        for entry in data:
            try:
                interventions.append(JohariIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed JohariIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # ------------------------------------------------------------------
    # Deterministic synthesis
    # ------------------------------------------------------------------

    def _build_weights(self, quadrants: list[QuadrantContent]) -> dict[str, float]:
        weights: dict[str, float] = {q: 0.0 for q in QUADRANTS}
        for q in quadrants:
            weights[q.quadrant] = max(weights.get(q.quadrant, 0.0), q.weight)
        return weights

    def _dominant_quadrant(
        self, weights: dict[str, float]
    ) -> Literal["open", "blind", "hidden", "unknown"]:
        max_weight = max(weights.values(), default=0.0)
        if max_weight <= 0.0:
            return "open"  # default to healthy when there's no signal
        # Tie-break order: blind, hidden, unknown, open
        ordered = ("blind", "hidden", "unknown", "open")
        for q in ordered:
            if weights.get(q, 0.0) >= max_weight - 0.05:
                return q  # type: ignore[return-value]
        return "open"

    def _self_awareness_score(self, weights: dict[str, float]) -> float:
        """Self-awareness = (open + 0.5*hidden) / (open + 0.5*hidden + blind + 0.3*unknown).

        Higher OPEN -> higher score. Higher BLIND -> lower score. HIDDEN is
        half-credit (some hidden is functional; Hase et al. 1999). UNKNOWN
        is 30% penalty (we don't know what we don't know, but it's not as
        bad as known-blind).
        """
        open_w = weights.get("open", 0.0)
        blind_w = weights.get("blind", 0.0)
        hidden_w = weights.get("hidden", 0.0)
        unknown_w = weights.get("unknown", 0.0)

        numerator = open_w + 0.5 * hidden_w
        denominator = numerator + blind_w + 0.3 * unknown_w

        if denominator <= 0.0:
            return 0.5
        return max(0.0, min(1.0, numerator / denominator))

    def _compute_quadrant_size_metrics(
        self,
        weights: dict[str, float],
        quadrants: list[QuadrantContent],
    ) -> QuadrantSizeMetrics:
        total = sum(weights.values())
        if total <= 0.0:
            # No signal -- treat as fully unknown.
            return QuadrantSizeMetrics(
                open_proportion=0.25,
                blind_proportion=0.25,
                hidden_proportion=0.25,
                unknown_proportion=0.25,
                proportions_sum=1.0,
                open_arena_growth_potential=0.0,
            )
        open_p = weights.get("open", 0.0) / total
        blind_p = weights.get("blind", 0.0) / total
        hidden_p = weights.get("hidden", 0.0) / total
        unknown_p = weights.get("unknown", 0.0) / total
        # Growth potential: room to expand OPEN.
        # If blind + hidden are both small, growth potential is small.
        # If either is large, growth potential is correspondingly large.
        growth_potential = min(1.0, 0.7 * blind_p + 0.5 * hidden_p + 0.3 * unknown_p)
        return QuadrantSizeMetrics(
            open_proportion=round(open_p, 4),
            blind_proportion=round(blind_p, 4),
            hidden_proportion=round(hidden_p, 4),
            unknown_proportion=round(unknown_p, 4),
            proportions_sum=round(open_p + blind_p + hidden_p + unknown_p, 4),
            open_arena_growth_potential=round(growth_potential, 4),
        )

    def _classify_profile_pattern(
        self,
        weights: dict[str, float],
        quadrants: list[QuadrantContent],
    ) -> JohariProfilePattern:
        open_w = weights.get("open", 0.0)
        blind_w = weights.get("blind", 0.0)
        hidden_w = weights.get("hidden", 0.0)
        unknown_w = weights.get("unknown", 0.0)

        # Balanced patterns
        all_high = all(w >= 0.5 for w in weights.values())
        if all_high:
            return "balanced_high"
        all_low = all(w < 0.3 for w in weights.values())
        if all_low:
            return "balanced_low"
        # balanced growth: large OPEN, small healthy HIDDEN/BLIND
        if open_w >= 0.6 and hidden_w < 0.3 and blind_w < 0.3 and unknown_w < 0.3:
            return "balanced_growth"
        # Eurich split is checked FIRST when the gap is clearly large enough
        # to point at one direction. internal = open + hidden;
        # external = open + blind.
        internal = open_w + hidden_w
        external = open_w + blind_w
        gap = abs(external - internal)
        # Strong Eurich pattern: large gap AND blind/hidden are not the
        # extreme dominant case yet (>= 0.6 reserves for confabulating /
        # opaque_to_users).
        if gap >= 0.3 and blind_w < 0.6 and hidden_w < 0.6:
            if external - internal >= 0.3:
                return "self_unaware_other_aware"
            return "self_aware_other_unaware"
        # Specific dominant patterns
        if blind_w >= 0.5 and blind_w > hidden_w + 0.15:
            return "confabulating"
        if hidden_w >= 0.5 and hidden_w > blind_w + 0.15:
            return "opaque_to_users"
        if unknown_w >= 0.45:
            return "sandbagging"
        if open_w >= 0.7 and hidden_w < 0.1:
            return "over_disclosing"
        # Mild Eurich gap.
        if external - internal >= 0.25:
            return "self_unaware_other_aware"
        if internal - external >= 0.25:
            return "self_aware_other_unaware"
        return "indeterminate"

    def _check_introspection_ceiling(self, self_awareness_score: float, ceiling: float) -> bool:
        """Anthropic 2025 introspection ceiling check.

        Returns True if the self-awareness score significantly exceeds
        the empirical ceiling, indicating the model is claiming more
        self-awareness than research suggests is achievable.
        """
        return self_awareness_score > (ceiling + 0.30)

    # ------------------------------------------------------------------
    # Composition + playbooks
    # ------------------------------------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentSelfReportTrace,
        dominant: str,
        profile_pattern: JohariProfilePattern,
        interventions: list[JohariIntervention],
    ) -> ComposedPatternHandoff:
        provisional = JohariSelfAudit(
            dominant_quadrant=dominant,  # type: ignore[arg-type]
            quadrant_weights={q: 0.0 for q in QUADRANTS},
            quadrants=[],
            self_awareness_score=0.5,
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_quadrant": dominant,
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

    def _attach_playbooks(self, interventions: list[JohariIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            pb = find_playbook_for_intervention(iv.target_quadrant, iv.intervention_type)
            if pb is not None and (pb.quadrant, pb.failure_mode) not in attached:
                attached[(pb.quadrant, pb.failure_mode)] = pb
        return list(attached.values())


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


class JohariSelfAuditorAsync:
    """Async mirror of :class:`JohariSelfAuditor`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: JohariMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: JohariMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentSelfReportTrace,
        *,
        mode: JohariMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> JohariSelfAudit:
        active_mode: JohariMode = mode or self.mode

        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))

        sync_detector = JohariSelfAuditor(
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


_legacy_log = logging.getLogger("vstack.johari.generator")
_legacy_log.addHandler(logging.NullHandler())
