"""Comprehensive v0.2.0 tests for the upgraded 4 Motivation Traps diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.motivation_traps import (
    MOTIVATION_COMPOSITION,
    MOTIVATION_MODES,
    MOTIVATION_PROFILE_PATTERNS,
    MOTIVATION_TRAPS,
    PLAYBOOKS,
    SEVERITY_ORDER,
    AgentMotivationTrace,
    BaselineComparison,
    MotivationDetection,
    MotivationTrapsAnalyzer,
    MotivationTrapsAnalyzerAsync,
    MotivationTrapsDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_trap_score,
)


def _trace(
    *,
    task: str = "Investigate latency spike.",
    task_class: str = "research",
    outcome: str = "Agent gave up; root cause unfound.",
    success: bool = False,
    abandonment_signal: str = "refused after one attempt",
    framework: str | None = None,
) -> AgentMotivationTrace:
    return AgentMotivationTrace(
        agent_id="t",
        model_name="m",
        task=task,
        task_class=task_class,  # type: ignore[arg-type]
        observed_behaviors=[
            "Agent quit after one failed query.",
            "Repeated the same query format on retry.",
        ],
        self_reports=[
            "I'm not sure I can find this answer.",
            "Maybe the data is wrong.",
        ],
        abandonment_signal=abandonment_signal,
        outcome=outcome,
        success=success,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _ev(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "trap": name,
        "score": score,
        "explanation": f"{name} ev",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _standard_payload(
    values_s: float = 0.1,
    se_s: float = 0.7,
    emotions_s: float = 0.1,
    attr_s: float = 0.1,
    dominant: str = "self_efficacy",
    quality: str = "abandoning",
) -> str:
    return json.dumps(
        {
            "trap_evidence": [
                _ev("values", values_s),
                _ev("self_efficacy", se_s),
                _ev("emotions", emotions_s),
                _ev("attribution", attr_s),
            ],
            "dominant_trap": dominant,
            "motivation_quality": quality,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_trap": "self_efficacy",
                "intervention_type": "scaffold_subtasks",
                "description": "Decompose into smaller subtasks.",
                "suggested_implementation": "Add explicit step list.",
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
        "target_trap": "self_efficacy",
        "intervention_type": "scaffold_subtasks",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _weiner_payload() -> str:
    return json.dumps(
        {
            "locus": "internal",
            "stability": "stable",
            "controllability": "uncontrollable",
            "is_maladaptive": True,
            "explanation": "x",
            "evidence_quotes": [],
        }
    )


def _abandonment_payload() -> str:
    return json.dumps(
        [
            {
                "step_index": 0,
                "trap": "self_efficacy",
                "signal_type": "refusal",
                "observed_text": "I can't do this.",
                "severity": "high",
            }
        ]
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(MOTIVATION_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(MOTIVATION_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_four_traps(self) -> None:
        assert len(MOTIVATION_TRAPS) == 4

    def test_severity_polarity(self) -> None:
        assert severity_from_trap_score(0.0) == "none"
        assert severity_from_trap_score(1.0) == "critical"
        # Quality floor
        assert severity_from_trap_score(0.1, "abandoning") == "medium"

    def test_legacy_alias_works(self) -> None:
        assert MotivationTrapsDetector is MotivationTrapsAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.dominant_trap == "self_efficacy"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = MotivationTrapsAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _weiner_payload(),
                _abandonment_payload(),
                _interventions_payload(),
            ]
        )
        det = MotivationTrapsAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert det.attribution_axis is not None
        assert det.attribution_axis.is_maladaptive
        assert len(det.abandonment_chain) == 1

    def test_motivated_skips_interventions(self) -> None:
        payload = _standard_payload(
            values_s=0.1,
            se_s=0.1,
            emotions_s=0.1,
            attr_s=0.1,
            dominant="none",
            quality="motivated",
        )
        stub = _stub([payload])
        det = MotivationTrapsAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_self_efficacy_collapse(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "self_efficacy_collapse_uncertainty"

    def test_high_stakes_capability_collapse(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub).run(_trace(task_class="tool_use"))  # type: ignore[arg-type]
        assert det.profile_pattern == "high_stakes_capability_collapse"

    def test_creative_value_misfit(self) -> None:
        payload = _standard_payload(
            values_s=0.8,
            se_s=0.1,
            emotions_s=0.1,
            attr_s=0.1,
            dominant="values",
            quality="abandoning",
        )
        stub = _stub([payload, _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub).run(_trace(task_class="creative"))  # type: ignore[arg-type]
        assert det.profile_pattern == "creative_task_value_misfit"

    def test_self_efficacy_plus_attribution(self) -> None:
        payload = _standard_payload(
            values_s=0.1,
            se_s=0.7,
            emotions_s=0.1,
            attr_s=0.6,
            dominant="self_efficacy",
            quality="abandoning",
        )
        stub = _stub([payload, _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "self_efficacy_plus_attribution"

    def test_motivated_baseline(self) -> None:
        payload = _standard_payload(
            values_s=0.1,
            se_s=0.1,
            emotions_s=0.1,
            attr_s=0.1,
            dominant="none",
            quality="motivated",
        )
        stub = _stub([payload])
        det = MotivationTrapsAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "motivated_baseline"


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
        det = MotivationTrapsAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "motivation_traps"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(MOTIVATION_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "self_efficacy_collapse_uncertainty" in keys
        assert "attribution_loop_wrong_cause" in keys

    def test_self_efficacy_recommends_cognitive_reappraisal(self) -> None:
        det = MotivationDetection(
            task_class="research",
            trap_evidence=[],
            dominant_trap="self_efficacy",
            motivation_quality="abandoning",
            interventions=[],
            profile_pattern="self_efficacy_collapse_uncertainty",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.cognitive_reappraisal" in recs

    def test_upstream_includes_hexaco(self) -> None:
        up = recommended_upstream()
        assert "vstack.hexaco" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("values", "irrelevance_refusal") in keys
        assert ("self_efficacy", "capability_collapse") in keys
        assert ("attribution", "wrong_cause_loop") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("self_efficacy", "scaffold_subtasks")
        assert pb is not None
        assert pb.failure_mode == "capability_collapse"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = MotivationDetection(
            task_class="research",
            trap_evidence=[],
            dominant_trap="self_efficacy",
            motivation_quality="abandoning",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.dominant_trap == "self_efficacy"

    def test_drift_returns_comparison(self) -> None:
        det = MotivationDetection(
            task_class="research",
            trap_evidence=[],
            dominant_trap="self_efficacy",
            motivation_quality="abandoning",
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
        stub = _AsyncStub([_standard_payload(), _interventions_payload()])
        analyzer = MotivationTrapsAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> MotivationDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = MotivationTrapsAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Motivation Traps" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_weiner_and_chain(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _weiner_payload(),
                _abandonment_payload(),
                _interventions_payload(),
            ]
        )
        det = MotivationTrapsAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Weiner Attribution Axis" in md
        assert "Abandonment Causation Chain" in md
