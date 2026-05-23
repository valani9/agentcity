"""Comprehensive v0.2.0 tests for the upgraded Process Gain/Loss diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentcity.aar import InMemoryTelemetrySink, set_default_sink
from agentcity.process_gain_loss import (
    PLAYBOOKS,
    PROCESS_COMPOSITION,
    PROCESS_FACTORS,
    PROCESS_MODES,
    PROCESS_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    BaselineComparison,
    IndividualBaseline,
    ProcessGainLossAnalyzer,
    ProcessGainLossAnalyzerAsync,
    ProcessGainLossDetection,
    ProcessGainLossDetector,
    ProcessTrace,
    TeamResult,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_loss,
)


def _trace(
    team_quality: float = 0.5, best_quality: float = 0.8, framework: str | None = None
) -> ProcessTrace:
    return ProcessTrace(
        trace_id="t",
        task="Write a research report.",
        individual_baselines=[
            IndividualBaseline(agent_name="alpha", output_summary="x", quality_score=best_quality),
            IndividualBaseline(agent_name="beta", output_summary="y", quality_score=0.6),
        ],
        team_result=TeamResult(
            agents=["alpha", "beta"],
            output_summary="team output",
            quality_score=team_quality,
        ),
        interaction_log="alpha: ...\nbeta: ok\n",
        outcome="completed",
        success=False,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from agentcity.aar import StubClient

    return StubClient(canned)


def _ev(factor: str, score: float = 0.6) -> dict[str, object]:
    return {
        "factor": factor,
        "score": score,
        "severity": "medium",
        "explanation": f"{factor} ev",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _factors_payload() -> str:
    return json.dumps(
        {
            "contributing_factors": [
                _ev("coordination_cost", 0.7),
                _ev("social_loafing", 0.3),
                _ev("groupthink", 0.2),
                _ev("handoff_loss", 0.3),
                _ev("context_dilution", 0.2),
                _ev("consensus_dilution", 0.2),
            ]
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_factor": "coordination_cost",
                "intervention_type": "smaller_team",
                "description": "Reduce team to 2.",
                "suggested_implementation": "Drop beta.",
                "estimated_impact": "high",
                "rationale": "x",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_factors_payload())
    obj["top_intervention"] = {
        "target_factor": "coordination_cost",
        "intervention_type": "smaller_team",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _log_audit_payload() -> str:
    return json.dumps(
        {
            "n_handoffs": 5,
            "n_silent_agents": 1,
            "n_premature_consensus": 0,
            "n_context_loss_events": 2,
            "dominant_factor": "coordination_cost",
            "notes": "Heavy handoff load.",
        }
    )


def _counterfactual_payload() -> str:
    return json.dumps(
        {
            "nominal_group_quality_estimate": 0.7,
            "nominal_minus_team": 0.2,
            "would_recommend_individual": True,
            "explanation": "Best individual would have outperformed team.",
        }
    )


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(PROCESS_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(PROCESS_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_six_factors(self) -> None:
        assert len(PROCESS_FACTORS) == 6

    def test_severity_polarity(self) -> None:
        # Positive (gain) = low severity; negative (loss) = high severity.
        assert severity_from_loss(0.5) == "none"
        assert severity_from_loss(-0.9) == "critical"

    def test_legacy_alias(self) -> None:
        assert ProcessGainLossDetector is ProcessGainLossAnalyzer


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_factors_payload(), _interventions_payload()])
        det = ProcessGainLossAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.process_quality == "process-loss"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = ProcessGainLossAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _factors_payload(),
                _log_audit_payload(),
                _counterfactual_payload(),
                _interventions_payload(),
            ]
        )
        det = ProcessGainLossAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert det.interaction_log_audit is not None
        assert det.counterfactual_audit is not None

    def test_process_gain_skips_interventions(self) -> None:
        # team_quality > best_individual.
        stub = _stub([_factors_payload()])
        det = ProcessGainLossAnalyzer(stub).run(_trace(team_quality=0.9, best_quality=0.7))  # type: ignore[arg-type]
        assert det.process_quality == "process-gain"
        assert det.interventions == []


class TestProfilePattern:
    def test_coordination_dominant(self) -> None:
        stub = _stub([_factors_payload(), _interventions_payload()])
        det = ProcessGainLossAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "coordination_dominant_loss"

    def test_process_gain_balanced(self) -> None:
        stub = _stub([_factors_payload()])
        det = ProcessGainLossAnalyzer(stub).run(_trace(team_quality=0.9, best_quality=0.7))  # type: ignore[arg-type]
        assert det.profile_pattern == "process_gain_balanced"


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_factors_payload(), _interventions_payload()])
        det = ProcessGainLossAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "process_gain_loss"
            assert ev.run_id == det.run_id


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(PROCESS_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "process_gain_balanced" in keys
        assert "coordination_dominant_loss" in keys

    def test_coord_recommends_grpi(self) -> None:
        det = ProcessGainLossDetection(
            trace_id="t",
            process_quality="process-loss",
            gain_loss_score=-0.3,
            individual_best_quality=0.8,
            individual_best_agent="alpha",
            individual_mean_quality=0.7,
            team_quality=0.5,
            contributing_factors=[],
            interventions=[],
            profile_pattern="coordination_dominant_loss",
        )
        recs, _ = recommended_downstream(det)
        assert "agentcity.grpi" in recs

    def test_upstream_includes_lewin(self) -> None:
        up = recommended_upstream()
        assert "agentcity.lewin" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("coordination_cost", "high_overhead") in keys
        assert ("groupthink", "premature_consensus") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("coordination_cost", "smaller_team")
        assert pb is not None
        assert pb.failure_mode == "high_overhead"


class TestCalibration:
    def _det(self) -> ProcessGainLossDetection:
        return ProcessGainLossDetection(
            trace_id="t",
            process_quality="process-loss",
            gain_loss_score=-0.3,
            individual_best_quality=0.8,
            individual_best_agent="alpha",
            individual_mean_quality=0.7,
            team_quality=0.5,
            contributing_factors=[],
            interventions=[],
            run_id="r-1",
        )

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = self._det()
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.process_quality == "process-loss"

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
        stub = _AsyncStub([_factors_payload(), _interventions_payload()])
        analyzer = ProcessGainLossAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> ProcessGainLossDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_factors_payload(), _interventions_payload()])
        det = ProcessGainLossAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Process Gain/Loss" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md
