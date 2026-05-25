"""PsychologicalSafetyAnalyzer: multi-mode Edmondson safety diagnostic.

Three modes (quick/standard/forensic) with v0.2.0 production
infrastructure. Backward-compatible: ``PsychologicalSafetyDetector``
remains aliased to ``PsychologicalSafetyAnalyzer``.
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
    BEHAVIOR_SCORING_PROMPT,
    FORENSIC_ERROR_REPORTING_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_VOICE_AUDIT_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    BEHAVIORS,
    AttachedPlaybook,
    BehaviorEvidence,
    ComposedPatternHandoff,
    ErrorReportingAudit,
    MultiAgentSafetyTrace,
    PsychologicalSafetyDetection,
    PsychSafetyMode,
    PsychSafetyProfilePattern,
    SafetyIntervention,
    VoiceSignalAudit,
    severity_from_absence,
)

log = get_logger("vstack.psych_safety.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class PsychologicalSafetyAnalyzer:
    """Run the Edmondson safety diagnostic on a MultiAgentSafetyTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: PsychSafetyMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: PsychSafetyMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(
        self,
        trace: MultiAgentSafetyTrace,
        *,
        mode: PsychSafetyMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> PsychologicalSafetyDetection:
        active_mode: PsychSafetyMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="psych_safety"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[MultiAgentSafetyTrace],
        *,
        mode: PsychSafetyMode | None = None,
    ) -> Iterator[PsychologicalSafetyDetection]:
        active_mode: PsychSafetyMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="psych_safety"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    def _run_pipeline(
        self,
        trace: MultiAgentSafetyTrace,
        mode: PsychSafetyMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> PsychologicalSafetyDetection:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)
        trace_text = self._serialize_trace(trace)
        started = time.monotonic()
        log.info(
            "Running PsychSafety diagnostic (mode=%s) for team %s (agents=%d, messages=%d)",
            mode,
            trace.team_id or "<unknown>",
            len(trace.agents),
            len(trace.messages),
        )

        acc = _PipelineAcc()
        voice_audit: VoiceSignalAudit | None = None
        error_reporting_audit: ErrorReportingAudit | None = None
        blocking_behaviors: list[str] = []

        if mode == "quick":
            evidence, blocking_behaviors, top_iv = self._pass_quick(trace, trace_text, acc)
            interventions = [top_iv] if top_iv else []
        elif mode == "standard":
            analysis = self._pass_1_behaviors(trace, trace_text, acc=acc)
            evidence = analysis["behaviors"]
            blocking_behaviors = analysis["blocking_behaviors"]
            scores = self._build_behavior_scores(evidence)
            lowest = self._lowest_presence(scores)
            interventions = self._pass_2_interventions(trace, trace_text, evidence, lowest, acc=acc)
        elif mode == "forensic":
            analysis = self._pass_1_behaviors(trace, trace_text, acc=acc)
            evidence = analysis["behaviors"]
            blocking_behaviors = analysis["blocking_behaviors"]
            scores = self._build_behavior_scores(evidence)
            lowest = self._lowest_presence(scores)
            voice_audit = self._pass_forensic_voice(trace_text, acc)
            error_reporting_audit = self._pass_forensic_error_reporting(trace_text, acc)
            interventions = self._pass_forensic_interventions(
                evidence, lowest, voice_audit, error_reporting_audit, acc
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown PsychSafetyMode: {mode!r}")

        scores = self._build_behavior_scores(evidence)
        safety_score = self._safety_score(scores)
        climate = self._climate(safety_score)
        profile_pattern = self._classify_profile_pattern(scores, climate)
        severity = severity_from_absence(1.0 - safety_score)

        composition = (
            self._build_composition_handoff(trace, profile_pattern, scores, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = PsychologicalSafetyDetection(
                    team_id=trace.team_id,
                    safety_score=safety_score,
                    team_climate=climate,
                    behavior_scores=scores,
                    behaviors=evidence,
                    blocking_behaviors=blocking_behaviors,
                    interventions=interventions,
                    success=trace.success,
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        elapsed_ms = (time.monotonic() - started) * 1000.0

        return PsychologicalSafetyDetection(
            team_id=trace.team_id,
            safety_score=safety_score,
            team_climate=climate,
            behavior_scores=scores,
            behaviors=evidence,
            blocking_behaviors=blocking_behaviors,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            voice_audit=voice_audit,
            error_reporting_audit=error_reporting_audit,
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

    # --- Legacy v0.0.x surface preserved ------------------------------

    def _validate_trace(self, trace: MultiAgentSafetyTrace) -> None:
        if not trace.goal or not trace.goal.strip():
            raise ValueError("MultiAgentSafetyTrace.goal cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("MultiAgentSafetyTrace.outcome cannot be empty.")
        if len(trace.agents) < 2:
            raise ValueError("MultiAgentSafetyTrace.agents must contain at least 2 agents.")
        if not trace.messages:
            raise ValueError("MultiAgentSafetyTrace.messages cannot be empty.")

    def _scan_injection(self, trace: MultiAgentSafetyTrace) -> bool:
        targets: list[tuple[str, str]] = [
            ("goal", trace.goal),
            ("outcome", trace.outcome),
        ]
        for i, m in enumerate(trace.messages):
            targets.append((f"messages[{i}].content", m.content))
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
        return hit_count > 0

    def _serialize_trace(self, trace: MultiAgentSafetyTrace) -> str:
        header = [
            f"Goal: {trace.goal}",
            f"Agents: {', '.join(trace.agents)}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        msg_lines = []
        for i, m in enumerate(trace.messages):
            ts = f"[{m.timestamp.isoformat()}] " if m.timestamp is not None else f"[msg {i + 1}] "
            msg_lines.append(
                f"{ts}({m.message_type}) {m.from_agent} -> {m.to_agent or 'TEAM'}: {m.content}"
            )
        full = "\n".join(header + msg_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning("Safety trace exceeds max_trace_chars; truncating")
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRUNCATED ({len(full) - self.max_trace_chars} chars) ...]\n\n"
            + full[-keep:]
        )

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: PsychSafetyMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=SAFETY_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "psych_safety"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    def _pass_1_behaviors(
        self,
        trace: MultiAgentSafetyTrace,
        trace_text: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> dict[str, Any]:
        prompt = BEHAVIOR_SCORING_PROMPT.format(
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=SAFETY_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="behaviors", mode="standard", acc=acc)
        data = _try_json_object(raw) or {"behaviors": [], "blocking_behaviors": []}

        behaviors: list[BehaviorEvidence] = []
        for entry in data.get("behaviors", []):
            if not isinstance(entry, dict):
                continue
            try:
                behaviors.append(BehaviorEvidence(**entry))
            except Exception as exc:
                log.warning("Dropping malformed BehaviorEvidence (%s)", type(exc).__name__)
        seen = {ev.behavior for ev in behaviors}
        for b in BEHAVIORS:
            if b not in seen:
                behaviors.append(
                    BehaviorEvidence(
                        behavior=b,  # type: ignore[arg-type]
                        presence_score=0.0,
                        severity_of_absence="high",
                        explanation="No evidence of this behavior in the trace.",
                        evidence_quotes=[],
                    )
                )
        order = {b: i for i, b in enumerate(BEHAVIORS)}
        behaviors.sort(key=lambda e: order.get(e.behavior, len(BEHAVIORS)))
        blocking_raw = data.get("blocking_behaviors", [])
        blocking = [str(x) for x in blocking_raw if isinstance(x, str)]
        return {"behaviors": behaviors, "blocking_behaviors": blocking}

    def _pass_2_interventions(
        self,
        trace: MultiAgentSafetyTrace,
        trace_text: str,
        behaviors: list[BehaviorEvidence],
        lowest: str,
        *,
        acc: "_PipelineAcc | None" = None,
    ) -> list[SafetyIntervention]:
        evidence_text = json.dumps([b.model_dump() for b in behaviors], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            lowest_behavior=lowest,
            evidence=evidence_text,
            trace=trace_text,
        )
        if acc is None:
            raw = self._complete(prompt, system=SAFETY_SYSTEM_PROMPT).strip()
        else:
            raw = self._call(prompt, pass_name="interventions", mode="standard", acc=acc)
        data = extract_json_array(raw)
        interventions: list[SafetyIntervention] = []
        for entry in data:
            try:
                interventions.append(SafetyIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed SafetyIntervention (%s)", type(exc).__name__)
        return interventions

    def _build_behavior_scores(self, behaviors: list[BehaviorEvidence]) -> dict[str, float]:
        scores: dict[str, float] = {b: 0.0 for b in BEHAVIORS}
        for ev in behaviors:
            scores[str(ev.behavior)] = max(scores.get(str(ev.behavior), 0.0), ev.presence_score)
        return scores

    def _lowest_presence(self, scores: dict[str, float]) -> str:
        if not scores:
            return "voice"
        return min(scores, key=lambda b: scores[b])

    def _safety_score(self, scores: dict[str, float]) -> float:
        if not scores:
            return 0.0
        return round(sum(scores.values()) / len(scores), 2)

    def _climate(self, safety_score: float) -> Literal["safe", "cautious", "silenced"]:
        if safety_score >= 0.65:
            return "safe"
        if safety_score >= 0.35:
            return "cautious"
        return "silenced"

    # --- v0.2.0 mode passes -------------------------------------------

    def _pass_quick(
        self,
        trace: MultiAgentSafetyTrace,
        trace_text: str,
        acc: "_PipelineAcc",
    ) -> tuple[list[BehaviorEvidence], list[str], SafetyIntervention | None]:
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            goal=trace.goal,
            outcome=trace.outcome,
            success=trace.success,
            agents=trace.agents,
            trace=trace_text,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        obj = _try_json_object(raw) or {}
        behaviors_raw = obj.get("behaviors", [])
        behaviors: list[BehaviorEvidence] = []
        if isinstance(behaviors_raw, list):
            for entry in behaviors_raw:
                if not isinstance(entry, dict):
                    continue
                try:
                    behaviors.append(BehaviorEvidence(**entry))
                except Exception as exc:
                    log.warning(
                        "Dropping malformed BehaviorEvidence (%s)",
                        type(exc).__name__,
                    )
        seen = {ev.behavior for ev in behaviors}
        for b in BEHAVIORS:
            if b not in seen:
                behaviors.append(
                    BehaviorEvidence(
                        behavior=b,  # type: ignore[arg-type]
                        presence_score=0.0,
                        severity_of_absence="high",
                        explanation="No evidence observed.",
                        evidence_quotes=[],
                    )
                )
        order = {b: i for i, b in enumerate(BEHAVIORS)}
        behaviors.sort(key=lambda e: order.get(e.behavior, len(BEHAVIORS)))
        blocking_raw = obj.get("blocking_behaviors", [])
        blocking = [str(x) for x in blocking_raw if isinstance(x, str)]
        top_iv: SafetyIntervention | None = None
        iv_entry = obj.get("top_intervention")
        if iv_entry:
            try:
                top_iv = SafetyIntervention(**iv_entry)
            except Exception as exc:
                log.warning("Quick top_intervention parse error: %s", type(exc).__name__)
        return behaviors, blocking, top_iv

    def _pass_forensic_voice(self, trace_text: str, acc: "_PipelineAcc") -> VoiceSignalAudit | None:
        prompt = assemble_prompt(FORENSIC_VOICE_AUDIT_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_voice", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return VoiceSignalAudit(**obj)
        except Exception as exc:
            log.warning("VoiceSignalAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_error_reporting(
        self, trace_text: str, acc: "_PipelineAcc"
    ) -> ErrorReportingAudit | None:
        prompt = assemble_prompt(FORENSIC_ERROR_REPORTING_PROMPT, trace=trace_text)
        raw = self._call(prompt, pass_name="forensic_error_reporting", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return ErrorReportingAudit(**obj)
        except Exception as exc:
            log.warning("ErrorReportingAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        behaviors: list[BehaviorEvidence],
        lowest: str,
        voice_audit: VoiceSignalAudit | None,
        error_reporting_audit: ErrorReportingAudit | None,
        acc: "_PipelineAcc",
    ) -> list[SafetyIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            lowest_behavior=lowest,
            evidence=[b.model_dump() for b in behaviors],
            voice_audit=voice_audit.model_dump() if voice_audit else None,
            error_reporting_audit=error_reporting_audit.model_dump()
            if error_reporting_audit
            else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[SafetyIntervention] = []
        for entry in data:
            try:
                interventions.append(SafetyIntervention(**entry))
            except Exception as exc:
                log.warning("Dropping malformed SafetyIntervention (%s)", type(exc).__name__)
        return interventions

    # --- Profile classifier + composition + playbooks -----------------

    def _classify_profile_pattern(
        self, scores: dict[str, float], climate: str
    ) -> PsychSafetyProfilePattern:
        if climate == "safe":
            return "safe_team"
        all_absent = sum(1 for s in scores.values() if s < 0.2)
        if all_absent == 4:
            return "all_four_suppressed"
        if climate == "silenced":
            return "silenced_team"

        voice = scores.get("voice", 0.0)
        help_seeking = scores.get("help-seeking", 0.0)
        error_reporting = scores.get("error-reporting", 0.0)
        boundary = scores.get("boundary-spanning", 0.0)
        if voice < 0.2 and help_seeking >= 0.3:
            return "voice_absent"
        if error_reporting < 0.2:
            return "error_concealment"
        if help_seeking < 0.2:
            return "help_seeking_blocked"
        if boundary < 0.2:
            return "siloed_no_boundary_spanning"
        if climate == "cautious":
            return "cautious_team"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        trace: MultiAgentSafetyTrace,
        profile_pattern: PsychSafetyProfilePattern,
        scores: dict[str, float],
        interventions: list[SafetyIntervention],
    ) -> ComposedPatternHandoff:
        provisional = PsychologicalSafetyDetection(
            team_id=trace.team_id,
            safety_score=0.0,
            team_climate="cautious",
            behavior_scores={},
            behaviors=[],
            blocking_behaviors=[],
            interventions=interventions,
            success=trace.success,
            profile_pattern=profile_pattern,
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": profile_pattern,
            "behavior_scores": scores,
            "framework": trace.framework,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[SafetyIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_behavior)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.behavior, pb.failure_mode) not in attached:
                attached[(pb.behavior, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
PsychologicalSafetyDetector = PsychologicalSafetyAnalyzer


class PsychologicalSafetyAnalyzerAsync:
    """Async mirror of :class:`PsychologicalSafetyAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: PsychSafetyMode = "standard",
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: PsychSafetyMode = mode
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: MultiAgentSafetyTrace,
        *,
        mode: PsychSafetyMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> PsychologicalSafetyDetection:
        active_mode: PsychSafetyMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = PsychologicalSafetyAnalyzer(
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


_legacy_log = logging.getLogger("vstack.psych_safety.generator")
_legacy_log.addHandler(logging.NullHandler())
