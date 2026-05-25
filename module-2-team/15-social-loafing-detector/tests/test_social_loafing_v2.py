"""Comprehensive v0.2.0 tests for the upgraded Social Loafing diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.social_loafing import (
    PLAYBOOKS,
    SEVERITY_ORDER,
    SOCIAL_LOAFING_COMPOSITION,
    SOCIAL_LOAFING_MODES,
    SOCIAL_LOAFING_PROFILE_PATTERNS,
    AgentMessage,
    BaselineComparison,
    MultiAgentTaskTrace,
    SocialLoafingAnalyzer,
    SocialLoafingAnalyzerAsync,
    SocialLoafingDetection,
    SocialLoafingDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_gini,
)


def _trace(framework: str | None = None) -> MultiAgentTaskTrace:
    return MultiAgentTaskTrace(
        team_id="t",
        task="Write a report.",
        agents=["a", "b"],
        messages=[
            AgentMessage(from_agent="a", message_type="proposal", content="Here's draft 1."),
            AgentMessage(from_agent="b", message_type="rubber_stamp", content="LGTM"),
            AgentMessage(from_agent="a", message_type="decision", content="Shipping."),
        ],
        outcome="Shipped",
        success=True,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _contributions_payload() -> str:
    return json.dumps(
        {
            "agent_contributions": [
                {
                    "agent_name": "a",
                    "contribution_share": 0.9,
                    "substantive_work_count": 2,
                    "cosmetic_work_count": 0,
                    "loafing_score": 0.0,
                    "role": "primary-contributor",
                    "explanation": "did all work",
                    "evidence_quotes": [],
                    "confidence": 0.8,
                },
                {
                    "agent_name": "b",
                    "contribution_share": 0.1,
                    "substantive_work_count": 0,
                    "cosmetic_work_count": 1,
                    "loafing_score": 0.9,
                    "role": "loafer",
                    "explanation": "rubber stamped",
                    "evidence_quotes": [],
                    "confidence": 0.8,
                },
            ],
            "gini_coefficient": 0.6,
            "loafing_quality": "severe-loafing",
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_agent": "b",
                "intervention_type": "individual_accountability",
                "description": "Assign a subgoal.",
                "suggested_implementation": "Edit prompt.",
                "estimated_impact": "high",
                "rationale": "x",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_contributions_payload())
    obj["top_intervention"] = {
        "target_agent": "b",
        "intervention_type": "individual_accountability",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _anonymity_payload() -> str:
    return json.dumps(
        {
            "individual_evaluable": False,
            "task_decomposable": True,
            "contribution_visible": True,
            "cohesion_estimate": 0.5,
            "explanation": "x",
        }
    )


def _free_riding_payload() -> str:
    return json.dumps(
        [
            {
                "loafer_agent": "b",
                "enabling_messages": [1],
                "cosmetic_pattern": "rubber_stamp_chain",
                "severity": "high",
            }
        ]
    )


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(SOCIAL_LOAFING_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(SOCIAL_LOAFING_PROFILE_PATTERNS) == 9

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_gini(0.0) == "none"
        assert severity_from_gini(1.0) == "critical"

    def test_legacy_alias(self) -> None:
        assert SocialLoafingDetector is SocialLoafingAnalyzer


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_contributions_payload(), _interventions_payload()])
        det = SocialLoafingAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = SocialLoafingAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _contributions_payload(),
                _anonymity_payload(),
                _free_riding_payload(),
                _interventions_payload(),
            ]
        )
        det = SocialLoafingAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert det.anonymity_audit is not None
        assert len(det.free_riding_chains) == 1


class TestProfilePattern:
    def test_single_dominant(self) -> None:
        stub = _stub([_contributions_payload(), _interventions_payload()])
        det = SocialLoafingAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "single_dominant_contributor"


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_contributions_payload(), _interventions_payload()])
        det = SocialLoafingAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "social_loafing"
            assert ev.run_id == det.run_id


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(SOCIAL_LOAFING_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "balanced_team" in keys
        assert "all_loafers" in keys

    def test_single_dominant_recommends_grpi(self) -> None:
        det = SocialLoafingDetection(
            team_id="t",
            agent_contributions=[],
            gini_coefficient=0.6,
            loafing_quality="severe-loafing",
            interventions=[],
            profile_pattern="single_dominant_contributor",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.grpi" in recs

    def test_upstream_includes_grpi(self) -> None:
        up = recommended_upstream()
        assert "vstack.grpi" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("loafer", "rubber_stamp") in keys
        assert ("loafer", "silent_majority") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("loafer", "assign_subgoals")
        assert pb is not None
        assert pb.failure_mode == "rubber_stamp"


class TestCalibration:
    def _det(self) -> SocialLoafingDetection:
        return SocialLoafingDetection(
            team_id="t",
            agent_contributions=[],
            gini_coefficient=0.5,
            loafing_quality="severe-loafing",
            interventions=[],
            run_id="r-1",
        )

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = self._det()
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.gini_coefficient == 0.5

    def test_drift_returns_comparison(self) -> None:
        det = self._det()
        cmp = compare_to_baseline(det, det)
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
    def test_arun_returns_detection(self) -> None:
        stub = _AsyncStub([_contributions_payload(), _interventions_payload()])
        analyzer = SocialLoafingAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> SocialLoafingDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_contributions_payload(), _interventions_payload()])
        det = SocialLoafingAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Social Loafing" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md
