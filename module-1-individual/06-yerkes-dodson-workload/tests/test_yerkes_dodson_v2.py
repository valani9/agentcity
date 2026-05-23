"""Comprehensive v0.2.0 tests for the upgraded Yerkes-Dodson diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentcity.aar import InMemoryTelemetrySink, set_default_sink
from agentcity.yerkes_dodson import (
    PLAYBOOKS,
    SEVERITY_ORDER,
    WORKLOAD_PROFILE_PATTERNS,
    YERKES_DODSON_COMPOSITION,
    YERKES_DODSON_MODES,
    AgentPerformanceTrace,
    BaselineComparison,
    PressureInputs,
    WorkloadDetection,
    WorkloadDetector,
    YerkesDodsonAnalyzer,
    YerkesDodsonAnalyzerAsync,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_distance,
)


def _trace(
    *,
    task: str = "Compile a 1-page summary on prompt injection defenses.",
    outcome: str = "Summary contains 2 fabricated citations.",
    success: bool = False,
    pressure: PressureInputs | None = None,
    observed_behaviors: list[str] | None = None,
    framework: str | None = None,
) -> AgentPerformanceTrace:
    return AgentPerformanceTrace(
        agent_id="t",
        model_name="m",
        task=task,
        pressure=pressure or PressureInputs(),
        observed_behaviors=observed_behaviors
        or ["Agent skipped fact-check.", "Agent cited 3 unverified papers."],
        outcome=outcome,
        success=success,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from agentcity.aar import StubClient

    return StubClient(canned)


def _zone(name: str, score: float, severity: str = "moderate") -> dict[str, object]:
    return {
        "zone": name,
        "score": score,
        "explanation": f"{name} ev",
        "evidence_quotes": [],
        "confidence": 0.7,
        "severity": severity,
    }


def _standard_payload(
    observed_zone: str = "over_pressure",
    failure_mode: str = "hallucinating",
    distance: float = 0.85,
    n_interventions: int = 2,
    under: float = 0.0,
    opt: float = 0.1,
    over: float = 0.9,
) -> str:
    interventions = [
        {
            "target_zone": "optimal",
            "intervention_type": "loosen_deadline",
            "direction": "decrease_pressure",
            "description": "give more time",
            "suggested_implementation": "config",
            "estimated_impact": "high",
            "rationale": "headroom",
            "effort_estimate": "1d",
            "risk": "low",
            "reversibility": "two-way-door",
        }
        for _ in range(n_interventions)
    ]
    return json.dumps(
        {
            "zone_evidence": [
                _zone("under_pressure", under),
                _zone("optimal", opt),
                _zone("over_pressure", over),
            ],
            "observed_zone": observed_zone,
            "distance_from_optimal": distance,
            "failure_mode": failure_mode,
            "interventions": interventions,
        }
    )


def _quick_payload(
    observed_zone: str = "over_pressure",
    failure_mode: str = "hallucinating",
) -> str:
    return json.dumps(
        {
            "zone_evidence": [
                _zone("under_pressure", 0.0),
                _zone("optimal", 0.1),
                _zone("over_pressure", 0.9),
            ],
            "observed_zone": observed_zone,
            "distance_from_optimal": 0.85,
            "failure_mode": failure_mode,
            "top_intervention": {
                "target_zone": "optimal",
                "intervention_type": "loosen_deadline",
                "direction": "decrease_pressure",
                "description": "x",
                "suggested_implementation": "y",
                "rationale": "z",
                "estimated_impact": "high",
            },
        }
    )


def _cl_payload(
    intrinsic: float = 0.4,
    extraneous: float = 0.7,
    germane: float = 0.2,
    dominant: str = "extraneous",
) -> str:
    return json.dumps(
        {
            "intrinsic_load": intrinsic,
            "extraneous_load": extraneous,
            "germane_load": germane,
            "total_load": min(1.0, intrinsic + extraneous + germane),
            "dominant_component": dominant,
            "notes": "x",
        }
    )


def _ctx_payload(ratio: float = 0.8, risk: str = "high") -> str:
    return json.dumps(
        {
            "saturation_ratio": ratio,
            "lost_in_middle_risk": risk,
            "estimated_useful_tokens": 1000,
            "estimated_noise_tokens": 500,
            "notes": "x",
        }
    )


def _interventions_array() -> str:
    return json.dumps(
        [
            {
                "target_zone": "optimal",
                "intervention_type": "chunk_context",
                "direction": "decrease_pressure",
                "description": "chunk it",
                "suggested_implementation": "split docs",
                "estimated_impact": "high",
                "rationale": "saturation",
                "effort_estimate": "1d",
            }
        ]
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(YERKES_DODSON_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_eleven(self) -> None:
        assert len(WORKLOAD_PROFILE_PATTERNS) == 11

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_distance(0.0) == "none"
        assert severity_from_distance(1.0) == "critical"

    def test_legacy_alias_works(self) -> None:
        assert WorkloadDetector is YerkesDodsonAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_one_call(self) -> None:
        stub = _stub([_standard_payload()])
        det = YerkesDodsonAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 1
        assert det.observed_zone == "over_pressure"
        assert det.failure_mode == "hallucinating"
        assert len(det.interventions) == 2

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = YerkesDodsonAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _cl_payload(),
                _ctx_payload(),
                _interventions_array(),
            ]
        )
        det = YerkesDodsonAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert det.cognitive_load_analysis is not None
        assert det.cognitive_load_analysis.dominant_component == "extraneous"
        assert det.context_saturation is not None
        assert det.context_saturation.saturation_ratio == 0.8

    def test_optimal_skips_interventions(self) -> None:
        payload = _standard_payload(
            observed_zone="optimal",
            failure_mode="focused",
            distance=0.0,
            n_interventions=0,
            under=0.05,
            opt=0.9,
            over=0.05,
        )
        stub = _stub([payload])
        det = YerkesDodsonAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.observed_zone == "optimal"
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_over_pressure_hallucinating(self) -> None:
        stub = _stub([_standard_payload()])
        det = YerkesDodsonAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "over_pressure_hallucinating"

    def test_over_pressure_corner_cutting(self) -> None:
        stub = _stub([_standard_payload(failure_mode="corner_cutting")])
        det = YerkesDodsonAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "over_pressure_corner_cutting"

    def test_under_pressure_wandering(self) -> None:
        payload = _standard_payload(
            observed_zone="under_pressure",
            failure_mode="wandering",
            distance=0.6,
            under=0.8,
            opt=0.2,
            over=0.0,
        )
        stub = _stub([payload])
        det = YerkesDodsonAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "under_pressure_wandering"

    def test_optimal_zone(self) -> None:
        payload = _standard_payload(
            observed_zone="optimal",
            failure_mode="focused",
            distance=0.05,
            n_interventions=0,
            under=0.05,
            opt=0.9,
            over=0.05,
        )
        stub = _stub([payload])
        det = YerkesDodsonAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "optimal_zone"

    def test_context_saturation_wins(self) -> None:
        # Even if LLM says over_pressure_hallucinating, deterministic
        # context_saturation should override when ratio >= 0.7.
        stub = _stub([_standard_payload()])
        det = YerkesDodsonAnalyzer(stub).run(  # type: ignore[arg-type]
            _trace(
                pressure=PressureInputs(
                    context_size_tokens=80_000,
                    context_window_size=100_000,
                )
            )
        )
        assert det.profile_pattern == "context_saturation"
        # And deterministic saturation should be populated.
        assert det.context_saturation is not None
        assert det.context_saturation.saturation_ratio >= 0.7


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_standard_payload()])
        det = YerkesDodsonAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 1
        for ev in sink.events:
            assert ev.pattern == "yerkes_dodson"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(YERKES_DODSON_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "over_pressure_hallucinating" in keys
        assert "over_pressure_corner_cutting" in keys
        assert "optimal_zone" in keys

    def test_hallucinating_recommends_johari(self) -> None:
        det = WorkloadDetection(
            observed_zone="over_pressure",
            zone_evidence=[],
            distance_from_optimal=0.8,
            failure_mode="hallucinating",
            interventions=[],
            profile_pattern="over_pressure_hallucinating",
        )
        recs, _ = recommended_downstream(det)
        assert "agentcity.johari" in recs

    def test_upstream_includes_lewin(self) -> None:
        up = recommended_upstream()
        assert "agentcity.lewin" in up
        assert "agentcity.aar" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("under_pressure", "wandering") in keys
        assert ("over_pressure", "hallucinating") in keys
        assert ("over_pressure", "context_saturation") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("over_pressure", "chunk_context")
        assert pb is not None
        assert pb.failure_mode == "context_saturation"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = WorkloadDetection(
            observed_zone="over_pressure",
            zone_evidence=[],
            distance_from_optimal=0.7,
            failure_mode="hallucinating",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.observed_zone == "over_pressure"

    def test_drift_returns_comparison(self) -> None:
        det = WorkloadDetection(
            observed_zone="over_pressure",
            zone_evidence=[],
            distance_from_optimal=0.7,
            failure_mode="hallucinating",
            interventions=[],
        )
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
        stub = _AsyncStub([_standard_payload()])
        analyzer = YerkesDodsonAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> WorkloadDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"
        assert det.observed_zone == "over_pressure"


# ---------------------------------------------------------------------------
# Markdown v2 + serialization
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload()])
        det = YerkesDodsonAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Yerkes-Dodson" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_cl_and_saturation(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _cl_payload(),
                _ctx_payload(),
                _interventions_array(),
            ]
        )
        det = YerkesDodsonAnalyzer(stub, mode="forensic").run(  # type: ignore[arg-type]
            _trace(
                pressure=PressureInputs(
                    context_size_tokens=60_000,
                    context_window_size=100_000,
                )
            )
        )
        md = det.to_markdown()
        assert "Cognitive Load" in md
        assert "Context Saturation" in md
