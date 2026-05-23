"""SMARTGoalAnalyzer: multi-mode Doran SMART goal generator.

Three pipeline modes (quick=1 call, standard=1 call generate, forensic=4 calls)
with v0.2.0 production infrastructure.

Backward-compatible: ``SMARTGoalGenerator`` aliased to
``SMARTGoalAnalyzer``.
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
    FORENSIC_CRITERIA_COMPLETENESS_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_MEASUREMENT_RIGOR_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SMART_GENERATION_PROMPT,
    SMART_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    SMART_CRITERIA,
    AttachedPlaybook,
    ComposedPatternHandoff,
    CriteriaCompletenessAudit,
    GoalRequest,
    KillCriterion,
    MeasurementRigorAudit,
    SMARTCriterion,
    SMARTGoal,
    SmartGoalIntervention,
    SmartGoalMode,
    SmartGoalProfilePattern,
    SuccessMetric,
    severity_from_smart_score,
)

log = get_logger("agentcity.smart_goal.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class SMARTGoalAnalyzer:
    """Generate a SMART goal spec from a vague task description."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SmartGoalMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SmartGoalMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        request: GoalRequest,
        *,
        mode: SmartGoalMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SMARTGoal:
        active_mode: SmartGoalMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="smart_goal"):
            return self._run_pipeline(request, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        requests: Iterable[GoalRequest],
        *,
        mode: SmartGoalMode | None = None,
    ) -> Iterator[SMARTGoal]:
        active_mode: SmartGoalMode = mode or self.mode
        for request in requests:
            run_id = new_run_id()
            with run_context(run_id, pattern="smart_goal"):
                yield self._run_pipeline(request, active_mode, run_id, None)

    def _run_pipeline(
        self,
        request: GoalRequest,
        mode: SmartGoalMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> SMARTGoal:
        self._validate_request(request)
        injection_detected = self._scan_injection(request)
        started = time.monotonic()
        log.info(
            "Generating SMART goal (mode=%s) for goal_id=%s",
            mode,
            request.goal_id or "<unknown>",
        )

        acc = _PipelineAcc()
        criteria_audit: CriteriaCompletenessAudit | None = None
        rigor_audit: MeasurementRigorAudit | None = None
        interventions: list[SmartGoalIntervention] = []

        if mode == "quick":
            data = self._pass_quick(request, acc)
        elif mode == "standard":
            data = self._pass_generate(request, acc=acc)
        else:  # forensic
            data = self._pass_generate(request, acc=acc)

        criteria = self._parse_criteria(data.get("criteria", []))
        success_metrics = self._parse_success_metrics(data.get("success_metrics", []))
        kill_criteria = self._parse_kill_criteria(data.get("kill_criteria", []))
        open_questions = [str(q) for q in data.get("open_questions", []) if isinstance(q, str)]
        completion_criteria = [
            str(c) for c in data.get("completion_criteria", []) if isinstance(c, str)
        ]
        smart_statement = str(data.get("smart_statement", "")).strip() or request.vague_goal
        deadline = str(data.get("deadline", "")).strip() or "(not specified)"
        overall_score = self._coerce_score(data.get("overall_smart_score"))
        if overall_score is None:
            overall_score = self._compute_score_from_criteria(criteria)
        smart_quality = self._reconcile_quality(data.get("smart_quality"), overall_score)

        if mode == "forensic":
            goal_text = self._serialize_goal(
                smart_statement,
                criteria,
                completion_criteria,
                success_metrics,
                kill_criteria,
                deadline,
                overall_score,
                smart_quality,
            )
            criteria_audit = self._pass_forensic_criteria(goal_text, acc)
            rigor_audit = self._pass_forensic_rigor(goal_text, acc)
            interventions = self._pass_forensic_interventions(
                goal_text, criteria_audit, rigor_audit, acc
            )

        severity = severity_from_smart_score(overall_score)
        profile_pattern = self._classify_profile_pattern(
            criteria, success_metrics, kill_criteria, deadline, overall_score
        )

        composition = (
            self._build_composition_handoff(request, profile_pattern, overall_score, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or request.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = SMARTGoal(
                    goal_id=request.goal_id,
                    original_goal=request.vague_goal,
                    smart_statement=smart_statement,
                    criteria=criteria,
                    completion_criteria=completion_criteria,
                    success_metrics=success_metrics,
                    kill_criteria=kill_criteria,
                    deadline=deadline,
                    open_questions=open_questions,
                    overall_smart_score=overall_score,
                    smart_quality=smart_quality,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return SMARTGoal(
            goal_id=request.goal_id,
            original_goal=request.vague_goal,
            smart_statement=smart_statement,
            criteria=criteria,
            completion_criteria=completion_criteria,
            success_metrics=success_metrics,
            kill_criteria=kill_criteria,
            deadline=deadline,
            open_questions=open_questions,
            overall_smart_score=overall_score,
            smart_quality=smart_quality,
            generator_model=self.model,
            framework=request.framework,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            criteria_audit=criteria_audit,
            rigor_audit=rigor_audit,
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

    def _validate_request(self, request: GoalRequest) -> None:
        if not request.vague_goal or not request.vague_goal.strip():
            raise ValueError("GoalRequest.vague_goal cannot be empty.")

    def _scan_injection(self, request: GoalRequest) -> bool:
        targets: list[tuple[str, str]] = [
            ("vague_goal", request.vague_goal),
            ("context", request.context or ""),
        ]
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in goal request",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: SmartGoalMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SMART_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "smart_goal"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_generate(
        self, request: GoalRequest, *, acc: "_PipelineAcc | None" = None
    ) -> dict[str, Any]:
        prompt = SMART_GENERATION_PROMPT.format(
            vague_goal=request.vague_goal,
            context=request.context or "(none)",
            available_resources=", ".join(request.available_resources) or "(unspecified)",
            known_constraints=", ".join(request.known_constraints) or "(unspecified)",
            deadline_hint=request.deadline_hint or "(none)",
            framework=request.framework or "(none)",
        )
        if acc is None:
            raw = self._complete(prompt, system=SMART_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="generate", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, request: GoalRequest, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            vague_goal=request.vague_goal,
            context=request.context or "(none)",
            deadline_hint=request.deadline_hint or "(none)",
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _parse_criteria(self, raw: list[Any]) -> list[SMARTCriterion]:
        criteria: list[SMARTCriterion] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                criteria.append(SMARTCriterion(**entry))
            except Exception as exc:
                log.warning("Dropping malformed SMARTCriterion (%s)", type(exc).__name__)
        seen = {c.criterion for c in criteria}
        for name in SMART_CRITERIA:
            if name not in seen:
                criteria.append(
                    SMARTCriterion(
                        criterion=name,  # type: ignore[arg-type]
                        statement="Not addressed by the generator.",
                        quality_score=0.0,
                    )
                )
        order = {name: i for i, name in enumerate(SMART_CRITERIA)}
        criteria.sort(key=lambda c: order.get(c.criterion, len(SMART_CRITERIA)))
        return criteria

    def _parse_success_metrics(self, raw: list[Any]) -> list[SuccessMetric]:
        metrics: list[SuccessMetric] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                metrics.append(SuccessMetric(**entry))
            except Exception as exc:
                log.warning("Dropping malformed SuccessMetric (%s)", type(exc).__name__)
        return metrics

    def _parse_kill_criteria(self, raw: list[Any]) -> list[KillCriterion]:
        kills: list[KillCriterion] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                kills.append(KillCriterion(**entry))
            except Exception as exc:
                log.warning("Dropping malformed KillCriterion (%s)", type(exc).__name__)
        return kills

    def _coerce_score(self, raw: Any) -> float | None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, value))

    def _compute_score_from_criteria(self, criteria: list[SMARTCriterion]) -> float:
        if not criteria:
            return 0.0
        return round(sum(c.quality_score for c in criteria) / len(criteria), 2)

    def _reconcile_quality(
        self, raw: Any, overall_score: float
    ) -> Literal["strong", "acceptable", "weak"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "strong",
            "acceptable",
            "weak",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        if overall_score >= 0.8:
            return "strong"
        if overall_score >= 0.5:
            return "acceptable"
        return "weak"

    # --- v0.2.0 forensic passes ---------------------------------------

    def _serialize_goal(
        self,
        smart_statement: str,
        criteria: list[SMARTCriterion],
        completion_criteria: list[str],
        success_metrics: list[SuccessMetric],
        kill_criteria: list[KillCriterion],
        deadline: str,
        overall_score: float,
        smart_quality: str,
    ) -> str:
        return json.dumps(
            {
                "smart_statement": smart_statement,
                "criteria": [c.model_dump() for c in criteria],
                "completion_criteria": completion_criteria,
                "success_metrics": [m.model_dump() for m in success_metrics],
                "kill_criteria": [k.model_dump() for k in kill_criteria],
                "deadline": deadline,
                "overall_smart_score": overall_score,
                "smart_quality": smart_quality,
            },
            indent=2,
            default=str,
        )

    def _pass_forensic_criteria(
        self, goal_text: str, acc: "_PipelineAcc"
    ) -> CriteriaCompletenessAudit | None:
        prompt = assemble_prompt(FORENSIC_CRITERIA_COMPLETENESS_PROMPT, goal=goal_text)
        raw = self._call(prompt, pass_name="forensic_criteria", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CriteriaCompletenessAudit(**obj)
        except Exception as exc:
            log.warning("CriteriaCompletenessAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_rigor(
        self, goal_text: str, acc: "_PipelineAcc"
    ) -> MeasurementRigorAudit | None:
        prompt = assemble_prompt(FORENSIC_MEASUREMENT_RIGOR_PROMPT, goal=goal_text)
        raw = self._call(prompt, pass_name="forensic_rigor", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return MeasurementRigorAudit(**obj)
        except Exception as exc:
            log.warning("MeasurementRigorAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        goal_text: str,
        criteria_audit: CriteriaCompletenessAudit | None,
        rigor_audit: MeasurementRigorAudit | None,
        acc: "_PipelineAcc",
    ) -> list[SmartGoalIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            goal=goal_text,
            criteria_audit=criteria_audit.model_dump() if criteria_audit else None,
            rigor_audit=rigor_audit.model_dump() if rigor_audit else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[SmartGoalIntervention] = []
        for entry in data:
            try:
                interventions.append(SmartGoalIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SmartGoalIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self,
        criteria: list[SMARTCriterion],
        success_metrics: list[SuccessMetric],
        kill_criteria: list[KillCriterion],
        deadline: str,
        overall_score: float,
    ) -> SmartGoalProfilePattern:
        by_name = {c.criterion: c.quality_score for c in criteria}
        if overall_score >= 0.8:
            return "strong_smart_goal"
        if by_name.get("specific", 0.0) < 0.4:
            return "vague_unspecific"
        if by_name.get("measurable", 0.0) < 0.4 or not success_metrics:
            return "unmeasurable"
        if by_name.get("achievable", 0.0) < 0.4:
            return "unachievable_stretch"
        if by_name.get("relevant", 0.0) < 0.4:
            return "irrelevant_to_context"
        if by_name.get("time_bound", 0.0) < 0.4 or deadline.strip().lower() in (
            "(not specified)",
            "",
            "asap",
        ):
            return "no_deadline"
        if not kill_criteria:
            return "missing_kill_criteria"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        request: GoalRequest,
        profile_pattern: SmartGoalProfilePattern,
        overall_score: float,
        interventions: list[SmartGoalIntervention],
    ) -> ComposedPatternHandoff:
        provisional = SMARTGoal(
            goal_id=request.goal_id,
            original_goal=request.vague_goal,
            smart_statement=request.vague_goal,
            criteria=[],
            completion_criteria=[],
            success_metrics=[],
            kill_criteria=[],
            deadline="",
            overall_smart_score=overall_score,
            smart_quality="acceptable",
            framework=request.framework,
            profile_pattern=profile_pattern,
            interventions=interventions,
        )
        downstream, rationale = recommended_downstream(provisional, request)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "overall_smart_score": overall_score,
            "framework": request.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self, interventions: list[SmartGoalIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_criterion)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.criterion, pb.failure_mode) not in attached:
                attached[(pb.criterion, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
SMARTGoalGenerator = SMARTGoalAnalyzer


class SMARTGoalAnalyzerAsync:
    """Async mirror of :class:`SMARTGoalAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: SmartGoalMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: SmartGoalMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        request: GoalRequest,
        *,
        mode: SmartGoalMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> SMARTGoal:
        active_mode: SmartGoalMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = SMARTGoalAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.smart_goal.generator")
_legacy_log.addHandler(logging.NullHandler())
