"""CultureProfileAnalyzer: multi-mode Robbins/Judge 7-Characteristics audit.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``CultureProfileDetector`` aliased
to ``CultureProfileAnalyzer``.
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
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PROVENANCE_PROMPT,
    FORENSIC_RISK_PROMPT,
    INTERVENTIONS_PROMPT,
    PROFILE_PROMPT,
    QUICK_PROFILE_PROMPT,
    ROBBINS_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    CULTURE_CHARACTERISTICS,
    AgentCultureTrace,
    AttachedPlaybook,
    CharacteristicScore,
    ComposedPatternHandoff,
    CultureIntervention,
    CultureProfileDetection,
    PerDimensionRisk,
    RobbinsMode,
    RobbinsProfilePattern,
    TargetProfileProvenance,
    severity_from_misfit,
)

log = get_logger("vstack.robbins_culture.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class CultureProfileAnalyzer:
    """Run the 7-Characteristics culture profile diagnostic."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: RobbinsMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: RobbinsMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentCultureTrace,
        *,
        mode: RobbinsMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> CultureProfileDetection:
        active_mode: RobbinsMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="robbins_culture"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentCultureTrace],
        *,
        mode: RobbinsMode | None = None,
    ) -> Iterator[CultureProfileDetection]:
        active_mode: RobbinsMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="robbins_culture"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentCultureTrace,
        mode: RobbinsMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> CultureProfileDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Robbins/Judge 7-Characteristics audit (mode=%s) for agent %s (task_class=%s)",
            mode,
            trace.agent_id or "<unknown>",
            trace.task_class,
        )

        acc = _PipelineAcc()
        provenance: TargetProfileProvenance | None = None
        per_dim_risk: PerDimensionRisk | None = None

        if mode == "quick":
            data = self._pass_quick(trace, acc)
        else:
            data = self._pass_profile(trace, acc=acc)

        characteristics = self._coerce_characteristics(data.get("characteristics", []))
        overall_fit = self._coerce_fraction(
            data.get("overall_fit"), default=self._compute_overall_fit(characteristics)
        )
        biggest_gap = self._coerce_gap(data.get("biggest_gap"), characteristics)
        fit_quality = self._fit_quality(
            overall_fit, str(data.get("fit_quality", "")).strip().lower()
        )

        if mode == "quick":
            interventions: list[CultureIntervention] = []
            top_iv_entry = data.get("top_intervention")
            if top_iv_entry:
                try:
                    interventions.append(CultureIntervention(**top_iv_entry))
                except Exception as exc:
                    log.warning(
                        "Quick top_intervention parse error: %s",
                        type(exc).__name__,
                    )
        elif mode == "standard":
            interventions = self._pass_interventions(
                trace, characteristics, biggest_gap, fit_quality, acc=acc
            )
        else:  # forensic
            provenance = self._pass_forensic_provenance(trace, acc)
            per_dim_risk = self._pass_forensic_risk(trace, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                characteristics,
                biggest_gap,
                fit_quality,
                provenance,
                per_dim_risk,
                acc,
            )

        misfit = 1.0 - overall_fit
        severity = severity_from_misfit(misfit)
        profile_pattern = self._classify_profile_pattern(characteristics, biggest_gap, fit_quality)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, biggest_gap, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = CultureProfileDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    task_class=trace.task_class,
                    characteristics=characteristics,
                    overall_fit=overall_fit,
                    fit_quality=fit_quality,
                    biggest_gap=biggest_gap,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return CultureProfileDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            characteristics=characteristics,
            overall_fit=overall_fit,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            target_profile_provenance=provenance,
            per_dimension_risk=per_dim_risk,
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

    # --- Validation + injection ---------------------------------------

    def _validate_trace(self, trace: AgentCultureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentCultureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentCultureTrace.outcome cannot be empty.")

    def _scan_injection(self, trace: AgentCultureTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("system_prompt", trace.system_prompt or ""),
        ]
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
        for i, a in enumerate(trace.inferred_assumptions):
            targets.append((f"inferred_assumptions[{i}]", a))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in culture trace",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    # --- LLM bookkeeping ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: RobbinsMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=ROBBINS_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "robbins_culture"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- LLM passes ---------------------------------------------------

    def _pass_profile(
        self,
        trace: AgentCultureTrace,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = PROFILE_PROMPT.format(
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
        )
        if acc is None:
            raw = self._complete(prompt, system=ROBBINS_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="profile", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, trace: AgentCultureTrace, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_PROFILE_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_interventions(
        self,
        trace: AgentCultureTrace,
        characteristics: list[CharacteristicScore],
        biggest_gap: str,
        fit_quality: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[CultureIntervention]:
        if fit_quality == "well-fit":
            return []
        evidence_text = json.dumps([c.model_dump() for c in characteristics], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            task_class=trace.task_class,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            evidence=evidence_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=ROBBINS_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_provenance(
        self, trace: AgentCultureTrace, acc: "_PipelineAcc"
    ) -> TargetProfileProvenance | None:
        prompt = assemble_prompt(
            FORENSIC_PROVENANCE_PROMPT,
            task_class=trace.task_class,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_provenance", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return TargetProfileProvenance(**obj)
        except Exception as exc:
            log.warning("TargetProfileProvenance parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_risk(
        self, trace: AgentCultureTrace, acc: "_PipelineAcc"
    ) -> PerDimensionRisk | None:
        prompt = assemble_prompt(
            FORENSIC_RISK_PROMPT,
            task_class=trace.task_class,
            outcome=trace.outcome,
            success=trace.success,
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_risk", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return PerDimensionRisk(**obj)
        except Exception as exc:
            log.warning("PerDimensionRisk parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentCultureTrace,
        characteristics: list[CharacteristicScore],
        biggest_gap: str,
        fit_quality: str,
        provenance: TargetProfileProvenance | None,
        per_dim_risk: PerDimensionRisk | None,
        acc: "_PipelineAcc",
    ) -> list[CultureIntervention]:
        if fit_quality == "well-fit":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            task_class=trace.task_class,
            fit_quality=fit_quality,
            biggest_gap=biggest_gap,
            provenance=provenance.model_dump() if provenance else None,
            per_dim_risk=per_dim_risk.model_dump() if per_dim_risk else None,
            evidence=[c.model_dump() for c in characteristics],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_interventions(self, raw: str) -> list[CultureIntervention]:
        data = extract_json_array(raw)
        interventions: list[CultureIntervention] = []
        for entry in data:
            try:
                interventions.append(CultureIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed CultureIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Coercion helpers ---------------------------------------------

    def _coerce_characteristics(self, raw: list[Any]) -> list[CharacteristicScore]:
        scores: list[CharacteristicScore] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                scores.append(CharacteristicScore(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed CharacteristicScore (%s)",
                    type(exc).__name__,
                )

        seen = {s.characteristic for s in scores}
        for c in CULTURE_CHARACTERISTICS:
            if c not in seen:
                scores.append(
                    CharacteristicScore(
                        characteristic=c,  # type: ignore[arg-type]
                        observed_score=0.5,
                        target_score=0.5,
                        fit_score=1.0,
                        explanation="No data observed; defaulting to neutral.",
                        evidence_quotes=[],
                    )
                )

        order = {c: i for i, c in enumerate(CULTURE_CHARACTERISTICS)}
        scores.sort(key=lambda s: order.get(s.characteristic, len(CULTURE_CHARACTERISTICS)))
        return scores

    def _compute_overall_fit(self, scores: list[CharacteristicScore]) -> float:
        if not scores:
            return 0.0
        return round(sum(s.fit_score for s in scores) / len(scores), 2)

    def _coerce_fraction(self, raw: Any, default: float = 0.0) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, value))

    def _coerce_gap(
        self, raw: Any, scores: list[CharacteristicScore]
    ) -> Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
        "none",
    ]:
        valid = set(CULTURE_CHARACTERISTICS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        if not scores:
            return "none"
        biggest = max(scores, key=lambda s: abs(s.observed_score - s.target_score))
        if abs(biggest.observed_score - biggest.target_score) < 0.1:
            return "none"
        return biggest.characteristic

    def _fit_quality(
        self, overall_fit: float, raw_quality: str
    ) -> Literal["well-fit", "partial-fit", "misfit"]:
        if raw_quality in ("well-fit", "partial-fit", "misfit"):
            return raw_quality  # type: ignore[return-value]
        if overall_fit >= 0.8:
            return "well-fit"
        if overall_fit >= 0.5:
            return "partial-fit"
        return "misfit"

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        characteristics: list[CharacteristicScore],
        biggest_gap: str,
        fit_quality: str,
    ) -> RobbinsProfilePattern:
        if fit_quality == "well-fit":
            return "well_fit"

        # Count moderate-or-larger misalignments
        misaligned = [c for c in characteristics if abs(c.observed_score - c.target_score) >= 0.25]
        if len(misaligned) >= 5:
            return "broadly_misfit"

        by: dict[str, CharacteristicScore] = {str(c.characteristic): c for c in characteristics}

        def under(name: str) -> bool:
            c = by.get(name)
            return bool(c and c.observed_score + 0.15 < c.target_score)

        def over(name: str) -> bool:
            c = by.get(name)
            return bool(c and c.observed_score - 0.15 > c.target_score)

        if biggest_gap == "innovation":
            return "innovation_starved" if under("innovation") else "innovation_excess"
        if biggest_gap == "attention_to_detail" and under("attention_to_detail"):
            return "detail_starved"
        if biggest_gap == "stability" and over("stability"):
            return "stability_excess"
        if biggest_gap == "team":
            return "team_starved" if under("team") else "team_excess"
        if biggest_gap == "aggressiveness" and over("aggressiveness"):
            return "aggressiveness_excess"
        if biggest_gap == "people" and under("people"):
            return "people_starved"
        if biggest_gap == "outcome" and under("outcome"):
            return "outcome_starved"

        # Fallbacks based on under/over patterns
        if under("innovation"):
            return "innovation_starved"
        if under("attention_to_detail"):
            return "detail_starved"
        if over("stability"):
            return "stability_excess"
        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentCultureTrace,
        profile_pattern: RobbinsProfilePattern,
        biggest_gap: str,
        interventions: list[CultureIntervention],
    ) -> ComposedPatternHandoff:
        provisional = CultureProfileDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            characteristics=[],
            overall_fit=0.5,
            fit_quality="partial-fit",
            biggest_gap=cast(Any, biggest_gap),
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "task_class": trace.task_class,
            "biggest_gap": biggest_gap,
            "framework": trace.framework,
            "model_name": trace.model_name,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[CultureIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_characteristic)
            pb = find_playbook_for_intervention(target, iv.intervention_type, iv.direction)
            if pb is not None and (pb.characteristic, pb.failure_mode) not in attached:
                attached[(pb.characteristic, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
CultureProfileDetector = CultureProfileAnalyzer


class CultureProfileAnalyzerAsync:
    """Async mirror of :class:`CultureProfileAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: RobbinsMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: RobbinsMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentCultureTrace,
        *,
        mode: RobbinsMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> CultureProfileDetection:
        active_mode: RobbinsMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = CultureProfileAnalyzer(
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

    def add(
        self,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        elapsed_ms: float,
    ) -> None:
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


_legacy_log = logging.getLogger("vstack.robbins_culture.generator")
_legacy_log.addHandler(logging.NullHandler())


__all__ = [
    "AsyncLLMClient",
    "CultureProfileAnalyzer",
    "CultureProfileAnalyzerAsync",
    "CultureProfileDetector",
    "LLMClient",
]
