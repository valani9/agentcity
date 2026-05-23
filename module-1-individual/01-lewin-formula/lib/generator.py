"""LewinAttributionDetector: diagnose Kurt Lewin's B = f(P, E) locus
(internal / environmental / interactional) for an agent failure trace.

The detector exposes three pipeline modes:

  - ``quick`` — one LLM call (combined scoring + top intervention).
    For CI / live ops. ~2s, ~$0.005.
  - ``standard`` — two LLM calls (current v0.0.x behavior, refined).
    For human-driven postmortems. ~10s, ~$0.05.
  - ``forensic`` — four LLM calls (Kelley covariance scoring +
    counterfactuals + Gilbert-Malone bias mechanism + ranked
    interventions with composition targets). For deep dives. ~60s,
    ~$0.30.

Each mode wires the full v0.1.0 production-readiness infrastructure:
structured logging with run-id correlation, token / cost telemetry,
input sanitization + fencing, and (via the async mirror)
non-blocking pipelines.

The deterministic synthesis steps (locus aggregation, dominant-locus
selection, attribution-quality bucketing, initial-attribution check,
covariance prior, baseline comparison, composition handoff, playbook
attachment) all live in pure Python — the LLM never overrides the
math.
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
from ._playbooks import find_playbook
from .prompts import (
    BIAS_MECHANISM_PROMPT,
    COUNTERFACTUAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_LOCUS_SCORING_PROMPT,
    LEWIN_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_LOCUS_SCORING_PROMPT,
    assemble_prompt,
)
from .schema import (
    LOCI,
    AgentFailureTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CovarianceSignal,
    GilbertMaloneMechanism,
    LewinDetection,
    LewinIntervention,
    LewinMode,
    LocusEvidence,
    severity_from_score,
)

log = get_logger("agentcity.lewin.generator")


# Provider-agnostic per-1k-token rough cost table for telemetry's cost
# estimation. Real billing happens at the provider; this is just a
# coarse "what did this run roughly cost" signal for dashboards.
_DEFAULT_COST_PER_1K = {
    "input": 0.003,
    "output": 0.015,
}


class LLMClient(Protocol):
    """The single-method synchronous LLM client contract."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    """The single-method asynchronous LLM client contract."""

    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class LewinAttributionDetector:
    """Run the Lewin B = f(P, E) diagnostic on an :class:`AgentFailureTrace`.

    The detector is mode-aware. The ``mode`` parameter at construction
    sets the default mode for ``.run(trace)``; individual calls can
    override via ``.run(trace, mode="...")``.

    Construction is cheap; the LLM client is held but not exercised
    until :meth:`run` is called. Detectors are thread-safe for read-only
    access to the underlying client; the in-process telemetry sink
    (``agentcity.aar.set_default_sink``) is itself thread-safe.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: LewinMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: LewinMode = mode
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
        trace: AgentFailureTrace,
        *,
        mode: LewinMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> LewinDetection:
        """Run the diagnostic. Returns a fully populated :class:`LewinDetection`.

        ``mode`` overrides the constructor default for this call.
        ``baseline_path`` triggers drift comparison against a stored
        detection.
        """
        active_mode: LewinMode = mode or self.mode
        run_id = new_run_id()

        with run_context(run_id, pattern="lewin"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentFailureTrace],
        *,
        mode: LewinMode | None = None,
    ) -> Iterator[LewinDetection]:
        """Run the diagnostic over an iterable of traces, yielding detections.

        Each trace gets its own ``run_id``. The detector instance is
        reused; only the LLM client is exercised.
        """
        active_mode: LewinMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="lewin"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    # ------------------------------------------------------------------
    # Pipeline dispatch
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        trace: AgentFailureTrace,
        mode: LewinMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> LewinDetection:
        self._validate_trace(trace)
        self._scan_injection(trace)

        started = time.monotonic()
        log.info(
            "Running Lewin diagnostic (mode=%s) for agent %s steps=%d",
            mode,
            trace.agent_id or "<unknown>",
            len(trace.steps),
        )

        # Acc carriers: per-call telemetry rolls up into these.
        acc = _PipelineAcc()

        trace_text = self._serialize_trace(trace)

        if mode == "quick":
            evidence, top_intervention = self._pass_quick(trace, trace_text, acc)
            interventions = [top_intervention] if top_intervention else []
            bias_mechanism: GilbertMaloneMechanism = "none"
        elif mode == "standard":
            evidence = self._pass_standard_loci(trace, trace_text, acc)
            interventions = self._pass_standard_interventions(trace, trace_text, evidence, acc)
            bias_mechanism = "none"
        elif mode == "forensic":
            evidence = self._pass_forensic_loci(trace, trace_text, acc)
            evidence = self._pass_forensic_counterfactuals(evidence, trace, trace_text, acc)
            bias_mechanism = self._pass_forensic_bias_mechanism(evidence, trace, trace_text, acc)
            interventions = self._pass_forensic_interventions(
                trace, trace_text, evidence, bias_mechanism, acc
            )
        else:  # pragma: no cover — exhaustive check
            raise ValueError(f"unknown LewinMode: {mode!r}")

        evidence = self._apply_covariance_prior(evidence, trace.covariance_signal)
        locus_scores = self._build_scores(evidence)
        dominant = self._dominant_locus(locus_scores)
        quality = self._attribution_quality(locus_scores)
        initial_correct = self._check_initial_attribution(trace, dominant)

        composition = (
            self._build_composition_handoff(trace, dominant, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = (
            self._attach_playbooks(dominant, interventions, trace) if self.playbooks_enabled else []
        )

        baseline = None
        if baseline_path:
            try:
                bl = load_baseline(baseline_path)
                # Build a minimal current detection to compare; deltas are
                # purely from locus_scores + dominant_locus.
                provisional_curr = LewinDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    dominant_locus=dominant,
                    locus_scores=locus_scores,
                    loci=evidence,
                    interventions=interventions,
                    attribution_quality=quality,
                    initial_attribution_correct=initial_correct,
                    generator_model=self.model,
                    success=trace.success,
                    mode=mode,
                    run_id=run_id,
                )
                baseline = compare_to_baseline(provisional_curr, bl)
            except Exception as exc:  # pragma: no cover — defensive
                log.warning("Baseline comparison failed (%s): %r", type(exc).__name__, exc)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = LewinDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            dominant_locus=dominant,
            locus_scores=locus_scores,
            loci=evidence,
            interventions=interventions,
            attribution_quality=quality,
            initial_attribution_correct=initial_correct,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            covariance_signal=trace.covariance_signal,
            baseline=baseline,
            composition_handoff=composition,
            attached_playbooks=playbooks,
            bias_mechanism=bias_mechanism,
            cost_usd=acc.cost_usd,
            tokens_total=acc.tokens_total,
            tokens_input=acc.tokens_input,
            tokens_output=acc.tokens_output,
            llm_calls=acc.llm_calls,
            elapsed_ms=elapsed_ms,
            run_id=run_id,
        )

        log.info(
            "Lewin diagnostic done mode=%s dominant=%s quality=%s elapsed=%.0fms tokens=%d cost=$%.4f",
            mode,
            dominant,
            quality,
            elapsed_ms,
            acc.tokens_total,
            acc.cost_usd,
        )
        return detection

    # ------------------------------------------------------------------
    # Validation + sanitization scan
    # ------------------------------------------------------------------

    def _validate_trace(self, trace: AgentFailureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentFailureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentFailureTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("AgentFailureTrace.steps cannot be empty.")

    def _scan_injection(self, trace: AgentFailureTrace) -> None:
        """Run :func:`detect_injection` on every free-text field; log hits.

        Does NOT block — sanitization at prompt-assembly time handles
        the actual interpolation. The detection is informational, and
        becomes observable via the structured-logging pipeline.
        """
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
        ]
        if trace.initial_attribution:
            targets.append(("initial_attribution", trace.initial_attribution))
        for i, step in enumerate(trace.steps):
            targets.append((f"step[{i}].content", step.content))
        for i, p_factor in enumerate(trace.individual_factors):
            targets.append((f"individual_factors[{i}].description", p_factor.description))
        for i, e_factor in enumerate(trace.environmental_factors):
            targets.append((f"environmental_factors[{i}].description", e_factor.description))

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

    # ------------------------------------------------------------------
    # LLM call + telemetry helper
    # ------------------------------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: LewinMode,
        acc: "_PipelineAcc",
    ) -> str:
        """Issue one LLM call, wrap in time_call(), record telemetry."""
        with time_call() as t:
            raw = self._complete(prompt, system=LEWIN_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "lewin"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # ------------------------------------------------------------------
    # Mode: QUICK (single combined call)
    # ------------------------------------------------------------------

    def _pass_quick(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[LocusEvidence], LewinIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            initial_attribution=trace.initial_attribution,
            individual_factors=[f.model_dump() for f in trace.individual_factors],
            environmental_factors=[f.model_dump() for f in trace.environmental_factors],
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick_combined", mode="quick", acc=acc)
        evidence = self._parse_loci(raw)

        # Quick mode wraps response as JSON object {loci: [...], top_intervention: {...}}.
        # Parse the top intervention from the same response.
        top_intervention: LewinIntervention | None = None
        try:
            obj = _try_json_object(raw)
            iv_entry = obj.get("top_intervention") if obj else None
            if iv_entry:
                top_intervention = LewinIntervention(**iv_entry)
        except Exception as exc:
            log.warning(
                "Quick-mode: failed to parse top_intervention (%s)",
                type(exc).__name__,
            )
        return evidence, top_intervention

    # ------------------------------------------------------------------
    # Mode: STANDARD (two calls)
    # ------------------------------------------------------------------

    def _pass_standard_loci(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> list[LocusEvidence]:
        prompt = assemble_prompt(
            STANDARD_LOCUS_SCORING_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            initial_attribution=trace.initial_attribution,
            individual_factors=[f.model_dump() for f in trace.individual_factors],
            environmental_factors=[f.model_dump() for f in trace.environmental_factors],
            covariance_signal=(
                trace.covariance_signal.model_dump() if trace.covariance_signal else None
            ),
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="standard_loci", mode="standard", acc=acc)
        return self._parse_loci(raw)

    def _pass_standard_interventions(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        evidence: list[LocusEvidence],
        acc: "_PipelineAcc",
    ) -> list[LewinIntervention]:
        # Skip intervention generation when the diagnostic is indeterminate.
        provisional_scores = self._build_scores(evidence)
        provisional_dominant = self._dominant_locus(provisional_scores)
        if provisional_dominant == "indeterminate":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            dominant=provisional_dominant,
            evidence=[e.model_dump() for e in evidence],
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Mode: FORENSIC (four calls)
    # ------------------------------------------------------------------

    def _pass_forensic_loci(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> list[LocusEvidence]:
        prompt = assemble_prompt(
            FORENSIC_LOCUS_SCORING_PROMPT,
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            framework=trace.framework or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            initial_attribution=trace.initial_attribution,
            individual_factors=[f.model_dump() for f in trace.individual_factors],
            environmental_factors=[f.model_dump() for f in trace.environmental_factors],
            covariance_signal=(
                trace.covariance_signal.model_dump() if trace.covariance_signal else None
            ),
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="forensic_loci", mode="forensic", acc=acc)
        return self._parse_loci(raw)

    def _pass_forensic_counterfactuals(
        self,
        evidence: list[LocusEvidence],
        trace: AgentFailureTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> list[LocusEvidence]:
        prompt = assemble_prompt(
            COUNTERFACTUAL_PROMPT,
            evidence=[e.model_dump() for e in evidence],
            individual_factors=[f.model_dump() for f in trace.individual_factors],
            environmental_factors=[f.model_dump() for f in trace.environmental_factors],
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="forensic_counterfactuals", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        cf_by_locus: dict[str, str] = {}
        for entry in data:
            locus = entry.get("locus")
            cf = entry.get("counterfactual", "")
            if isinstance(locus, str) and isinstance(cf, str) and cf:
                cf_by_locus[locus] = cf
        for ev in evidence:
            if ev.locus in cf_by_locus:
                ev.counterfactual = cf_by_locus[ev.locus]
        return evidence

    def _pass_forensic_bias_mechanism(
        self,
        evidence: list[LocusEvidence],
        trace: AgentFailureTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> GilbertMaloneMechanism:
        if not trace.initial_attribution:
            return "none"
        provisional_dominant = self._dominant_locus(self._build_scores(evidence))
        if provisional_dominant == "indeterminate":
            return "none"
        prompt = assemble_prompt(
            BIAS_MECHANISM_PROMPT,
            initial_attribution=trace.initial_attribution,
            dominant_locus=provisional_dominant,
            evidence=[e.model_dump() for e in evidence],
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="forensic_bias_mechanism", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return "none"
        mech_raw = obj.get("bias_mechanism", "none")
        valid: set[str] = {
            "unaware",
            "unrealistic_expectation",
            "over_categorization",
            "incomplete_correction",
            "none",
        }
        if mech_raw not in valid:
            log.warning("Forensic: unknown bias_mechanism %r; defaulting to 'none'", mech_raw)
            return "none"
        return cast(GilbertMaloneMechanism, mech_raw)

    def _pass_forensic_interventions(
        self,
        trace: AgentFailureTrace,
        trace_text: str,
        evidence: list[LocusEvidence],
        bias_mechanism: GilbertMaloneMechanism,
        acc: "_PipelineAcc",
    ) -> list[LewinIntervention]:
        provisional_scores = self._build_scores(evidence)
        provisional_dominant = self._dominant_locus(provisional_scores)
        if provisional_dominant == "indeterminate":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant=provisional_dominant,
            evidence=[e.model_dump() for e in evidence],
            trace=trace_text,
            bias_mechanism=bias_mechanism,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_loci(self, raw: str) -> list[LocusEvidence]:
        # Accept either a top-level array or an object with a "loci" key
        # (quick-mode response shape).
        data = extract_json_array(raw)
        if not data:
            obj = _try_json_object(raw)
            if obj and isinstance(obj.get("loci"), list):
                data = [x for x in obj["loci"] if isinstance(x, dict)]

        evidence: list[LocusEvidence] = []
        for entry in data:
            try:
                # Backward compat: tolerate v0.0.x severity values.
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
                evidence.append(LocusEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LocusEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.locus for ev in evidence}
        for locus in LOCI:
            if locus not in seen:
                evidence.append(
                    LocusEvidence(
                        locus=locus,  # type: ignore[arg-type]
                        score=0.0,
                        severity="none",
                        explanation="No evidence of this locus observed.",
                        evidence_quotes=[],
                    )
                )

        order = {locus: i for i, locus in enumerate(LOCI)}
        evidence.sort(key=lambda e: order.get(e.locus, len(LOCI)))
        return evidence

    def _parse_interventions(self, raw: str) -> list[LewinIntervention]:
        data = extract_json_array(raw)
        interventions: list[LewinIntervention] = []
        for entry in data:
            try:
                interventions.append(LewinIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LewinIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # ------------------------------------------------------------------
    # Deterministic synthesis
    # ------------------------------------------------------------------

    def _apply_covariance_prior(
        self, evidence: list[LocusEvidence], cov: CovarianceSignal | None
    ) -> list[LocusEvidence]:
        """Apply Kelley (1967) covariance priors deterministically.

        The LLM is told about covariance in its prompt, but the
        deterministic prior also nudges the scores so the final number
        is calibrated even if the LLM under-weighted the signal.

        Nudge mapping (kept small; thresholds tuned for ±0.05–0.10 max):
          - high consensus + high distinctiveness + high consistency
              → +0.05 to environmental
          - low consensus + low distinctiveness + high consistency
              → +0.05 to internal
          - low consensus + high distinctiveness + low consistency
              → +0.05 to interactional
        """
        if cov is None:
            return evidence
        nudge: dict[str, float] = {}
        if cov.consensus == "high" and cov.distinctiveness == "high" and cov.consistency == "high":
            nudge["environmental"] = 0.05
        elif cov.consensus == "low" and cov.distinctiveness == "low" and cov.consistency == "high":
            nudge["internal"] = 0.05
        elif cov.consensus == "low" and cov.distinctiveness == "high" and cov.consistency == "low":
            nudge["interactional"] = 0.05
        if not nudge:
            return evidence
        for ev in evidence:
            if ev.locus in nudge:
                ev.score = min(1.0, ev.score + nudge[ev.locus])
                # Update severity to match the nudged score if the original
                # severity was lower than what the score now warrants.
                derived = severity_from_score(ev.score)
                if _severity_rank(derived) > _severity_rank(ev.severity):
                    ev.severity = derived
        return evidence

    def _build_scores(self, evidence: list[LocusEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {locus: 0.0 for locus in LOCI}
        for ev in evidence:
            scores[ev.locus] = max(scores.get(ev.locus, 0.0), ev.score)
        return scores

    def _dominant_locus(
        self, locus_scores: dict[str, float]
    ) -> Literal["internal", "environmental", "interactional", "indeterminate"]:
        """Pick the dominant locus.

        Tie-breaking favors ``environmental`` over ``internal`` — the
        systematic bias to correct is over-attribution to "the model is
        bad" when the actual cause is fixable in scaffolding (cf. Ross
        1977 fundamental attribution error; Cemri et al. 2025 MAST
        finding that most multi-agent failures are system-design).
        """
        max_score = max(locus_scores.values(), default=0.0)
        if max_score < 0.2:
            return "indeterminate"
        ordered = ("environmental", "interactional", "internal")
        for locus in ordered:
            if locus_scores.get(locus, 0.0) >= max_score - 0.05:
                return locus  # type: ignore[return-value]
        return "indeterminate"

    def _attribution_quality(
        self, locus_scores: dict[str, float]
    ) -> Literal["well-attributed", "ambiguous", "miscalibrated"]:
        sorted_scores = sorted(locus_scores.values(), reverse=True)
        if not sorted_scores:
            return "miscalibrated"
        top = sorted_scores[0]
        second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        gap = top - second
        if top < 0.3:
            return "miscalibrated"
        if gap >= 0.3:
            return "well-attributed"
        return "ambiguous"

    def _check_initial_attribution(self, trace: AgentFailureTrace, dominant: str) -> bool | None:
        if not trace.initial_attribution:
            return None
        initial = trace.initial_attribution.strip().lower()
        if initial in LOCI:
            return initial == dominant
        if "model" in initial or "training" in initial or "rlhf" in initial:
            return dominant == "internal"
        if (
            "prompt" in initial
            or "context" in initial
            or "tool" in initial
            or "rag" in initial
            or "orchestrat" in initial
            or "scaffold" in initial
        ):
            return dominant == "environmental"
        if "both" in initial or "interaction" in initial:
            return dominant == "interactional"
        return None

    # ------------------------------------------------------------------
    # Composition + playbooks
    # ------------------------------------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentFailureTrace,
        dominant: str,
        interventions: list[LewinIntervention],
    ) -> ComposedPatternHandoff:
        provisional = LewinDetection(
            agent_id=trace.agent_id,
            dominant_locus=dominant,  # type: ignore[arg-type]
            locus_scores={locus: 0.0 for locus in LOCI},
            loci=[],
            interventions=interventions,
            attribution_quality="well-attributed",
            success=trace.success,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "dominant_locus": dominant,
            "framework": trace.framework,
            "intervention_types": [iv.intervention_type for iv in interventions],
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self,
        dominant: str,
        interventions: list[LewinIntervention],
        trace: AgentFailureTrace,
    ) -> list[AttachedPlaybook]:
        """Auto-attach playbooks based on (locus, factor) keys.

        For each intervention, try to derive the matching factor key from
        the intervention_type and the intervention's text. Also walk
        the input factors and attach a playbook if it matches the
        dominant locus.
        """
        attached: dict[tuple[str, str], AttachedPlaybook] = {}

        # Intervention-derived attachment via intervention_type → factor map.
        iv_type_to_factor: dict[str, str] = {
            "change_model": "base_model",
            "change_sampling": "sampling_config",
            "change_prompt": "system_prompt",
            "change_tools": "tools_available",
            "change_context": "rag_context",
            "change_rag_index": "rag_context",
            "change_orchestration": "orchestration",
            "change_topology": "orchestration",
            "change_memory": "memory_store",
            "add_verification_step": "verification_step",
            "change_safety_filter": "safety_filter",
        }
        for iv in interventions:
            factor = iv_type_to_factor.get(iv.intervention_type)
            if factor:
                pb = find_playbook(iv.target_locus, factor)
                if pb is not None and (pb.locus, pb.factor) not in attached:
                    attached[(pb.locus, pb.factor)] = pb

        # Factor-derived attachment: if the trace had an env factor that
        # matches an env-locus playbook, attach it.
        if dominant in {"internal", "interactional"}:
            for p_factor in trace.individual_factors:
                pb = find_playbook(dominant, p_factor.factor)
                if pb is not None and (pb.locus, pb.factor) not in attached:
                    attached[(pb.locus, pb.factor)] = pb
        if dominant in {"environmental", "interactional"}:
            for e_factor in trace.environmental_factors:
                pb = find_playbook(dominant, e_factor.factor)
                if pb is not None and (pb.locus, pb.factor) not in attached:
                    attached[(pb.locus, pb.factor)] = pb

        return list(attached.values())

    # ------------------------------------------------------------------
    # Trace serialization
    # ------------------------------------------------------------------

    def _serialize_trace(self, trace: AgentFailureTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Framework: {trace.framework or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            f"Run count observed: {trace.run_count}",
            "",
        ]
        step_lines: list[str] = []
        for i, step in enumerate(trace.steps):
            ts = (
                f"[{step.timestamp.isoformat()}] "
                if step.timestamp is not None
                else f"[step {i + 1}] "
            )
            step_lines.append(f"{ts}({step.type}) {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Failure trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


class LewinAttributionDetectorAsync:
    """Async mirror of :class:`LewinAttributionDetector`.

    Same constructor surface, same modes; uses an
    :class:`AsyncLLMClient` (e.g. ``AnthropicAsyncClient``) and exposes
    ``arun`` instead of ``run``.

    Implementation detail: the heavy synthesis logic
    (validation, parsing, deterministic synthesis, composition,
    playbooks) is reused via composition with a sync detector that
    wraps a tiny shim around the async client. This avoids duplicating
    400 LOC of pure-Python logic between the two classes.
    """

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: LewinMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: LewinMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentFailureTrace,
        *,
        mode: LewinMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> LewinDetection:
        active_mode: LewinMode = mode or self.mode

        # Run the synchronous detector against a tiny adapter that
        # turns the async ``complete`` into a sync ``complete`` by
        # running the awaitable to completion in the current loop or
        # a fresh one. For correctness we offload to a thread when an
        # existing loop is running.
        client: AsyncLLMClient = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))

        sync_detector = LewinAttributionDetector(
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
    """Wrap an async ``complete`` callable as a synchronous client.

    Used inside :class:`LewinAttributionDetectorAsync` so the heavy
    synthesis code in :class:`LewinAttributionDetector` can be reused
    without duplication. The async ``complete`` is run via
    ``asyncio.run`` in a fresh loop on a worker thread.
    """

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
    """Pull a JSON object out of an LLM response that may have fences/junk."""
    text = raw.strip()
    if not text:
        return None
    # Try whole string first.
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    # Try first { ... last } slice.
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


def _severity_rank(s: str) -> int:
    order = {
        "none": 0,
        "trace": 1,
        "low": 2,
        "moderate": 3,
        "medium": 4,
        "high": 5,
        "critical": 6,
    }
    return order.get(s, 0)


# ---------------------------------------------------------------------------
# Backward-compatible legacy log object (some tests import this).
# ---------------------------------------------------------------------------


_legacy_log = logging.getLogger("agentcity.lewin.generator")
_legacy_log.addHandler(logging.NullHandler())
