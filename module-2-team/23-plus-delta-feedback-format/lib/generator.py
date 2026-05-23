"""PlusDeltaFeedbackAnalyzer: multi-mode plus/delta feedback generator.

Three pipeline modes (quick=1 call, standard=1 call generate, forensic=4 calls
generate+audits+interventions) with v0.2.0 production infrastructure.

This is a GENERATIVE pattern: standard mode produces the artifact in one
call (the artifact IS the output). Forensic mode adds specificity audit,
behavioral audit, and quality-improvement interventions.

Backward-compatible: ``PlusDeltaFeedbackGenerator`` aliased to
``PlusDeltaFeedbackAnalyzer``.
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
    FORENSIC_BEHAVIORAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SPECIFICITY_PROMPT,
    PLUS_DELTA_PROMPT,
    PLUS_DELTA_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    assemble_prompt,
)
from .schema import (
    AttachedPlaybook,
    BehavioralVsGenericAudit,
    Commitment,
    ComposedPatternHandoff,
    DeltaItem,
    FeedbackRequest,
    PlusDeltaFeedback,
    PlusDeltaIntervention,
    PlusDeltaMode,
    PlusDeltaProfilePattern,
    PlusItem,
    SpecificityAudit,
    severity_from_quality,
)

log = get_logger("agentcity.plus_delta.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class PlusDeltaFeedbackAnalyzer:
    """Generate a plus/delta feedback artifact from a FeedbackRequest."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: PlusDeltaMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: PlusDeltaMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        request: FeedbackRequest,
        *,
        mode: PlusDeltaMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> PlusDeltaFeedback:
        active_mode: PlusDeltaMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="plus_delta"):
            return self._run_pipeline(request, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        requests: Iterable[FeedbackRequest],
        *,
        mode: PlusDeltaMode | None = None,
    ) -> Iterator[PlusDeltaFeedback]:
        active_mode: PlusDeltaMode = mode or self.mode
        for request in requests:
            run_id = new_run_id()
            with run_context(run_id, pattern="plus_delta"):
                yield self._run_pipeline(request, active_mode, run_id, None)

    def _run_pipeline(
        self,
        request: FeedbackRequest,
        mode: PlusDeltaMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> PlusDeltaFeedback:
        self._validate_request(request)
        injection_detected = self._scan_injection(request)
        started = time.monotonic()
        log.info(
            "Generating plus/delta feedback (mode=%s) for %s -> %s",
            mode,
            request.reviewer_agent,
            request.subject_agent,
        )

        acc = _PipelineAcc()
        specificity_audit: SpecificityAudit | None = None
        behavioral_audit: BehavioralVsGenericAudit | None = None
        interventions: list[PlusDeltaIntervention] = []

        if mode == "quick":
            data = self._pass_quick(request, acc)
        elif mode == "standard":
            data = self._pass_generate(request, acc=acc)
        else:  # forensic
            data = self._pass_generate(request, acc=acc)

        plus_items = self._parse_plus_items(
            data.get("plus_items", []), request.max_items_per_category
        )
        delta_items = self._parse_delta_items(
            data.get("delta_items", []), request.max_items_per_category
        )
        commitments = self._parse_commitments(data.get("commitments", []))
        overall = self._coerce_overall(data.get("overall_assessment"), delta_items)
        quality = self._coerce_quality(data.get("feedback_quality_score"))

        if mode == "forensic":
            artifact_text = self._serialize_artifact(
                plus_items, delta_items, commitments, overall, quality
            )
            specificity_audit = self._pass_forensic_specificity(artifact_text, acc)
            behavioral_audit = self._pass_forensic_behavioral(artifact_text, acc)
            interventions = self._pass_forensic_interventions(
                artifact_text, specificity_audit, behavioral_audit, acc
            )

        severity = severity_from_quality(quality)
        profile_pattern = self._classify_profile_pattern(
            plus_items, delta_items, overall, quality, request.style
        )

        composition = (
            self._build_composition_handoff(request, profile_pattern, overall, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or request.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = PlusDeltaFeedback(
                    feedback_id=request.feedback_id,
                    reviewer_agent=request.reviewer_agent,
                    subject_agent=request.subject_agent,
                    task_context=request.task_context,
                    contribution_summary=request.contribution_summary,
                    plus_items=plus_items,
                    delta_items=delta_items,
                    commitments=commitments,
                    overall_assessment=overall,
                    feedback_quality_score=quality,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return PlusDeltaFeedback(
            feedback_id=request.feedback_id,
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            plus_items=plus_items,
            delta_items=delta_items,
            commitments=commitments,
            overall_assessment=overall,
            feedback_quality_score=quality,
            generator_model=self.model,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            specificity_audit=specificity_audit,
            behavioral_audit=behavioral_audit,
            interventions=interventions,
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

    def _validate_request(self, request: FeedbackRequest) -> None:
        if not request.reviewer_agent or not request.reviewer_agent.strip():
            raise ValueError("FeedbackRequest.reviewer_agent cannot be empty.")
        if not request.subject_agent or not request.subject_agent.strip():
            raise ValueError("FeedbackRequest.subject_agent cannot be empty.")
        if not request.task_context or not request.task_context.strip():
            raise ValueError("FeedbackRequest.task_context cannot be empty.")
        if not request.contribution_artifact or not request.contribution_artifact.strip():
            raise ValueError("FeedbackRequest.contribution_artifact cannot be empty.")

    def _scan_injection(self, request: FeedbackRequest) -> bool:
        targets: list[tuple[str, str]] = [
            ("task_context", request.task_context),
            ("contribution_summary", request.contribution_summary),
            ("contribution_artifact", request.contribution_artifact),
        ]
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in request",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: PlusDeltaMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=PLUS_DELTA_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "plus_delta"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_generate(
        self,
        request: FeedbackRequest,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = PLUS_DELTA_PROMPT.format(
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            success_criteria="\n".join(f"- {c}" for c in request.success_criteria)
            or "(none provided)",
            style=request.style,
            max_items=request.max_items_per_category,
            contribution_artifact=request.contribution_artifact,
        )
        if acc is None:
            raw = self._complete(prompt, system=PLUS_DELTA_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="generate", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, request: FeedbackRequest, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            style=request.style,
            max_items=request.max_items_per_category,
            contribution_artifact=request.contribution_artifact,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _parse_plus_items(self, raw: list[Any], cap: int) -> list[PlusItem]:
        items: list[PlusItem] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(PlusItem(**entry))
            except Exception as exc:
                log.warning("Dropping malformed PlusItem (%s)", type(exc).__name__)
            if len(items) >= cap:
                break
        return items

    def _parse_delta_items(self, raw: list[Any], cap: int) -> list[DeltaItem]:
        items: list[DeltaItem] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(DeltaItem(**entry))
            except Exception as exc:
                log.warning("Dropping malformed DeltaItem (%s)", type(exc).__name__)
            if len(items) >= cap:
                break
        return items

    def _parse_commitments(self, raw: list[Any]) -> list[Commitment]:
        items: list[Commitment] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(Commitment(**entry))
            except Exception as exc:
                log.warning("Dropping malformed Commitment (%s)", type(exc).__name__)
        return items

    def _coerce_overall(
        self, raw: Any, delta_items: list[DeltaItem]
    ) -> Literal["keep-going", "iterate", "rework"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "keep-going",
            "iterate",
            "rework",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        has_critical = any(d.severity == "critical" for d in delta_items)
        has_moderate = any(d.severity == "moderate" for d in delta_items)
        if has_critical:
            return "rework"
        if has_moderate:
            return "iterate"
        return "keep-going"

    def _coerce_quality(self, raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, value))

    # --- v0.2.0 forensic passes ---------------------------------------

    def _serialize_artifact(
        self,
        plus_items: list[PlusItem],
        delta_items: list[DeltaItem],
        commitments: list[Commitment],
        overall: str,
        quality: float,
    ) -> str:
        return json.dumps(
            {
                "plus_items": [p.model_dump() for p in plus_items],
                "delta_items": [d.model_dump() for d in delta_items],
                "commitments": [c.model_dump() for c in commitments],
                "overall_assessment": overall,
                "feedback_quality_score": quality,
            },
            indent=2,
            default=str,
        )

    def _pass_forensic_specificity(
        self, artifact_text: str, acc: "_PipelineAcc"
    ) -> SpecificityAudit | None:
        prompt = assemble_prompt(FORENSIC_SPECIFICITY_PROMPT, artifact=artifact_text)
        raw = self._call(prompt, pass_name="forensic_specificity", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return SpecificityAudit(**obj)
        except Exception as exc:
            log.warning("SpecificityAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_behavioral(
        self, artifact_text: str, acc: "_PipelineAcc"
    ) -> BehavioralVsGenericAudit | None:
        prompt = assemble_prompt(FORENSIC_BEHAVIORAL_PROMPT, artifact=artifact_text)
        raw = self._call(prompt, pass_name="forensic_behavioral", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return BehavioralVsGenericAudit(**obj)
        except Exception as exc:
            log.warning("BehavioralVsGenericAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        artifact_text: str,
        specificity_audit: SpecificityAudit | None,
        behavioral_audit: BehavioralVsGenericAudit | None,
        acc: "_PipelineAcc",
    ) -> list[PlusDeltaIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            artifact=artifact_text,
            specificity_audit=specificity_audit.model_dump() if specificity_audit else None,
            behavioral_audit=behavioral_audit.model_dump() if behavioral_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[PlusDeltaIntervention] = []
        for entry in data:
            try:
                interventions.append(PlusDeltaIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed PlusDeltaIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        plus_items: list[PlusItem],
        delta_items: list[DeltaItem],
        overall: str,
        quality: float,
        style: str,
    ) -> PlusDeltaProfilePattern:
        n_plus = len(plus_items)
        n_delta = len(delta_items)
        has_critical = any(d.severity == "critical" for d in delta_items)

        if quality < 0.4:
            return "generic_noise"

        n_plus_without_evidence = sum(1 for p in plus_items if not p.evidence.strip())
        n_delta_without_evidence = sum(1 for d in delta_items if not d.evidence.strip())
        if (n_plus_without_evidence + n_delta_without_evidence) >= max(1, (n_plus + n_delta) // 2):
            return "no_evidence_cited"

        n_delta_without_alt = sum(1 for d in delta_items if not d.alternative.strip())
        if n_delta > 0 and n_delta_without_alt == n_delta:
            return "no_alternatives_named"

        if has_critical and overall == "rework":
            return "critical_findings"
        if n_plus > 2 * max(1, n_delta) and style == "plus-leaning":
            return "plus_heavy_morale"
        if n_delta > 2 * max(1, n_plus) and style == "delta-leaning":
            return "delta_heavy_rework"
        if quality >= 0.7 and 1 <= n_plus and (n_delta >= 1 or overall == "keep-going"):
            return "balanced_specific"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        request: FeedbackRequest,
        profile_pattern: PlusDeltaProfilePattern,
        overall: str,
        interventions: list[PlusDeltaIntervention],
    ) -> ComposedPatternHandoff:
        provisional = PlusDeltaFeedback(
            feedback_id=request.feedback_id,
            reviewer_agent=request.reviewer_agent,
            subject_agent=request.subject_agent,
            task_context=request.task_context,
            contribution_summary=request.contribution_summary,
            overall_assessment=cast(Any, overall),
            feedback_quality_score=0.5,
            interventions=interventions,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, request)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "overall_assessment": overall,
            "framework": request.framework,
            "style": request.style,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self, interventions: list[PlusDeltaIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_dimension)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.dimension, pb.failure_mode) not in attached:
                attached[(pb.dimension, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
PlusDeltaFeedbackGenerator = PlusDeltaFeedbackAnalyzer


class PlusDeltaFeedbackAnalyzerAsync:
    """Async mirror of :class:`PlusDeltaFeedbackAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: PlusDeltaMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: PlusDeltaMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        request: FeedbackRequest,
        *,
        mode: PlusDeltaMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> PlusDeltaFeedback:
        active_mode: PlusDeltaMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = PlusDeltaFeedbackAnalyzer(
            llm_client=sync_shim,
            model=self.model,
            mode=active_mode,
            max_retries=self.max_retries,
            cost_per_1k_input=self.cost_per_1k_input,
            cost_per_1k_output=self.cost_per_1k_output,
            composition_enabled=self.composition_enabled,
            playbooks_enabled=self.playbooks_enabled,
        )
        return await asyncio.to_thread(
            sync_analyzer.run, request, mode=active_mode, baseline_path=baseline_path
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


_legacy_log = logging.getLogger("agentcity.plus_delta.generator")
_legacy_log.addHandler(logging.NullHandler())
