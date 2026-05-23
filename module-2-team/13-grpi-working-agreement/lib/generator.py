"""GRPIWorkingAgreementAnalyzer: multi-mode GRPI generator.

Three pipeline modes (quick / standard / forensic) wired with full
v0.2.0 production infrastructure: structured logging with run-id,
token/cost telemetry, input sanitization + fencing, async mirror.

Backward-compatible: ``GRPIWorkingAgreementGenerator`` remains
exported as an alias for ``GRPIWorkingAgreementAnalyzer``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine, Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol, cast

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
    FORENSIC_DYSFUNCTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_ROLE_FIT_PROMPT,
    GRPI_SYSTEM_PROMPT,
    QUICK_GENERATION_PROMPT,
    STANDARD_GENERATION_PROMPT,
    STANDARD_REFINEMENT_PROMPT,
    assemble_prompt,
)
from .schema import (
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DysfunctionPreventionAudit,
    GoalsSection,
    GRPIIntervention,
    GRPIMode,
    GRPIProfilePattern,
    InteractionsSection,
    ProcessesSection,
    RoleAssignment,
    RoleFitAudit,
    RolesSection,
    TeamSetupRequest,
    WorkingAgreement,
    severity_from_completeness,
)

log = get_logger("agentcity.grpi.generator")


_DEFAULT_COST_PER_1K = {"input": 0.003, "output": 0.015}


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    async def complete(self, prompt: str, system: str | None = None) -> str: ...


class GRPIWorkingAgreementAnalyzer:
    """Generate a GRPI Working Agreement from a TeamSetupRequest."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: GRPIMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: GRPIMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def generate(
        self,
        request: TeamSetupRequest,
        *,
        mode: GRPIMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> WorkingAgreement:
        """v0.0.x-compatible entrypoint."""
        return self.run(request, mode=mode, baseline_path=baseline_path)

    def run(
        self,
        request: TeamSetupRequest,
        *,
        mode: GRPIMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> WorkingAgreement:
        active_mode: GRPIMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="grpi"):
            return self._run_pipeline(request, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        requests: Iterable[TeamSetupRequest],
        *,
        mode: GRPIMode | None = None,
    ) -> Iterator[WorkingAgreement]:
        active_mode: GRPIMode = mode or self.mode
        for request in requests:
            run_id = new_run_id()
            with run_context(run_id, pattern="grpi"):
                yield self._run_pipeline(request, active_mode, run_id, None)

    def _run_pipeline(
        self,
        request: TeamSetupRequest,
        mode: GRPIMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> WorkingAgreement:
        self._validate_request(request)
        injection_detected = self._scan_injection(request)
        started = time.monotonic()
        log.info(
            "Generating GRPI agreement (mode=%s) for team %s (agents=%d)",
            mode,
            request.team_id or "<unknown>",
            len(request.agents),
        )

        acc = _PipelineAcc()
        role_fit: list[RoleFitAudit] = []
        dysfunction: DysfunctionPreventionAudit | None = None
        interventions: list[GRPIIntervention] = []

        if mode == "quick":
            data = self._pass_quick(request, acc)
        elif mode == "standard":
            # v0.0.x compat: single generation pass.
            data = self._pass_standard_generation(request, acc)
        elif mode == "forensic":
            data = self._pass_standard_generation(request, acc)
        else:  # pragma: no cover
            raise ValueError(f"unknown GRPIMode: {mode!r}")

        agreement = self._build_agreement(request, data, mode)

        if mode == "forensic":
            role_fit = self._pass_forensic_role_fit(request, agreement, acc)
            dysfunction = self._pass_forensic_dysfunction(agreement, acc)
            interventions = self._pass_forensic_interventions(agreement, role_fit, dysfunction, acc)
            agreement.role_fit_audits = role_fit
            agreement.dysfunction_prevention = dysfunction
            agreement.interventions = interventions

        # Deterministic completeness + profile pattern.
        agreement.completeness_score = self._compute_completeness(agreement)
        agreement.profile_pattern = self._classify_profile_pattern(agreement, request)
        agreement.severity = severity_from_completeness(agreement.completeness_score)

        if self.composition_enabled:
            agreement.composition_handoff = self._build_composition_handoff(request, agreement)

        if self.playbooks_enabled:
            agreement.attached_playbooks = self._attach_playbooks(interventions)

        baseline: BaselineComparison | None = None
        baseline_source = baseline_path or request.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                baseline = compare_to_baseline(agreement, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)
        agreement.baseline = baseline

        elapsed_ms = (time.monotonic() - started) * 1000.0
        agreement.run_id = run_id
        agreement.cost_usd = acc.cost_usd
        agreement.tokens_total = acc.tokens_total
        agreement.tokens_input = acc.tokens_input
        agreement.tokens_output = acc.tokens_output
        agreement.llm_calls = acc.llm_calls
        agreement.elapsed_ms = elapsed_ms
        agreement.injection_detected = injection_detected
        agreement.mode = mode

        log.info(
            "GRPI done mode=%s completeness=%.2f profile=%s elapsed=%.0fms",
            mode,
            agreement.completeness_score,
            agreement.profile_pattern,
            elapsed_ms,
        )
        return agreement

    # --- Validation ----------------------------------------------------

    def _validate_request(self, request: TeamSetupRequest) -> None:
        if not request.task or not request.task.strip():
            raise ValueError("TeamSetupRequest.task cannot be empty.")
        if len(request.agents) < 2:
            raise ValueError("TeamSetupRequest.agents must contain at least 2 agents.")
        names = [agent.name for agent in request.agents]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate agent names in TeamSetupRequest.agents: {names}")

    def _scan_injection(self, request: TeamSetupRequest) -> bool:
        targets: list[tuple[str, str]] = [("task", request.task)]
        for i, c in enumerate(request.constraints):
            targets.append((f"constraints[{i}]", c))
        for i, c in enumerate(request.success_criteria):
            targets.append((f"success_criteria[{i}]", c))
        for i, a in enumerate(request.agents):
            targets.append((f"agents[{i}].description", a.description))
        hit_count = 0
        for field, value in targets:
            if not value:
                continue
            hits = detect_injection(value)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern in request field",
                    extra={"field": field, "pattern_count": len(hits)},
                )
        return hit_count > 0

    # --- LLM call helper ----------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: GRPIMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=GRPI_SYSTEM_PROMPT)
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
            extra={"pass": pass_name, "mode": mode, "pattern": "grpi"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # --- Passes --------------------------------------------------------

    def _pass_quick(self, request: TeamSetupRequest, acc: "_PipelineAcc") -> dict[str, Any]:
        prompt = assemble_prompt(
            QUICK_GENERATION_PROMPT,
            task=request.task,
            agents=[a.model_dump() for a in request.agents],
            constraints=request.constraints,
            success_criteria=request.success_criteria,
            kill_criteria=request.kill_criteria,
            framework=request.framework,
            risk_level=request.risk_level,
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_standard_generation(
        self, request: TeamSetupRequest, acc: "_PipelineAcc"
    ) -> dict[str, Any]:
        prompt = assemble_prompt(
            STANDARD_GENERATION_PROMPT,
            task=request.task,
            agents=[a.model_dump() for a in request.agents],
            constraints=request.constraints,
            success_criteria=request.success_criteria,
            kill_criteria=request.kill_criteria,
            framework=request.framework,
            risk_level=request.risk_level,
        )
        raw = self._call(prompt, pass_name="standard_generation", mode="standard", acc=acc)
        return _try_json_object(raw) or {}

    def _pass_standard_refinement(
        self,
        request: TeamSetupRequest,
        draft: dict[str, Any],
        acc: "_PipelineAcc",
    ) -> dict[str, Any]:
        prompt = assemble_prompt(
            STANDARD_REFINEMENT_PROMPT,
            draft=draft,
            task=request.task,
            risk_level=request.risk_level,
        )
        raw = self._call(prompt, pass_name="standard_refinement", mode="standard", acc=acc)
        refined = _try_json_object(raw)
        return refined if refined else draft

    def _pass_forensic_role_fit(
        self,
        request: TeamSetupRequest,
        agreement: WorkingAgreement,
        acc: "_PipelineAcc",
    ) -> list[RoleFitAudit]:
        prompt = assemble_prompt(
            FORENSIC_ROLE_FIT_PROMPT,
            agents=[a.model_dump() for a in request.agents],
            roles_section=agreement.roles.model_dump(),
        )
        raw = self._call(prompt, pass_name="forensic_role_fit", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        audits: list[RoleFitAudit] = []
        for entry in data:
            try:
                audits.append(RoleFitAudit(**entry))
            except Exception as exc:
                log.warning("Dropping malformed RoleFitAudit (%s)", type(exc).__name__)
        return audits

    def _pass_forensic_dysfunction(
        self, agreement: WorkingAgreement, acc: "_PipelineAcc"
    ) -> DysfunctionPreventionAudit | None:
        prompt = assemble_prompt(
            FORENSIC_DYSFUNCTION_PROMPT,
            agreement=agreement.model_dump(
                exclude={"composition_handoff", "attached_playbooks", "baseline"}
            ),
        )
        raw = self._call(prompt, pass_name="forensic_dysfunction", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return DysfunctionPreventionAudit(**obj)
        except Exception as exc:
            log.warning("DysfunctionPreventionAudit parse error: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        agreement: WorkingAgreement,
        role_fit: list[RoleFitAudit],
        dysfunction: DysfunctionPreventionAudit | None,
        acc: "_PipelineAcc",
    ) -> list[GRPIIntervention]:
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            agreement=agreement.model_dump(
                exclude={"composition_handoff", "attached_playbooks", "baseline"}
            ),
            role_fit=[rfa.model_dump() for rfa in role_fit],
            dysfunction=dysfunction.model_dump() if dysfunction else None,
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        data = extract_json_array(raw)
        interventions: list[GRPIIntervention] = []
        for entry in data:
            try:
                interventions.append(GRPIIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed GRPIIntervention (%s)",
                    type(exc).__name__,
                )
        return interventions

    # --- Builders ------------------------------------------------------

    def _build_agreement(
        self,
        request: TeamSetupRequest,
        data: dict[str, Any],
        mode: GRPIMode,
    ) -> WorkingAgreement:
        return WorkingAgreement(
            team_id=request.team_id,
            task=request.task,
            goals=self._build_goals(data.get("goals", {}), request),
            roles=self._build_roles(data.get("roles", {}), request),
            processes=self._build_processes(data.get("processes", {})),
            interactions=self._build_interactions(data.get("interactions", {})),
            generator_model=self.model,
            framework=request.framework,
            mode=mode,
        )

    def _build_goals(self, data: dict[str, Any], request: TeamSetupRequest) -> GoalsSection:
        try:
            return GoalsSection(
                primary_goal=str(data.get("primary_goal") or request.task),
                measurable_success_criteria=self._strlist(
                    data.get("measurable_success_criteria") or request.success_criteria
                )
                or ["(no measurable criteria specified; agreement needs revision)"],
                scope_boundaries=self._strlist(data.get("scope_boundaries", [])),
                deliverables=self._strlist(data.get("deliverables", [])),
                kill_criteria=self._strlist(data.get("kill_criteria") or request.kill_criteria),
            )
        except Exception as exc:
            log.warning("Falling back on Goals section (%s)", type(exc).__name__)
            return GoalsSection(
                primary_goal=request.task,
                measurable_success_criteria=request.success_criteria
                or ["(generation failed; please add manually)"],
                deliverables=[],
            )

    def _build_roles(self, data: dict[str, Any], request: TeamSetupRequest) -> RolesSection:
        assignments_raw = data.get("role_assignments") or []
        assignments: list[RoleAssignment] = []
        for entry in assignments_raw:
            if not isinstance(entry, dict):
                continue
            try:
                assignments.append(
                    RoleAssignment(
                        agent_name=str(entry.get("agent_name", "")),
                        role_title=str(entry.get("role_title", "")),
                        responsibilities=self._strlist(entry.get("responsibilities", [])),
                        decision_rights=self._strlist(entry.get("decision_rights", [])),
                        accountability_owner_for=self._strlist(
                            entry.get("accountability_owner_for", [])
                        ),
                    )
                )
            except Exception as exc:
                log.warning(
                    "Dropping malformed role assignment (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        named = {ra.agent_name for ra in assignments}
        for agent in request.agents:
            if agent.name not in named:
                assignments.append(
                    RoleAssignment(
                        agent_name=agent.name,
                        role_title=agent.description or f"{agent.name} (role to be defined)",
                        responsibilities=agent.deliverables
                        or ["(responsibilities to be specified)"],
                        decision_rights=agent.decision_rights or [],
                    )
                )

        return RolesSection(
            role_assignments=assignments,
            raci_summary=str(data.get("raci_summary", "")),
        )

    def _build_processes(self, data: dict[str, Any]) -> ProcessesSection:
        return ProcessesSection(
            decision_protocol=str(
                data.get("decision_protocol")
                or "Consensus among agents; fallback to orchestrator if unresolved."
            ),
            escalation_path=self._strlist(data.get("escalation_path", []))
            or ["agent peer review", "orchestrator", "human operator"],
            abandonment_criteria=self._strlist(data.get("abandonment_criteria", []))
            or [
                "task exceeds 3x estimated time",
                "no progress for two consecutive rounds",
            ],
            communication_cadence=str(
                data.get("communication_cadence") or "Per-step structured message exchange."
            ),
            review_cadence=str(data.get("review_cadence", "")),
            artifact_storage=str(data.get("artifact_storage", "")),
        )

    def _build_interactions(self, data: dict[str, Any]) -> InteractionsSection:
        return InteractionsSection(
            disagreement_norms=self._strlist(data.get("disagreement_norms", []))
            or [
                "Disagreement must be expressed as structured dissent before consensus.",
                "No agent may agree without first acknowledging the prior proposal.",
            ],
            feedback_format=str(data.get("feedback_format") or "Plus/Delta"),
            conflict_resolution=str(
                data.get("conflict_resolution")
                or "Surface to orchestrator; orchestrator weighs evidence and decides."
            ),
            voice_and_turn_taking=self._strlist(data.get("voice_and_turn_taking", [])),
            psychological_safety_commitments=self._strlist(
                data.get("psychological_safety_commitments", [])
            ),
        )

    # --- Helpers -------------------------------------------------------

    @staticmethod
    def _strlist(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, (str, int, float))]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _compute_completeness(self, agreement: WorkingAgreement) -> float:
        """Deterministic [0,1] score of how complete the agreement is."""
        score = 0.0
        # Goals.
        if agreement.goals.primary_goal:
            score += 0.05
        if agreement.goals.measurable_success_criteria:
            score += 0.10
        if agreement.goals.kill_criteria:
            score += 0.10
        # Roles.
        if agreement.roles.role_assignments:
            score += 0.10
            n_with_decision_rights = sum(
                1 for ra in agreement.roles.role_assignments if ra.decision_rights
            )
            score += 0.10 * (n_with_decision_rights / max(1, len(agreement.roles.role_assignments)))
        if agreement.roles.raci_summary:
            score += 0.05
        # Processes.
        if agreement.processes.decision_protocol:
            score += 0.05
        if agreement.processes.escalation_path:
            score += 0.10
        if agreement.processes.abandonment_criteria:
            score += 0.10
        if agreement.processes.communication_cadence:
            score += 0.05
        # Interactions.
        if agreement.interactions.disagreement_norms:
            score += 0.05
        if agreement.interactions.feedback_format:
            score += 0.05
        if agreement.interactions.psychological_safety_commitments:
            score += 0.10
        return round(max(0.0, min(1.0, score)), 4)

    def _classify_profile_pattern(
        self,
        agreement: WorkingAgreement,
        request: TeamSetupRequest,
    ) -> GRPIProfilePattern:
        # Single agent (shouldn't happen post-validation, but defensive).
        if len(agreement.roles.role_assignments) < 2:
            return "single_agent_team"

        # Missing kill criteria.
        if not agreement.goals.kill_criteria:
            return "missing_kill_criteria"

        # Missing escalation path.
        if not agreement.processes.escalation_path:
            return "missing_escalation_path"

        # Ambiguous decision rights.
        n_with_decision_rights = sum(
            1 for ra in agreement.roles.role_assignments if ra.decision_rights
        )
        if n_with_decision_rights < len(agreement.roles.role_assignments):
            return "ambiguous_decision_rights"

        # Per-dimension weakness.
        if not agreement.goals.measurable_success_criteria:
            return "weak_goals"
        if not agreement.processes.decision_protocol:
            return "weak_processes"
        if not agreement.interactions.disagreement_norms:
            return "weak_interactions"

        # Framework misfit (heuristic).
        if request.framework and not agreement.framework:
            return "framework_misfit"

        if agreement.completeness_score >= 0.85:
            return "complete_balanced"
        return "indeterminate"

    def _build_composition_handoff(
        self,
        request: TeamSetupRequest,
        agreement: WorkingAgreement,
    ) -> ComposedPatternHandoff:
        downstream, rationale = recommended_downstream(agreement, request)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "profile_pattern": agreement.profile_pattern,
            "framework": request.framework,
            "completeness_score": agreement.completeness_score,
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[GRPIIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            target: str = cast(str, iv.target_dimension)
            pb = find_playbook_for_intervention(target, iv.intervention_type)
            if pb is not None and (pb.dimension, pb.failure_mode) not in attached:
                attached[(pb.dimension, pb.failure_mode)] = pb
        return list(attached.values())


# v0.0.x backward-compat alias.
GRPIWorkingAgreementGenerator = GRPIWorkingAgreementAnalyzer


class GRPIWorkingAgreementAnalyzerAsync:
    """Async mirror of :class:`GRPIWorkingAgreementAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: GRPIMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: GRPIMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        request: TeamSetupRequest,
        *,
        mode: GRPIMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> WorkingAgreement:
        active_mode: GRPIMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = GRPIWorkingAgreementAnalyzer(
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


_legacy_log = logging.getLogger("agentcity.grpi.generator")
_legacy_log.addHandler(logging.NullHandler())
