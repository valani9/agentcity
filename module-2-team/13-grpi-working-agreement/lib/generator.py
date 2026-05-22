"""
GRPIWorkingAgreementGenerator: generates a structured GRPI working
agreement (Beckhard 1972) from a team-setup request.

Pipeline:
  1. Validate the request (non-empty task, ≥2 agents, no duplicate names)
  2. Single LLM pass producing a structured JSON working agreement
  3. Coerce JSON into typed Pydantic models, dropping malformed sub-objects
     and falling back to safe defaults where required fields are missing

Unlike most AgentCity patterns, this one is generative rather than
diagnostic — it consumes a request and produces a contract.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

from agentcity.aar._retry import with_retry

from .prompts import AGREEMENT_GENERATION_PROMPT, GRPI_SYSTEM_PROMPT
from .schema import (
    GoalsSection,
    InteractionsSection,
    ProcessesSection,
    RoleAssignment,
    RolesSection,
    TeamSetupRequest,
    WorkingAgreement,
)

log = logging.getLogger("agentcity.grpi.generator")


class LLMClient(Protocol):
    """Minimal LLM interface; matches the AAR Generator's LLMClient."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class GRPIWorkingAgreementGenerator:
    """Generate a structured GRPI working agreement from a team setup request."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def generate(self, request: TeamSetupRequest) -> WorkingAgreement:
        """Produce a GRPI working agreement for the given request.

        Raises:
            ValueError: if the request fails minimal sanity checks
                (empty task, fewer than 2 agents, duplicate agent names).
        """
        self._validate_request(request)

        started = time.monotonic()
        log.info(
            "Generating GRPI working agreement for team %s (agents=%d)",
            request.team_id or "<unknown>",
            len(request.agents),
        )

        data = self._llm_pass(request)
        agreement = self._build_agreement(request, data)

        elapsed = time.monotonic() - started
        log.info(
            "GRPI agreement for team %s generated in %.2fs",
            request.team_id or "<unknown>",
            elapsed,
        )
        return agreement

    # --- Input validation ----------------------------------------------

    def _validate_request(self, request: TeamSetupRequest) -> None:
        if not request.task or not request.task.strip():
            raise ValueError("TeamSetupRequest.task cannot be empty.")
        if len(request.agents) < 2:
            raise ValueError(
                "TeamSetupRequest.agents must contain at least 2 agents. "
                "GRPI describes team dynamics; for single-agent setup, use a "
                "regular system prompt."
            )
        names = [agent.name for agent in request.agents]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate agent names in TeamSetupRequest.agents: {names}")

    # --- LLM pass ------------------------------------------------------

    def _llm_pass(self, request: TeamSetupRequest) -> dict[str, Any]:
        agents_text = "\n".join(
            f"  - {a.name}: {a.description or '(no description provided)'}" for a in request.agents
        )
        constraints_text = (
            "\n".join(f"  - {c}" for c in request.constraints) or "  (none specified)"
        )
        success_text = (
            "\n".join(f"  - {c}" for c in request.success_criteria)
            or "  (none specified; please derive)"
        )
        kill_text = (
            "\n".join(f"  - {c}" for c in request.kill_criteria)
            or "  (none specified; please derive)"
        )
        prompt = AGREEMENT_GENERATION_PROMPT.format(
            task=request.task,
            team_id=request.team_id or "(unnamed)",
            framework=request.framework or "(unspecified)",
            agents=agents_text,
            constraints=constraints_text,
            success_criteria=success_text,
            kill_criteria=kill_text,
        )
        raw = self._complete(prompt, system=GRPI_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    # --- Synthesis -----------------------------------------------------

    def _build_agreement(self, request: TeamSetupRequest, data: dict[str, Any]) -> WorkingAgreement:
        goals = self._build_goals(data.get("goals", {}), request)
        roles = self._build_roles(data.get("roles", {}), request)
        processes = self._build_processes(data.get("processes", {}))
        interactions = self._build_interactions(data.get("interactions", {}))

        return WorkingAgreement(
            team_id=request.team_id,
            task=request.task,
            goals=goals,
            roles=roles,
            processes=processes,
            interactions=interactions,
            generator_model=self.model,
            framework=request.framework,
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

        # Ensure every requested agent has a role assignment.
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
            or ["task exceeds 3x estimated time", "no progress for two consecutive rounds"],
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
            feedback_format=str(data.get("feedback_format") or "Plus/Delta (Brené Brown style)"),
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
        """Coerce loose LLM list output into a list of strings."""
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, (str, int, float))]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        """Best-effort JSON-object extraction from an LLM response."""
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
        for match in _FENCE_RE.finditer(text):
            body = match.group(1).strip()
            if body:
                candidates.append(body)
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        log.warning(
            "Failed to parse JSON object from GRPI LLM response (len=%d). "
            "Returning empty; downstream will fall back to safe defaults.",
            len(text),
        )
        return {}
