"""Tests for the GRPI Working Agreement Generator.

Covers:
  - Schema construction and JSON round-trip
  - Markdown + orchestrator-preamble renderers
  - Validation: empty task, single-agent, duplicate-name rejected
  - End-to-end generation with stub LLM
  - Safe-default fallbacks when LLM returns empty output
  - Every requested agent gets a role assignment even if LLM omits some
"""

from __future__ import annotations

import json

import pytest

from agentcity.grpi import (
    AgentRole,
    GRPIWorkingAgreementGenerator,
    GoalsSection,
    InteractionsSection,
    ProcessesSection,
    RoleAssignment,
    RolesSection,
    TeamSetupRequest,
    WorkingAgreement,
)


def _agents() -> list[AgentRole]:
    return [
        AgentRole(name="alpha", description="Does the first thing."),
        AgentRole(name="beta", description="Does the second thing."),
    ]


def _request(**overrides: object) -> TeamSetupRequest:
    base: dict[str, object] = dict(
        team_id="test-team",
        task="Default test task description.",
        agents=_agents(),
    )
    base.update(overrides)
    return TeamSetupRequest(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestSchemaRoundtrip:
    def test_request_roundtrip(self) -> None:
        req = _request()
        restored = TeamSetupRequest.model_validate_json(req.model_dump_json())
        assert restored.task == req.task
        assert len(restored.agents) == 2

    def test_agreement_markdown_contains_all_grpi_sections(self) -> None:
        agreement = WorkingAgreement(
            team_id="t",
            task="task",
            goals=GoalsSection(
                primary_goal="g",
                measurable_success_criteria=["s1"],
                deliverables=["d1"],
            ),
            roles=RolesSection(
                role_assignments=[
                    RoleAssignment(
                        agent_name="alpha",
                        role_title="r",
                        responsibilities=["r1"],
                        decision_rights=["d1"],
                    )
                ]
            ),
            processes=ProcessesSection(
                decision_protocol="p",
                escalation_path=["x"],
                abandonment_criteria=["a"],
                communication_cadence="c",
            ),
            interactions=InteractionsSection(
                disagreement_norms=["n"],
                feedback_format="plus/delta",
                conflict_resolution="r",
            ),
        )
        md = agreement.to_markdown()
        assert "## G — Goals" in md
        assert "## R — Roles" in md
        assert "## P — Processes" in md
        assert "## I — Interactions" in md

    def test_orchestrator_preamble_contains_all_dimensions(self) -> None:
        agreement = WorkingAgreement(
            team_id="t",
            task="task",
            goals=GoalsSection(
                primary_goal="primary",
                measurable_success_criteria=["s1", "s2"],
            ),
            roles=RolesSection(
                role_assignments=[
                    RoleAssignment(
                        agent_name="alpha",
                        role_title="r",
                        responsibilities=["r1"],
                        decision_rights=[],
                    )
                ]
            ),
            processes=ProcessesSection(
                decision_protocol="proto",
                escalation_path=["a", "b"],
                abandonment_criteria=["c"],
                communication_cadence="cadence",
            ),
            interactions=InteractionsSection(
                disagreement_norms=["n1"],
                feedback_format="plus/delta",
                conflict_resolution="r",
            ),
        )
        preamble = agreement.to_orchestrator_preamble()
        assert "primary" in preamble
        assert "proto" in preamble
        assert "alpha" in preamble
        assert "plus/delta" in preamble
        assert "a -> b" in preamble


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        gen = GRPIWorkingAgreementGenerator(_Stub(["{}"]))
        with pytest.raises(ValueError, match="task"):
            gen.generate(_request(task=""))

    def test_single_agent_rejected(self) -> None:
        gen = GRPIWorkingAgreementGenerator(_Stub(["{}"]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            gen.generate(_request(agents=[AgentRole(name="solo")]))

    def test_duplicate_agent_names_rejected(self) -> None:
        gen = GRPIWorkingAgreementGenerator(_Stub(["{}"]))
        dupes = [AgentRole(name="alpha"), AgentRole(name="alpha")]
        with pytest.raises(ValueError, match="Duplicate"):
            gen.generate(_request(agents=dupes))


class TestGeneration:
    def test_end_to_end_with_full_canned_response(self) -> None:
        response = json.dumps(
            {
                "goals": {
                    "primary_goal": "ship the thing",
                    "measurable_success_criteria": ["3 alternatives compared", "launch by D14"],
                    "scope_boundaries": ["in: ads", "out: PR"],
                    "deliverables": ["concept memo D4"],
                    "kill_criteria": ["budget >125% cap"],
                },
                "roles": {
                    "role_assignments": [
                        {
                            "agent_name": "alpha",
                            "role_title": "lead",
                            "responsibilities": ["plan"],
                            "decision_rights": ["scope"],
                            "accountability_owner_for": ["plan"],
                        },
                        {
                            "agent_name": "beta",
                            "role_title": "critic",
                            "responsibilities": ["challenge"],
                            "decision_rights": ["veto"],
                            "accountability_owner_for": ["dissent"],
                        },
                    ],
                    "raci_summary": "alpha R, beta A",
                },
                "processes": {
                    "decision_protocol": "consensus",
                    "escalation_path": ["orchestrator", "human"],
                    "abandonment_criteria": ["no progress 2 rounds"],
                    "communication_cadence": "per-step",
                    "review_cadence": "AAR at D14",
                    "artifact_storage": "shared memory",
                },
                "interactions": {
                    "disagreement_norms": ["dissent before consensus"],
                    "feedback_format": "plus/delta",
                    "conflict_resolution": "escalate to orchestrator",
                    "voice_and_turn_taking": ["every agent speaks per round"],
                    "psychological_safety_commitments": ["objections rewarded"],
                },
            }
        )
        stub = _Stub([response])
        gen = GRPIWorkingAgreementGenerator(stub, model="test-model")
        agreement = gen.generate(_request())

        assert len(stub.calls) == 1
        assert agreement.goals.primary_goal == "ship the thing"
        assert len(agreement.roles.role_assignments) == 2
        assert agreement.processes.decision_protocol == "consensus"
        assert "dissent before consensus" in agreement.interactions.disagreement_norms

    def test_safe_defaults_when_llm_returns_empty(self) -> None:
        gen = GRPIWorkingAgreementGenerator(_Stub([""]))
        agreement = gen.generate(_request())
        # Fallbacks should still produce a usable agreement.
        assert agreement.goals.primary_goal  # falls back to the request task
        assert len(agreement.roles.role_assignments) == 2  # filled from request
        assert agreement.processes.decision_protocol  # safe default
        assert len(agreement.interactions.disagreement_norms) >= 1  # safe defaults

    def test_missing_role_in_llm_output_is_backfilled(self) -> None:
        """If the LLM forgets one of the requested agents, the generator
        backfills a role assignment from the request data."""
        response = json.dumps(
            {
                "goals": {
                    "primary_goal": "g",
                    "measurable_success_criteria": ["s"],
                    "deliverables": ["d"],
                },
                "roles": {
                    "role_assignments": [
                        {
                            "agent_name": "alpha",
                            "role_title": "lead",
                            "responsibilities": ["plan"],
                            "decision_rights": [],
                        }
                        # beta is missing from LLM output
                    ]
                },
                "processes": {
                    "decision_protocol": "consensus",
                    "escalation_path": ["orch"],
                    "abandonment_criteria": ["a"],
                    "communication_cadence": "c",
                },
                "interactions": {
                    "disagreement_norms": ["n"],
                    "feedback_format": "plus/delta",
                    "conflict_resolution": "r",
                },
            }
        )
        gen = GRPIWorkingAgreementGenerator(_Stub([response]))
        agreement = gen.generate(_request())
        agent_names = {ra.agent_name for ra in agreement.roles.role_assignments}
        assert agent_names == {"alpha", "beta"}

    def test_markdown_includes_all_sections_in_real_output(self) -> None:
        gen = GRPIWorkingAgreementGenerator(_Stub([""]))
        agreement = gen.generate(_request())
        md = agreement.to_markdown()
        for header in ["## G — Goals", "## R — Roles", "## P — Processes", "## I — Interactions"]:
            assert header in md
