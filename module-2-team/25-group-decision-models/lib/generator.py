"""DecisionProtocolAnalyzer: multi-mode group-decision protocol generator.

Three pipeline modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Optional local tally via tally.tally_votes runs after
the LLM picks the method.

Backward-compatible: ``DecisionProtocolGenerator`` aliased to
``DecisionProtocolAnalyzer``.
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
    DECISION_PROTOCOL_PROMPT,
    DECISION_SYSTEM_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_METHOD_FIT_PROMPT,
    FORENSIC_TALLY_INTEGRITY_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    assemble_prompt,
)
from .schema import (
    AgentVote,
    AttachedPlaybook,
    ComposedPatternHandoff,
    DecisionProtocol,
    DecisionRequest,
    GroupDecisionIntervention,
    GroupDecisionMode,
    GroupDecisionProfilePattern,
    MethodFitAudit,
    TallyIntegrityAudit,
    severity_from_fit,
)
from .tally import tally_votes

log = get_logger("vstack.group_decision.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class DecisionProtocolAnalyzer:
    """Generate a decision-aggregation protocol with optional tally."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: GroupDecisionMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: GroupDecisionMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        request: DecisionRequest,
        votes: list[AgentVote] | None = None,
        *,
        mode: GroupDecisionMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> DecisionProtocol:
        active_mode: GroupDecisionMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="group_decision"):
            return self._run_pipeline(request, votes, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        requests: Iterable[DecisionRequest],
        *,
        mode: GroupDecisionMode | None = None,
    ) -> Iterator[DecisionProtocol]:
        active_mode: GroupDecisionMode = mode or self.mode
        for request in requests:
            run_id = new_run_id()
            with run_context(run_id, pattern="group_decision"):
                yield self._run_pipeline(request, None, active_mode, run_id, None)

    def _run_pipeline(
        self,
        request: DecisionRequest,
        votes: list[AgentVote] | None,
        mode: GroupDecisionMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> DecisionProtocol:
        self._validate_request(request)
        injection_detected = self._scan_injection(request)
        started = time.monotonic()
        log.info(
            "Generating decision protocol (mode=%s) for decision_id=%s",
            mode,
            request.decision_id or "<unknown>",
        )

        acc = _PipelineAcc()
        method_fit_audit: MethodFitAudit | None = None
        tally_integrity_audit: TallyIntegrityAudit | None = None
        interventions: list[GroupDecisionIntervention] = []

        if mode == "quick":
            data = self._pass_quick(request, acc)
        elif mode == "standard":
            data = self._pass_generate(request, acc=acc)
        else:  # forensic
            data = self._pass_generate(request, acc=acc)

        recommended = self._coerce_model(request.forced_model or data.get("recommended_model"))
        rationale = str(data.get("rationale", "")).strip() or (
            "Selected the default model for the given stakes and reversibility."
        )
        protocol_steps = [
            str(s) for s in data.get("protocol_steps", []) if isinstance(s, str)
        ] or self._default_protocol_steps(recommended)
        threshold = str(data.get("threshold", "")).strip() or self._default_threshold(recommended)
        quorum = self._coerce_quorum(data.get("quorum"))
        tie_breaker = str(data.get("tie_breaker", "")).strip()
        fallback = self._coerce_optional_model(data.get("fallback_model"))

        tally_result = (
            tally_votes(method=recommended, votes=votes, quorum=quorum)
            if votes is not None
            else None
        )

        if mode == "forensic":
            protocol_text = json.dumps(
                {
                    "recommended_model": recommended,
                    "rationale": rationale,
                    "protocol_steps": protocol_steps,
                    "threshold": threshold,
                    "quorum": quorum,
                    "tie_breaker": tie_breaker,
                    "fallback_model": fallback,
                },
                default=str,
            )
            properties = json.dumps(
                {
                    "stakes": request.stakes,
                    "reversibility": request.reversibility,
                    "time_pressure": request.time_pressure,
                    "buy_in_required": request.buy_in_required,
                    "regulatory_exposure": request.regulatory_exposure,
                },
                default=str,
            )
            method_fit_audit = self._pass_forensic_method_fit(protocol_text, properties, acc)
            tally_integrity_audit = self._pass_forensic_tally_integrity(protocol_text, acc)
            interventions = self._pass_forensic_interventions(
                protocol_text, method_fit_audit, tally_integrity_audit, acc
            )

        fit_score = (
            method_fit_audit.fit_score
            if method_fit_audit
            else self._heuristic_fit(request, recommended)
        )
        severity = severity_from_fit(fit_score)
        profile_pattern = self._classify_profile_pattern(
            request, recommended, quorum, tie_breaker, fallback, fit_score
        )

        composition = (
            self._build_composition_handoff(request, profile_pattern, recommended, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or request.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = DecisionProtocol(
                    decision_id=request.decision_id,
                    title=request.title,
                    recommended_model=recommended,
                    rationale=rationale,
                    protocol_steps=protocol_steps,
                    threshold=threshold,
                    quorum=quorum,
                    tie_breaker=tie_breaker,
                    fallback_model=fallback,
                    tally_result=tally_result,
                    mode=mode,
                    profile_pattern=profile_pattern,
                    fit_score=fit_score,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return DecisionProtocol(
            decision_id=request.decision_id,
            title=request.title,
            recommended_model=recommended,
            rationale=rationale,
            protocol_steps=protocol_steps,
            threshold=threshold,
            quorum=quorum,
            tie_breaker=tie_breaker,
            fallback_model=fallback,
            tally_result=tally_result,
            generator_model=self.model,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            fit_score=fit_score,
            method_fit_audit=method_fit_audit,
            tally_integrity_audit=tally_integrity_audit,
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

    def _validate_request(self, request: DecisionRequest) -> None:
        if not request.title or not request.title.strip():
            raise ValueError("DecisionRequest.title cannot be empty.")
        if len(request.options) < 2:
            raise ValueError("DecisionRequest.options must contain at least 2 options.")
        if len(request.agents) < 2:
            raise ValueError("DecisionRequest.agents must contain at least 2 agents.")

    def _scan_injection(self, request: DecisionRequest) -> bool:
        targets: list[tuple[str, str]] = [("title", request.title)]
        for i, o in enumerate(request.options):
            targets.append((f"options[{i}].description", o.description))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in decision request",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: GroupDecisionMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=DECISION_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "group_decision"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_generate(
        self, request: DecisionRequest, *, acc: "_PipelineAcc | None" = None
    ) -> dict[str, Any]:
        prompt = DECISION_PROTOCOL_PROMPT.format(
            title=request.title,
            options=self._format_options(request),
            agents=", ".join(request.agents),
            stakes=request.stakes,
            reversibility=request.reversibility,
            time_pressure=request.time_pressure,
            expertise_asymmetry=request.expertise_asymmetry,
            regulatory_exposure=request.regulatory_exposure,
            buy_in_required=request.buy_in_required,
            forced_model=request.forced_model or "null",
        )
        if acc is None:
            raw = self._complete(prompt, system=DECISION_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="generate", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_quick(self, request: DecisionRequest, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            title=request.title,
            stakes=request.stakes,
            reversibility=request.reversibility,
            buy_in_required=request.buy_in_required,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _coerce_model(
        self, raw: Any
    ) -> Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]:
        if isinstance(raw, str) and raw.strip().lower() in (
            "concurring",
            "majority",
            "consensus",
            "fist_to_five",
            "unanimous",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        return "majority"

    def _coerce_optional_model(
        self, raw: Any
    ) -> Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None:
        if raw is None or raw == "null" or raw == "":
            return None
        if isinstance(raw, str) and raw.strip().lower() in (
            "concurring",
            "majority",
            "consensus",
            "fist_to_five",
            "unanimous",
        ):
            return raw.strip().lower()  # type: ignore[return-value]
        return None

    def _coerce_quorum(self, raw: Any) -> int | None:
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return max(1, value)

    def _default_protocol_steps(self, model: str) -> list[str]:
        if model == "concurring":
            return [
                "Designate one decisive voter (highest expertise + accountability).",
                "Decisive voter casts the vote; other agents may object explicitly.",
                "If no objection within the time window, the decision is final.",
            ]
        if model == "majority":
            return [
                "Each agent casts one vote for one option (or abstains).",
                "Tally cast votes; option with >50% of cast votes wins.",
                "Record dissenters by name; surface in the postmortem if applicable.",
            ]
        if model == "consensus":
            return [
                "Discuss until objections are surfaced and addressed.",
                "Each agent affirms or formally blocks (a block needs a concrete reason).",
                "If any agent blocks, return to discussion; do not call the decision.",
            ]
        if model == "fist_to_five":
            return [
                "Each agent privately scores their support (0 = block, 5 = champion).",
                "Reveal scores simultaneously.",
                "Any score of 0 blocks the option; otherwise the option with mean >= 3 wins.",
                "If multiple options qualify, the highest mean wins.",
            ]
        if model == "unanimous":
            return [
                "Each agent must positively vote for the same option.",
                "Any abstention or dissent halts the decision.",
                "Return to discussion until unanimous or escalate.",
            ]
        return ["Run the chosen model."]

    def _default_threshold(self, model: str) -> str:
        return {
            "concurring": "Decisive vote with no explicit objection.",
            "majority": ">50% of cast votes.",
            "consensus": "All agents affirm or do not block.",
            "fist_to_five": "Mean score >= 3.0 with no agent at score 0 (block).",
            "unanimous": "All agents vote for the same option.",
        }.get(model, "See protocol steps.")

    def _format_options(self, request: DecisionRequest) -> str:
        return "\n".join(f"  - {o.option_id}: {o.description}" for o in request.options)

    # --- v0.2.0 forensic passes ---------------------------------------

    def _pass_forensic_method_fit(
        self, protocol_text: str, properties: str, acc: "_PipelineAcc"
    ) -> MethodFitAudit | None:
        prompt = assemble_prompt(
            FORENSIC_METHOD_FIT_PROMPT, protocol=protocol_text, properties=properties
        )
        raw = self._call(prompt, pass_name="forensic_method_fit", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return MethodFitAudit(**obj)
        except Exception as exc:
            log.warning("MethodFitAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_tally_integrity(
        self, protocol_text: str, acc: "_PipelineAcc"
    ) -> TallyIntegrityAudit | None:
        prompt = assemble_prompt(FORENSIC_TALLY_INTEGRITY_PROMPT, protocol=protocol_text)
        raw = self._call(prompt, pass_name="forensic_tally_integrity", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return TallyIntegrityAudit(**obj)
        except Exception as exc:
            log.warning("TallyIntegrityAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        protocol_text: str,
        method_fit_audit: MethodFitAudit | None,
        tally_integrity_audit: TallyIntegrityAudit | None,
        acc: "_PipelineAcc",
    ) -> list[GroupDecisionIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            protocol=protocol_text,
            method_fit_audit=method_fit_audit.model_dump() if method_fit_audit else None,
            tally_integrity_audit=tally_integrity_audit.model_dump()
            if tally_integrity_audit
            else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[GroupDecisionIntervention] = []
        for entry in data:
            try:
                interventions.append(GroupDecisionIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed GroupDecisionIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _heuristic_fit(self, request: DecisionRequest, model: str) -> float:
        score = 0.5
        if request.stakes == "high" and model in ("consensus", "unanimous"):
            score += 0.15
        if (
            request.stakes == "low"
            and request.reversibility == "reversible"
            and model in ("concurring", "majority")
        ):
            score += 0.15
        if request.buy_in_required and model in ("consensus", "fist_to_five"):
            score += 0.15
        if request.buy_in_required and model == "concurring":
            score -= 0.2
        if request.regulatory_exposure and model in ("consensus", "unanimous"):
            score += 0.1
        if request.time_pressure == "urgent" and model in (
            "concurring",
            "majority",
        ):
            score += 0.05
        if request.time_pressure == "urgent" and model == "unanimous":
            score -= 0.1
        return round(max(0.0, min(1.0, score)), 2)

    def _classify_profile_pattern(
        self,
        request: DecisionRequest,
        model: str,
        quorum: int | None,
        tie_breaker: str,
        fallback: str | None,
        fit_score: float,
    ) -> GroupDecisionProfilePattern:
        if (
            model == "consensus"
            and request.stakes == "low"
            and request.reversibility != "irreversible"
        ):
            return "consensus_overused"
        if model == "majority" and request.buy_in_required and request.stakes != "low":
            return "majority_when_consensus_needed"
        if model == "concurring" and request.buy_in_required:
            return "concurring_when_buyin_needed"
        if request.buy_in_required and model not in ("consensus", "fist_to_five", "unanimous"):
            return "fist_to_five_underused"
        if model == "majority" and quorum is None:
            return "no_quorum_specified"
        if model == "majority" and not tie_breaker:
            return "no_tie_breaker"
        if fit_score >= 0.7:
            return "good_fit_protocol"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        request: DecisionRequest,
        profile_pattern: GroupDecisionProfilePattern,
        recommended: str,
        interventions: list[GroupDecisionIntervention],
    ) -> ComposedPatternHandoff:
        provisional = DecisionProtocol(
            decision_id=request.decision_id,
            title=request.title,
            recommended_model=cast(Any, recommended),
            rationale="",
            protocol_steps=[],
            threshold="",
            profile_pattern=profile_pattern,
            interventions=interventions,
        )
        downstream, rationale = recommended_downstream(provisional, request)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "recommended_model": recommended,
            "stakes": request.stakes,
            "framework": request.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(
        self, interventions: list[GroupDecisionIntervention]
    ) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_dimension)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.model, pb.failure_mode) not in attached:
                attached[(pb.model, pb.failure_mode)] = pb
        return list(attached.values())


# Backward-compat alias.
DecisionProtocolGenerator = DecisionProtocolAnalyzer


class DecisionProtocolAnalyzerAsync:
    """Async mirror of :class:`DecisionProtocolAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: GroupDecisionMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: GroupDecisionMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        request: DecisionRequest,
        votes: list[AgentVote] | None = None,
        *,
        mode: GroupDecisionMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> DecisionProtocol:
        active_mode: GroupDecisionMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = DecisionProtocolAnalyzer(
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
            sync_analyzer.run,
            request,
            votes,
            mode=active_mode,
            baseline_path=baseline_path,
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


_legacy_log = logging.getLogger("vstack.group_decision.generator")
_legacy_log.addHandler(logging.NullHandler())
