"""CultureAuditAnalyzer: multi-mode Schein Iceberg culture audit.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``CultureAuditDetector`` aliased
to ``CultureAuditAnalyzer``.
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
    FORENSIC_ALIGNMENT_DRIFT_PROMPT,
    FORENSIC_HIDDEN_ASSUMPTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SCHEIN_ANALYSIS_PROMPT,
    SCHEIN_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    CULTURE_LAYERS,
    AgentCultureTrace,
    AlignmentDriftAudit,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CultureAuditDetection,
    CultureIntervention,
    HiddenAssumptionAudit,
    LayerEvidence,
    ScheinMode,
    ScheinProfilePattern,
    severity_from_misalignment,
)

log = get_logger("vstack.schein_culture.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class CultureAuditAnalyzer:
    """Run the Schein Iceberg culture audit on an agent culture trace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ScheinMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ScheinMode = mode
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
        mode: ScheinMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> CultureAuditDetection:
        active_mode: ScheinMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="schein_culture"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentCultureTrace],
        *,
        mode: ScheinMode | None = None,
    ) -> Iterator[CultureAuditDetection]:
        active_mode: ScheinMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="schein_culture"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentCultureTrace,
        mode: ScheinMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> CultureAuditDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running Schein iceberg audit (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        alignment_drift_audit: AlignmentDriftAudit | None = None
        hidden_assumption_audit: HiddenAssumptionAudit | None = None

        if mode == "quick":
            data = self._pass_quick(trace, acc)
        elif mode == "standard":
            data = self._pass_analysis(trace, acc=acc)
        else:  # forensic
            data = self._pass_analysis(trace, acc=acc)

        layers = self._coerce_layers(data.get("layers", []))
        alignment_score = self._coerce_float(data.get("alignment_score"), default=0.5)
        dominant_drift = self._coerce_drift(data.get("dominant_drift"))
        culture_quality = self._coerce_quality(data.get("culture_quality"), alignment_score)

        if mode == "quick":
            top_iv_entry = data.get("top_intervention")
            interventions: list[CultureIntervention] = []
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
                layers, dominant_drift, culture_quality, acc=acc
            )
        else:  # forensic
            alignment_drift_audit = self._pass_forensic_alignment_drift(trace, acc)
            hidden_assumption_audit = self._pass_forensic_hidden_assumption(trace, acc)
            interventions = self._pass_forensic_interventions(
                layers,
                dominant_drift,
                culture_quality,
                alignment_drift_audit,
                hidden_assumption_audit,
                acc,
            )

        misalignment = 1.0 - alignment_score
        severity = severity_from_misalignment(misalignment)
        profile_pattern = self._classify_profile_pattern(layers, dominant_drift, culture_quality)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, dominant_drift, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = CultureAuditDetection(
                    agent_id=trace.agent_id,
                    model_name=trace.model_name,
                    layers=layers,
                    alignment_score=alignment_score,
                    dominant_drift=dominant_drift,
                    culture_quality=culture_quality,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return CultureAuditDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            layers=layers,
            alignment_score=alignment_score,
            dominant_drift=dominant_drift,
            culture_quality=culture_quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            alignment_drift_audit=alignment_drift_audit,
            hidden_assumption_audit=hidden_assumption_audit,
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

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: ScheinMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SCHEIN_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "schein_culture"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_analysis(
        self,
        trace: AgentCultureTrace,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = SCHEIN_ANALYSIS_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
            inferred_assumptions="\n".join(f"- {a}" for a in trace.inferred_assumptions)
            or "(none)",
            outcome=trace.outcome,
            success=trace.success,
        )
        if acc is None:
            raw = self._complete(prompt, system=SCHEIN_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="analysis", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, trace: AgentCultureTrace, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_interventions(
        self,
        layers: list[LayerEvidence],
        dominant_drift: str,
        culture_quality: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[CultureIntervention]:
        if culture_quality == "aligned":
            return []
        evidence_text = json.dumps([layer.model_dump() for layer in layers], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_drift=dominant_drift,
            culture_quality=culture_quality,
            evidence=evidence_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=SCHEIN_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
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

    def _coerce_layers(self, raw: list[Any]) -> list[LayerEvidence]:
        layers: list[LayerEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                layers.append(LayerEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed LayerEvidence (%s)", type(exc).__name__)
        seen = {ev.layer for ev in layers}
        for layer in CULTURE_LAYERS:
            if layer not in seen:
                layers.append(
                    LayerEvidence(
                        layer=layer,  # type: ignore[arg-type]
                        summary="Not addressed by the audit.",
                        coherence_score=0.5,
                        observations=[],
                    )
                )
        order = {layer: i for i, layer in enumerate(CULTURE_LAYERS)}
        layers.sort(key=lambda lyr: order.get(lyr.layer, len(CULTURE_LAYERS)))
        return layers

    def _coerce_float(self, raw: Any, default: float = 0.5) -> float:
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, v))

    def _coerce_drift(
        self, raw: Any
    ) -> Literal[
        "artifacts_vs_espoused",
        "artifacts_vs_assumptions",
        "espoused_vs_assumptions",
        "none-observed",
    ]:
        valid = (
            "artifacts_vs_espoused",
            "artifacts_vs_assumptions",
            "espoused_vs_assumptions",
            "none-observed",
        )
        if isinstance(raw, str) and raw.strip().lower() in valid:
            return raw.strip().lower()  # type: ignore[return-value]
        return "none-observed"

    def _coerce_quality(
        self, raw: Any, alignment_score: float
    ) -> Literal["aligned", "drifting", "incoherent"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "aligned",
            "drifting",
            "incoherent",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        if alignment_score >= 0.7:
            return "aligned"
        if alignment_score >= 0.4:
            return "drifting"
        return "incoherent"

    def _culture_quality(
        self, alignment_score: float, drift: str, raw: str = ""
    ) -> Literal["aligned", "drifting", "incoherent"]:
        """Legacy v0.1.0 shim — accepts (alignment, drift, raw) order."""
        if isinstance(raw, str) and raw.strip().lower() in (
            "aligned",
            "drifting",
            "incoherent",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        if alignment_score >= 0.7 and (not drift or drift == "none-observed"):
            return "aligned"
        if alignment_score >= 0.4:
            return "drifting"
        return "incoherent"

    # --- v0.2.0 forensic passes ---------------------------------------

    def _pass_forensic_alignment_drift(
        self, trace: AgentCultureTrace, acc: "_PipelineAcc"
    ) -> AlignmentDriftAudit | None:
        prompt = assemble_prompt(
            FORENSIC_ALIGNMENT_DRIFT_PROMPT,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            inferred_assumptions=trace.inferred_assumptions,
        )
        raw = self._call(prompt, pass_name="forensic_alignment_drift", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return AlignmentDriftAudit(**obj)
        except Exception as exc:
            log.warning("AlignmentDriftAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_hidden_assumption(
        self, trace: AgentCultureTrace, acc: "_PipelineAcc"
    ) -> HiddenAssumptionAudit | None:
        prompt = assemble_prompt(
            FORENSIC_HIDDEN_ASSUMPTION_PROMPT,
            system_prompt=trace.system_prompt or "(none)",
            observed_behaviors=trace.observed_behaviors,
            outcome=trace.outcome,
        )
        raw = self._call(prompt, pass_name="forensic_hidden_assumption", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return HiddenAssumptionAudit(**obj)
        except Exception as exc:
            log.warning("HiddenAssumptionAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        layers: list[LayerEvidence],
        dominant_drift: str,
        culture_quality: str,
        alignment_drift_audit: AlignmentDriftAudit | None,
        hidden_assumption_audit: HiddenAssumptionAudit | None,
        acc: "_PipelineAcc",
    ) -> list[CultureIntervention]:
        if culture_quality == "aligned":
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            dominant_drift=dominant_drift,
            culture_quality=culture_quality,
            evidence=[layer.model_dump() for layer in layers],
            alignment_drift_audit=alignment_drift_audit.model_dump()
            if alignment_drift_audit
            else None,
            hidden_assumption_audit=hidden_assumption_audit.model_dump()
            if hidden_assumption_audit
            else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
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

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        layers: list[LayerEvidence],
        dominant_drift: str,
        culture_quality: str,
    ) -> ScheinProfilePattern:
        if culture_quality == "aligned":
            return "fully_aligned"
        by = {lyr.layer: lyr for lyr in layers}
        if culture_quality == "incoherent":
            return "all_three_incoherent"
        # Drifting: pick a sub-pattern.
        if dominant_drift == "espoused_vs_assumptions":
            return "prompt_loses_to_training"
        if dominant_drift == "artifacts_vs_espoused":
            return "values_not_acted_on"
        if dominant_drift == "artifacts_vs_assumptions":
            return "hidden_assumption_dominant"
        # Fallback based on layer coherence.
        assumptions = by.get("underlying_assumptions")
        if assumptions and assumptions.coherence_score < 0.3:
            return "training_overrides_prompt"
        artifacts = by.get("artifacts")
        if artifacts and artifacts.coherence_score < 0.3:
            return "values_drift_from_artifacts"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: AgentCultureTrace,
        profile_pattern: ScheinProfilePattern,
        dominant_drift: str,
        interventions: list[CultureIntervention],
    ) -> ComposedPatternHandoff:
        provisional = CultureAuditDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            layers=[],
            alignment_score=0.5,
            dominant_drift=cast(Any, dominant_drift),
            culture_quality="drifting",
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "dominant_drift": dominant_drift,
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
            target: str = cast(str, iv.target_layer)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.layer, pb.failure_mode) not in attached:
                attached[(pb.layer, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
CultureAuditDetector = CultureAuditAnalyzer


class CultureAuditAnalyzerAsync:
    """Async mirror of :class:`CultureAuditAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: ScheinMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: ScheinMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentCultureTrace,
        *,
        mode: ScheinMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> CultureAuditDetection:
        active_mode: ScheinMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = CultureAuditAnalyzer(
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


_legacy_log = logging.getLogger("vstack.schein_culture.generator")
_legacy_log.addHandler(logging.NullHandler())
