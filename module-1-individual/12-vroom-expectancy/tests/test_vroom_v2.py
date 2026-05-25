"""Comprehensive v0.2.0 tests for the upgraded Vroom diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.vroom_expectancy import (
    PLAYBOOKS,
    SEVERITY_ORDER,
    VROOM_COMPOSITION,
    VROOM_MODES,
    VROOM_PROFILE_PATTERNS,
    VROOM_TERMS,
    AgentExpectancyTrace,
    BaselineComparison,
    VroomDetection,
    VroomExpectancyAnalyzer,
    VroomExpectancyAnalyzerAsync,
    VroomExpectancyCalculator,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_motivation,
)


def _trace(
    *,
    task: str = "Debug the entire codebase.",
    task_class: str = "code_generation",
    outcome: str = "Bugs unfound.",
    success: bool = False,
    system_prompt: str = "Find all bugs. No one will review carefully.",
    framework: str | None = None,
) -> AgentExpectancyTrace:
    return AgentExpectancyTrace(
        agent_id="t",
        model_name="m",
        task=task,
        task_class=task_class,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        observed_behaviors=["Agent produced superficial output, then quit."],
        effort_signals=["Quit after 5 files of 200."],
        outcome=outcome,
        success=success,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _t(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "term": name,
        "score": score,
        "explanation": f"{name} ev",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _standard_payload(
    expectancy: float = 0.2,
    instrumentality: float = 0.8,
    valence: float = 0.6,
    bottleneck: str = "expectancy",
    quality: str = "weak",
) -> str:
    return json.dumps(
        {
            "terms": [
                _t("expectancy", expectancy),
                _t("instrumentality", instrumentality),
                _t("valence", valence),
            ],
            "bottleneck_term": bottleneck,
            "motivation_quality": quality,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_term": "expectancy",
                "intervention_type": "scaffold_subtasks",
                "description": "Break into subtasks.",
                "suggested_implementation": "Edit prompt.",
                "estimated_impact": "high",
                "rationale": "x",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_standard_payload())
    obj["top_intervention"] = {
        "target_term": "expectancy",
        "intervention_type": "scaffold_subtasks",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _prompt_signals_payload() -> str:
    return json.dumps(
        [
            {
                "category": "pointless_signal",
                "source_quote": "no one will review",
                "affected_term": "instrumentality",
                "polarity": "lowers",
                "explanation": "x",
            }
        ]
    )


def _eiv_audit_payload() -> str:
    return json.dumps(
        {
            "dominant_interaction": "E_dominates",
            "multiplicative_collapse_term": "expectancy",
            "notes": "x",
        }
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(VROOM_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(VROOM_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_three_terms(self) -> None:
        assert len(VROOM_TERMS) == 3

    def test_severity_polarity(self) -> None:
        # Inverse polarity: high motivation = low severity.
        assert severity_from_motivation(1.0) == "none"
        assert severity_from_motivation(-1.0) == "critical"
        # Collapsed quality floor
        assert severity_from_motivation(0.9, "collapsed") == "high"
        # Negative-valence floor
        assert severity_from_motivation(-0.1) == "medium"

    def test_legacy_alias_works(self) -> None:
        assert VroomExpectancyCalculator is VroomExpectancyAnalyzer


# ---------------------------------------------------------------------------
# Modes + deterministic compute
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.bottleneck_term == "expectancy"
        # Deterministic: 0.2 * 0.8 * 0.6 = 0.096
        assert abs(det.motivation_score - 0.096) < 0.001

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = VroomExpectancyAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _prompt_signals_payload(),
                _eiv_audit_payload(),
                _interventions_payload(),
            ]
        )
        det = VroomExpectancyAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.prompt_signals) == 1
        assert det.eiv_interaction_audit is not None

    def test_motivated_skips_interventions(self) -> None:
        payload = _standard_payload(
            expectancy=0.9,
            instrumentality=0.9,
            valence=0.9,
            bottleneck="none",
            quality="motivated",
        )
        stub = _stub([payload])
        det = VroomExpectancyAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []

    def test_deterministic_motivation_overrides_llm_lie(self) -> None:
        # LLM puts wrong motivation_score but per-term scores are correct.
        # The runtime should compute deterministically.
        payload = json.dumps(
            {
                "terms": [_t("expectancy", 0.5), _t("instrumentality", 0.5), _t("valence", 0.5)],
                "motivation_score": 0.99,  # lie
                "motivation_quality": "motivated",
                "bottleneck_term": "none",
            }
        )
        stub = _stub([payload])
        det = VroomExpectancyAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        # 0.5 * 0.5 * 0.5 = 0.125
        assert abs(det.motivation_score - 0.125) < 0.01


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_expectancy_bottleneck_creative(self) -> None:
        # Low E + creative task class => low_E_creative_task_misfit
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace(task_class="creative"))  # type: ignore[arg-type]
        assert det.profile_pattern == "low_E_creative_task_misfit"

    def test_negative_valence(self) -> None:
        payload = _standard_payload(
            expectancy=0.8,
            instrumentality=0.8,
            valence=-0.5,
            bottleneck="valence",
            quality="collapsed",
        )
        stub = _stub([payload, _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "valence_negative_active_avoidance"

    def test_multi_term_collapse(self) -> None:
        payload = _standard_payload(
            expectancy=0.1,
            instrumentality=0.2,
            valence=0.1,
            bottleneck="expectancy",
            quality="collapsed",
        )
        stub = _stub([payload, _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "multi_term_collapse"

    def test_high_e_high_i_low_v(self) -> None:
        payload = _standard_payload(
            expectancy=0.8,
            instrumentality=0.8,
            valence=0.2,
            bottleneck="valence",
            quality="weak",
        )
        stub = _stub([payload, _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "high_E_high_I_low_V_misaligned_task"

    def test_motivated_balanced(self) -> None:
        payload = _standard_payload(
            expectancy=0.9,
            instrumentality=0.9,
            valence=0.9,
            bottleneck="none",
            quality="motivated",
        )
        stub = _stub([payload])
        det = VroomExpectancyAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "motivated_balanced"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "vroom_expectancy"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(VROOM_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "expectancy_bottleneck" in keys
        assert "valence_negative_active_avoidance" in keys

    def test_expectancy_recommends_smart_goal(self) -> None:
        det = VroomDetection(
            task_class="code_generation",
            terms=[],
            motivation_score=0.1,
            bottleneck_term="expectancy",
            motivation_quality="weak",
            interventions=[],
            profile_pattern="expectancy_bottleneck",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.smart_goal" in recs

    def test_upstream_includes_sdt(self) -> None:
        up = recommended_upstream()
        assert "vstack.sdt_reward" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("expectancy", "task_too_sprawling") in keys
        assert ("instrumentality", "pointless_signal") in keys
        assert ("valence", "anti_value_task") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("expectancy", "scaffold_subtasks")
        assert pb is not None
        assert pb.failure_mode == "task_too_sprawling"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def _det(self) -> VroomDetection:
        return VroomDetection(
            task_class="code_generation",
            terms=[],
            motivation_score=0.1,
            bottleneck_term="expectancy",
            motivation_quality="weak",
            interventions=[],
            run_id="r-1",
        )

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = self._det()
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.bottleneck_term == "expectancy"

    def test_drift_returns_comparison(self) -> None:
        det = self._det()
        cmp = compare_to_baseline(det, det)
        assert isinstance(cmp, BaselineComparison)
        assert cmp.drift_severity == "none"


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


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
        stub = _AsyncStub([_standard_payload(), _interventions_payload()])
        analyzer = VroomExpectancyAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> VroomDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = VroomExpectancyAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Vroom" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_signals_and_audit(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _prompt_signals_payload(),
                _eiv_audit_payload(),
                _interventions_payload(),
            ]
        )
        det = VroomExpectancyAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "System Prompt Decomposition" in md
        assert "EIV Interaction Audit" in md
