"""Comprehensive v0.2.0 tests for the upgraded GRPI diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.grpi import (
    DIMENSIONS,
    GRPI_COMPOSITION,
    GRPI_MODES,
    GRPI_PROFILE_PATTERNS,
    PLAYBOOKS,
    SEVERITY_ORDER,
    AgentRole,
    BaselineComparison,
    GoalsSection,
    GRPIWorkingAgreementAnalyzer,
    GRPIWorkingAgreementAnalyzerAsync,
    GRPIWorkingAgreementGenerator,
    InteractionsSection,
    ProcessesSection,
    RolesSection,
    TeamSetupRequest,
    WorkingAgreement,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_completeness,
)


def _request(framework: str | None = None) -> TeamSetupRequest:
    return TeamSetupRequest(
        team_id="t",
        task="Build a Q3 marketing campaign in 14 days.",
        agents=[
            AgentRole(name="researcher", description="Market research."),
            AgentRole(name="strategist", description="Channel selection."),
        ],
        constraints=["Budget $20K"],
        success_criteria=["Launch by Aug 1"],
        kill_criteria=["No leads after 7 days"],
        framework=framework,
    )


def _agreement_payload() -> str:
    return json.dumps(
        {
            "goals": {
                "primary_goal": "Launch Q3 campaign.",
                "measurable_success_criteria": ["Launch by Aug 1", "5+ leads"],
                "kill_criteria": ["No leads after 7 days"],
                "scope_boundaries": ["B2B only"],
                "deliverables": ["Campaign brief"],
            },
            "roles": {
                "role_assignments": [
                    {
                        "agent_name": "researcher",
                        "role_title": "Market Researcher",
                        "responsibilities": ["Survey market"],
                        "decision_rights": ["Sample size"],
                        "accountability_owner_for": ["Survey results"],
                    },
                    {
                        "agent_name": "strategist",
                        "role_title": "Strategist",
                        "responsibilities": ["Pick channels"],
                        "decision_rights": ["Channel mix"],
                        "accountability_owner_for": ["Channel plan"],
                    },
                ],
                "raci_summary": "Researcher owns data; strategist owns channels.",
            },
            "processes": {
                "decision_protocol": "Consensus; fallback to orchestrator.",
                "escalation_path": ["peer review", "orchestrator", "human"],
                "abandonment_criteria": ["No progress for 2 rounds"],
                "communication_cadence": "Daily standup",
                "review_cadence": "After each milestone",
                "artifact_storage": "Shared docs",
            },
            "interactions": {
                "disagreement_norms": ["Dissent before consensus"],
                "feedback_format": "plus/delta",
                "conflict_resolution": "Surface to orchestrator",
                "voice_and_turn_taking": ["Round-robin"],
                "psychological_safety_commitments": ["No blame"],
            },
        }
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _role_fit_payload() -> str:
    return json.dumps(
        [
            {
                "agent_name": "researcher",
                "fit_score": 0.85,
                "ambiguous_decision_rights": [],
                "overlapping_responsibilities": [],
                "notes": "Clean assignment.",
            }
        ]
    )


def _dysfunction_payload() -> str:
    return json.dumps(
        {
            "prevents_absence_of_trust": True,
            "prevents_fear_of_conflict": True,
            "prevents_lack_of_commitment": True,
            "prevents_avoidance_of_accountability": True,
            "prevents_inattention_to_results": True,
            "notes": "Strong agreement.",
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_dimension": "goals",
                "intervention_type": "tighten_goals",
                "description": "Add more specific criteria.",
                "suggested_implementation": "Edit goals section.",
                "estimated_impact": "medium",
                "rationale": "x",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(GRPI_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(GRPI_PROFILE_PATTERNS) == 11

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_dimensions(self) -> None:
        assert set(DIMENSIONS) == {"goals", "roles", "processes", "interactions"}

    def test_severity_polarity(self) -> None:
        assert severity_from_completeness(1.0) == "none"
        assert severity_from_completeness(0.0) == "critical"

    def test_legacy_alias(self) -> None:
        assert GRPIWorkingAgreementGenerator is GRPIWorkingAgreementAnalyzer


class TestModes:
    def test_quick_one_call(self) -> None:
        stub = _stub([_agreement_payload()])
        det = GRPIWorkingAgreementAnalyzer(stub, mode="quick").run(_request())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert det.goals.primary_goal == "Launch Q3 campaign."

    def test_standard_one_call(self) -> None:
        stub = _stub([_agreement_payload()])
        det = GRPIWorkingAgreementAnalyzer(stub, mode="standard").run(_request())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 1

    def test_forensic_four_calls(self) -> None:
        # generation (1) + role_fit + dysfunction + interventions = 4.
        stub = _stub(
            [
                _agreement_payload(),
                _role_fit_payload(),
                _dysfunction_payload(),
                _interventions_payload(),
            ]
        )
        det = GRPIWorkingAgreementAnalyzer(stub, mode="forensic").run(_request())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.role_fit_audits) == 1
        assert det.dysfunction_prevention is not None


class TestProfilePattern:
    def test_complete_balanced(self) -> None:
        stub = _stub([_agreement_payload()])
        det = GRPIWorkingAgreementAnalyzer(stub).run(_request())  # type: ignore[arg-type]
        assert det.profile_pattern == "complete_balanced"
        assert det.completeness_score >= 0.85


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_agreement_payload()])
        det = GRPIWorkingAgreementAnalyzer(stub).run(_request())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 1
        for ev in sink.events:
            assert ev.pattern == "grpi"
            assert ev.run_id == det.run_id


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(GRPI_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "complete_balanced" in keys
        assert "weak_interactions" in keys

    def test_weak_interactions_recommends_lencioni(self) -> None:
        det = WorkingAgreement(
            team_id="t",
            task="x",
            goals=GoalsSection(
                primary_goal="x",
                measurable_success_criteria=["x"],
            ),
            roles=RolesSection(role_assignments=[]),
            processes=ProcessesSection(
                decision_protocol="x",
                escalation_path=["x"],
                abandonment_criteria=["x"],
                communication_cadence="x",
            ),
            interactions=InteractionsSection(
                disagreement_norms=[],
                feedback_format="x",
                conflict_resolution="x",
            ),
            profile_pattern="weak_interactions",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.lencioni" in recs

    def test_upstream_includes_lewin(self) -> None:
        up = recommended_upstream()
        assert "vstack.lewin" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("goals", "missing_kill_criteria") in keys
        assert ("roles", "ambiguous_decision_rights") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("goals", "tighten_goals")
        assert pb is not None
        assert pb.failure_mode == "vague_primary_goal"


class TestCalibration:
    def _agreement(self) -> WorkingAgreement:
        stub = _stub([_agreement_payload()])
        return GRPIWorkingAgreementAnalyzer(stub).run(_request())  # type: ignore[arg-type]

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        a = self._agreement()
        path = tmp_path / "baseline.json"
        record_baseline(a, path)
        restored = load_baseline(path)
        assert restored.profile_pattern == a.profile_pattern

    def test_drift_returns_comparison(self) -> None:
        a = self._agreement()
        cmp = compare_to_baseline(a, a)
        assert isinstance(cmp, BaselineComparison)
        assert cmp.drift_severity == "none"


class _AsyncStub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.last_usage = None

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self._responses:
            raise RuntimeError("exhausted")
        return self._responses.pop(0)


class TestAsync:
    def test_arun_returns_agreement(self) -> None:
        stub = _AsyncStub([_agreement_payload()])
        analyzer = GRPIWorkingAgreementAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> WorkingAgreement:
            return await analyzer.arun(_request())

        det = asyncio.run(call())
        assert det.mode == "standard"


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_agreement_payload()])
        det = GRPIWorkingAgreementAnalyzer(stub).run(_request(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Working Agreement" in md
        assert "Mode:" in md
        assert "Completeness:" in md
        assert "Composition Handoff" in md
