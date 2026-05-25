"""SDTRewardAnalyzer: multi-mode Deci & Ryan SDT diagnostic.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``SDTRewardDetector`` remains exported as an
alias for ``SDTRewardAnalyzer``.
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
    FORENSIC_OVERJUSTIFICATION_PROMPT,
    FORENSIC_REWARD_SHAPING_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SDT_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_NEEDS_PROMPT,
    assemble_prompt,
)
from .schema import (
    SDT_NEEDS,
    AgentSDTTrace,
    AttachedPlaybook,
    ComposedPatternHandoff,
    NeedScore,
    OverjustificationAudit,
    RewardShapingItem,
    SDTDetection,
    SDTIntervention,
    SDTMode,
    SDTNeed,
    SDTNeedOrNone,
    SDTProfilePattern,
    severity_from_undermining,
)

log = get_logger("vstack.sdt_reward.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class SDTRewardAnalyzer:
    """Run the SDT Intrinsic Reward diagnostic on an AgentSDTTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SDTMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SDTMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: AgentSDTTrace,
        *,
        mode: SDTMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SDTDetection:
        active_mode: SDTMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="sdt_reward"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentSDTTrace],
        *,
        mode: SDTMode | None = None,
    ) -> Iterator[SDTDetection]:
        active_mode: SDTMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="sdt_reward"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: AgentSDTTrace,
        mode: SDTMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> SDTDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        started = time.monotonic()
        log.info(
            "Running SDT diagnostic (mode=%s) for agent %s",
            mode,
            trace.agent_id or "<unknown>",
        )

        acc = _PipelineAcc()
        reward_items: list[RewardShapingItem] = []
        overjustification: OverjustificationAudit | None = None

        if mode == "quick":
            evidence, intrinsic_score, quality, undermined, top_iv = self._pass_quick(trace, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            evidence, intrinsic_score, quality, undermined = self._pass_standard_needs(trace, acc)
            interventions = self._pass_standard_interventions(
                trace, evidence, undermined, quality, acc
            )
        elif mode == "forensic":
            evidence, intrinsic_score, quality, undermined = self._pass_standard_needs(trace, acc)
            reward_items = self._pass_forensic_reward_shaping(trace, acc)
            overjustification = self._pass_forensic_overjustification(
                trace, reward_items, evidence, acc
            )
            interventions = self._pass_forensic_interventions(
                trace,
                evidence,
                undermined,
                quality,
                reward_items,
                overjustification,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown SDTMode: {mode!r}")

        profile_pattern = self._classify_profile_pattern(
            evidence, undermined, quality, reward_items, overjustification, trace
        )
        severity = severity_from_undermining(intrinsic_score, quality)

        composition = (
            self._build_composition_handoff(trace, undermined, profile_pattern, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = SDTDetection(
                    task_class=trace.task_class,
                    need_evidence=evidence,
                    intrinsic_motivation_score=intrinsic_score,
                    motivation_quality=quality,
                    most_undermined_need=undermined,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        detection = SDTDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            task_class=trace.task_class,
            need_evidence=evidence,
            intrinsic_motivation_score=intrinsic_score,
            motivation_quality=quality,
            most_undermined_need=undermined,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            reward_shaping_items=reward_items,
            overjustification_audit=overjustification,
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

        log.info(
            "SDT done mode=%s intrinsic=%.2f quality=%s undermined=%s profile=%s elapsed=%.0fms",
            mode,
            intrinsic_score,
            quality,
            undermined,
            profile_pattern,
            elapsed_ms,
        )
        return detection

    # --- Validation ----------------------------------------------------

    def _validate_trace(self, trace: AgentSDTTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentSDTTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentSDTTrace.outcome cannot be empty.")
        # Need at least one of system_prompt / extrinsic_signals /
        # observed_behaviors to diagnose reward shaping.
        if not trace.system_prompt and not trace.extrinsic_signals and not trace.observed_behaviors:
            raise ValueError(
                "AgentSDTTrace must include at least one of system_prompt, "
                "extrinsic_signals, or observed_behaviors."
            )

    def _scan_injection(self, trace: AgentSDTTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("task", trace.task),
            ("outcome", trace.outcome),
            ("system_prompt", trace.system_prompt),
        ]
        for i, s in enumerate(trace.extrinsic_signals):
            targets.append((f"extrinsic_signals[{i}]", s))
        for i, b in enumerate(trace.observed_behaviors):
            targets.append((f"observed_behaviors[{i}]", b))
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
        if hit_count:
            log.warning("injection scan: %d field(s) flagged", hit_count)
        return hit_count > 0

    # --- LLM call helper ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: SDTMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SDT_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "sdt_reward"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(
        self, trace: AgentSDTTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[NeedScore],
        float,
        Literal["intrinsic", "mixed", "controlled"],
        SDTNeedOrNone,
        SDTIntervention | None,
    ]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt or "(none)",
            extrinsic_signals=trace.extrinsic_signals,
            observed_behaviors=trace.observed_behaviors,
            outcome=trace.outcome,
            success=trace.success,
            user_purpose=trace.user_purpose,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("need_evidence", []))
        intrinsic_score = self._coerce_intrinsic(obj.get("intrinsic_motivation_score"), evidence)
        quality = self._coerce_quality(obj.get("motivation_quality"), evidence, intrinsic_score)
        undermined = self._coerce_undermined(obj.get("most_undermined_need"), evidence)
        top_iv: SDTIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = SDTIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return evidence, intrinsic_score, quality, undermined, top_iv

    def _pass_standard_needs(
        self, trace: AgentSDTTrace, acc: "_PipelineAcc"
    ) -> tuple[
        list[NeedScore],
        float,
        Literal["intrinsic", "mixed", "controlled"],
        SDTNeedOrNone,
    ]:
        prompt = assemble_prompt(
            STANDARD_NEEDS_PROMPT,
            task=trace.task,
            task_class=trace.task_class,
            model_name=trace.model_name or "unspecified",
            system_prompt=trace.system_prompt or "(none)",
            extrinsic_signals=trace.extrinsic_signals,
            observed_behaviors=trace.observed_behaviors,
            outcome=trace.outcome,
            success=trace.success,
            user_purpose=trace.user_purpose,
        )
        raw = self._call(prompt, pass_name="standard_needs", mode="standard", acc=acc)
        obj = _try_json_object(raw) or {}
        evidence = self._parse_evidence(obj.get("need_evidence", []))
        intrinsic_score = self._coerce_intrinsic(obj.get("intrinsic_motivation_score"), evidence)
        quality = self._coerce_quality(obj.get("motivation_quality"), evidence, intrinsic_score)
        undermined = self._coerce_undermined(obj.get("most_undermined_need"), evidence)
        return evidence, intrinsic_score, quality, undermined

    def _pass_standard_interventions(
        self,
        trace: AgentSDTTrace,
        evidence: list[NeedScore],
        undermined: SDTNeedOrNone,
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[SDTIntervention]:
        if undermined == "none" and quality == "intrinsic":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            most_undermined_need=undermined,
            motivation_quality=quality,
            task_class=trace.task_class,
            evidence=[ev.model_dump() for ev in evidence],
        )
        raw = self._call(prompt, pass_name="standard_interventions", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_forensic_reward_shaping(
        self, trace: AgentSDTTrace, acc: "_PipelineAcc"
    ) -> list[RewardShapingItem]:
        prompt = assemble_prompt(
            FORENSIC_REWARD_SHAPING_PROMPT,
            system_prompt=trace.system_prompt or "(none)",
            extrinsic_signals=trace.extrinsic_signals,
        )
        raw = self._call(prompt, pass_name="forensic_reward_shaping", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        items: list[RewardShapingItem] = []
        for entry in data:
            try:
                items.append(RewardShapingItem(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RewardShapingItem (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return items

    def _pass_forensic_overjustification(
        self,
        trace: AgentSDTTrace,
        reward_items: list[RewardShapingItem],
        evidence: list[NeedScore],
        acc: "_PipelineAcc",
    ) -> OverjustificationAudit | None:
        prompt = assemble_prompt(
            FORENSIC_OVERJUSTIFICATION_PROMPT,
            reward_shaping_items=[ri.model_dump() for ri in reward_items],
            evidence=[ev.model_dump() for ev in evidence],
            observed_behaviors=trace.observed_behaviors,
        )
        raw = self._call(prompt, pass_name="forensic_overjustification", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return OverjustificationAudit(**obj)
        except Exception as exc:
            log.warning("OverjustificationAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentSDTTrace,
        evidence: list[NeedScore],
        undermined: SDTNeedOrNone,
        quality: str,
        reward_items: list[RewardShapingItem],
        overjustification: OverjustificationAudit | None,
        acc: "_PipelineAcc",
    ) -> list[SDTIntervention]:
        provisional_profile = self._classify_profile_pattern(
            evidence, undermined, quality, reward_items, overjustification, trace
        )
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            most_undermined_need=undermined,
            profile_pattern=provisional_profile,
            motivation_quality=quality,
            task_class=trace.task_class,
            reward_shaping_items=[ri.model_dump() for ri in reward_items],
            overjustification=overjustification.model_dump() if overjustification else None,
            evidence=[ev.model_dump() for ev in evidence],
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    # --- Parsers + coercers -------------------------------------------

    def _parse_evidence(self, raw: Any) -> list[NeedScore]:
        evidence: list[NeedScore] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    evidence.append(NeedScore(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed NeedScore (%s): %r",
                        type(exc).__name__,
                        entry,
                    )

        seen = {ev.need for ev in evidence}
        for n in SDT_NEEDS:
            if n not in seen:
                evidence.append(
                    NeedScore(
                        need=n,  # type: ignore[arg-type]
                        score=0.5,
                        explanation="No evidence observed for this need.",
                        evidence_quotes=[],
                        confidence=0.5,
                    )
                )
        order = {n: i for i, n in enumerate(SDT_NEEDS)}
        evidence.sort(key=lambda ev: order.get(ev.need, len(SDT_NEEDS)))
        return evidence

    def _parse_interventions(self, raw: str) -> list[SDTIntervention]:
        data = extract_json_array(raw)
        interventions: list[SDTIntervention] = []
        for entry in data:
            try:
                interventions.append(SDTIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SDTIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    def _coerce_intrinsic(self, raw: Any, evidence: list[NeedScore]) -> float:
        try:
            value = float(raw)
            return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass
        if not evidence:
            return 0.0
        mean = sum(ev.score for ev in evidence) / len(evidence)
        return round(max(0.0, min(1.0, mean)), 2)

    def _coerce_quality(
        self,
        raw: Any,
        evidence: list[NeedScore],
        intrinsic_score: float,
    ) -> Literal["intrinsic", "mixed", "controlled"]:
        if isinstance(raw, str) and raw.strip() in (
            "intrinsic",
            "mixed",
            "controlled",
        ):
            return cast(Literal["intrinsic", "mixed", "controlled"], raw.strip())
        # Derive: all >= 0.7 -> intrinsic; mean < 0.4 -> controlled.
        if all(ev.score >= 0.7 for ev in evidence):
            return "intrinsic"
        if intrinsic_score < 0.4:
            return "controlled"
        return "mixed"

    def _motivation_quality(
        self, score: float, raw: str
    ) -> Literal["intrinsic", "mixed", "controlled"]:
        """v0.0.x compat: derive quality from a single intrinsic score."""
        if isinstance(raw, str) and raw.strip() in (
            "intrinsic",
            "mixed",
            "controlled",
        ):
            return cast(Literal["intrinsic", "mixed", "controlled"], raw.strip())
        s = max(0.0, min(1.0, float(score)))
        if s >= 0.7:
            return "intrinsic"
        if s >= 0.4:
            return "mixed"
        return "controlled"

    def _coerce_undermined(self, raw: Any, evidence: list[NeedScore]) -> SDTNeedOrNone:
        valid = set(SDT_NEEDS) | {"none"}
        if isinstance(raw, str) and raw.strip() in valid:
            return cast(SDTNeedOrNone, raw.strip())
        if not evidence:
            return "none"
        bottom = min(evidence, key=lambda ev: ev.score)
        if bottom.score >= 0.7:
            return "none"
        return cast(SDTNeedOrNone, bottom.need)

    # --- Profile classifier -------------------------------------------

    def _classify_profile_pattern(
        self,
        evidence: list[NeedScore],
        undermined: SDTNeedOrNone,
        quality: str,
        reward_items: list[RewardShapingItem],
        overjustification: OverjustificationAudit | None,
        trace: AgentSDTTrace,
    ) -> SDTProfilePattern:
        scores: dict[str, float] = {str(ev.need): ev.score for ev in evidence}
        a = scores.get("autonomy", 0.5)
        c = scores.get("competence", 0.5)

        # Overjustification active overrides per-need patterns.
        if overjustification and overjustification.is_active:
            return "overjustification_active"

        # Multi-need undermined.
        n_low = sum(1 for v in scores.values() if v < 0.4)
        if n_low >= 2:
            if quality == "controlled":
                return "controlled_motivation_dominant"
            return "multi_need_undermined"

        # Task-class-specific.
        if trace.task_class == "regulated_workflow" and undermined == "autonomy" and a >= 0.3:
            return "regulated_workflow_low_autonomy_acceptable"
        if trace.task_class == "creative_generation" and undermined == "autonomy":
            return "creative_task_low_autonomy_misfit"

        # Reward-shaping-specific.
        if reward_items:
            has_deadline = any(
                ri.category == "deadline_pressure" and ri.polarity == "extrinsic_controlling"
                for ri in reward_items
            )
            has_rule = any(
                ri.category == "rule_imposition" and ri.polarity == "extrinsic_controlling"
                for ri in reward_items
            )
            if undermined == "competence" and has_deadline:
                return "competence_collapse_under_deadline"
            if undermined == "autonomy" and has_rule:
                return "autonomy_collapse_under_rule_imposition"

        # Per-undermined patterns.
        mapping: dict[str, SDTProfilePattern] = {
            "autonomy": "autonomy_undermined_dominant",
            "competence": "competence_undermined_dominant",
            "relatedness": "relatedness_undermined_dominant",
        }
        if undermined in mapping:
            return mapping[undermined]

        if quality == "intrinsic" or (a >= 0.7 and c >= 0.7):
            return "intrinsic_balanced"
        return "indeterminate"

    # --- Composition + playbooks --------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentSDTTrace,
        undermined: SDTNeedOrNone,
        profile_pattern: SDTProfilePattern,
        interventions: list[SDTIntervention],
    ) -> ComposedPatternHandoff:
        provisional = SDTDetection(
            task_class=trace.task_class,
            need_evidence=[],
            intrinsic_motivation_score=0.5,
            motivation_quality="mixed",
            most_undermined_need=undermined,
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "most_undermined_need": undermined,
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

    def _attach_playbooks(self, interventions: list[SDTIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_need)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.need, pb.failure_mode) not in attached:
                attached[(pb.need, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
SDTRewardDetector = SDTRewardAnalyzer


class SDTRewardAnalyzerAsync:
    """Async mirror of :class:`SDTRewardAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SDTMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SDTMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentSDTTrace,
        *,
        mode: SDTMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SDTDetection:
        active_mode: SDTMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = SDTRewardAnalyzer(
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


_legacy_log = logging.getLogger("vstack.sdt_reward.generator")
_legacy_log.addHandler(logging.NullHandler())

_PUBLIC_REEXPORTS: tuple[object, ...] = (SDTNeed,)
