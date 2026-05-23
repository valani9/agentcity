"""Comprehensive v0.2.0 tests for the upgraded Cognitive Reappraisal diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


from agentcity.aar import InMemoryTelemetrySink, set_default_sink
from agentcity.cognitive_reappraisal import (
    PLAYBOOKS,
    REAPPRAISAL_COMPOSITION,
    REAPPRAISAL_MODES,
    REAPPRAISAL_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentRegulationTrace,
    BaselineComparison,
    ReappraisalAnalyzer,
    ReappraisalAnalyzerAsync,
    ReappraisalDetector,
    RegulationDetection,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_adaptivity,
)


def _trace(
    *,
    user_input: str = "I JUST WANT THIS FIXED!!!",
    user_emotion_label: str = "angry",
    user_emotion_intensity: float = 0.9,
    agent_response: str = "I understand your concern. Per our policy, billing is final.",
    agent_internal_state: str = "User is being unreasonable. Apply policy.",
    outcome: str = "User escalated to manager.",
    success: bool = False,
    pushback_detected: bool = False,
    framework: str | None = None,
) -> AgentRegulationTrace:
    return AgentRegulationTrace(
        agent_id="t",
        model_name="m",
        user_input=user_input,
        user_emotion_label=user_emotion_label,  # type: ignore[arg-type]
        user_emotion_intensity=user_emotion_intensity,
        agent_response=agent_response,
        agent_internal_state=agent_internal_state,
        outcome=outcome,
        success=success,
        pushback_detected=pushback_detected,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from agentcity.aar import StubClient

    return StubClient(canned)


def _strategy_payload(
    reapp: float = 0.1,
    supp: float = 0.7,
    rum: float = 0.2,
    avoid: float = 0.4,
    expr: float = 0.0,
    dominant: str = "suppression",
    adaptivity: str = "maladaptive",
    rumination_flavor: str = "none",
) -> str:
    return json.dumps(
        {
            "strategy_evidence": [
                {
                    "strategy": "reappraisal",
                    "score": reapp,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.7,
                },
                {
                    "strategy": "suppression",
                    "score": supp,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.8,
                },
                {
                    "strategy": "rumination",
                    "score": rum,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.6,
                    "rumination_flavor": rumination_flavor,
                },
                {
                    "strategy": "avoidance",
                    "score": avoid,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.6,
                },
                {
                    "strategy": "expression",
                    "score": expr,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.5,
                },
                {
                    "strategy": "none",
                    "score": 0.0,
                    "explanation": "x",
                    "evidence_quotes": [],
                    "confidence": 0.5,
                },
            ],
            "dominant_strategy": dominant,
            "adaptivity": adaptivity,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_strategy": "suppression",
                "direction": "decrease",
                "intervention_type": "remove_suppression_pattern",
                "description": "Remove boilerplate opener.",
                "suggested_implementation": "Forbid 'I understand'.",
                "estimated_impact": "high",
                "rationale": "x",
            }
        ]
    )


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(REAPPRAISAL_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_twelve(self) -> None:
        assert len(REAPPRAISAL_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_adaptivity("adaptive") == "none"
        assert severity_from_adaptivity("maladaptive", "rumination") == "critical"
        assert severity_from_adaptivity("maladaptive", "suppression") == "high"

    def test_legacy_alias_works(self) -> None:
        assert ReappraisalDetector is ReappraisalAnalyzer


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_strategy_payload(), _interventions_payload()])
        det = ReappraisalAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.dominant_strategy == "suppression"

    def test_quick_one_call(self) -> None:
        payload = json.dumps(
            {
                "strategy_evidence": json.loads(_strategy_payload())["strategy_evidence"],
                "dominant_strategy": "suppression",
                "adaptivity": "maladaptive",
                "top_intervention": {
                    "target_strategy": "suppression",
                    "direction": "decrease",
                    "intervention_type": "remove_suppression_pattern",
                    "description": "x",
                    "suggested_implementation": "y",
                    "rationale": "z",
                },
            }
        )
        stub = _stub([payload])
        det = ReappraisalAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1

    def test_standard_adaptive_skips_interventions(self) -> None:
        payload = _strategy_payload(
            reapp=0.8, supp=0.1, rum=0.05, avoid=0.05, dominant="reappraisal", adaptivity="adaptive"
        )
        stub = _stub([payload])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.adaptivity == "adaptive"
        assert det.interventions == []


class TestProfilePattern:
    def test_suppression_dominant(self) -> None:
        stub = _stub([_strategy_payload(), _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "suppression_dominant"

    def test_suppression_under_pushback(self) -> None:
        stub = _stub([_strategy_payload(supp=0.6), _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace(pushback_detected=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "suppression_under_pushback"

    def test_reappraisal_skilled(self) -> None:
        payload = _strategy_payload(
            reapp=0.8, supp=0.1, rum=0.05, avoid=0.1, dominant="reappraisal", adaptivity="adaptive"
        )
        stub = _stub([payload])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "reappraisal_skilled"

    def test_rumination_brooding(self) -> None:
        payload = _strategy_payload(
            reapp=0.1,
            supp=0.1,
            rum=0.7,
            avoid=0.1,
            dominant="rumination",
            adaptivity="maladaptive",
            rumination_flavor="brooding",
        )
        stub = _stub([payload, _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "rumination_brooding"

    def test_avoidance_pivot(self) -> None:
        payload = _strategy_payload(
            reapp=0.1, supp=0.1, rum=0.1, avoid=0.7, dominant="avoidance", adaptivity="maladaptive"
        )
        stub = _stub([payload, _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "avoidance_pivot"


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_strategy_payload(), _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "cognitive_reappraisal"
            assert ev.run_id == det.run_id


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(REAPPRAISAL_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "suppression_dominant" in keys
        assert "suppression_under_pushback" in keys

    def test_suppression_recommends_devils_advocate(self) -> None:
        det = RegulationDetection(
            strategy_evidence=[],
            dominant_strategy="suppression",
            adaptivity="maladaptive",
            interventions=[],
            profile_pattern="suppression_dominant",
        )
        recs, _ = recommended_downstream(det)
        assert "agentcity.devils_advocate" in recs

    def test_upstream_includes_goleman(self) -> None:
        up = recommended_upstream()
        assert "agentcity.goleman_ei" in up
        assert "agentcity.johari" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("suppression", "boilerplate_acknowledgment") in keys
        assert ("suppression", "pushback_capitulation") in keys
        assert ("rumination", "negative_loop") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("suppression", "remove_suppression_pattern")
        assert pb is not None
        assert pb.failure_mode == "boilerplate_acknowledgment"


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = RegulationDetection(
            strategy_evidence=[],
            dominant_strategy="suppression",
            adaptivity="maladaptive",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.dominant_strategy == "suppression"

    def test_drift_returns_comparison(self) -> None:
        det = RegulationDetection(
            strategy_evidence=[],
            dominant_strategy="suppression",
            adaptivity="maladaptive",
            interventions=[],
        )
        cmp = compare_to_baseline(det, det)
        assert isinstance(cmp, BaselineComparison)


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
        stub = _AsyncStub([_strategy_payload(), _interventions_payload()])
        analyzer = ReappraisalAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> RegulationDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_strategy_payload(), _interventions_payload()])
        det = ReappraisalAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Cognitive Reappraisal" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md
