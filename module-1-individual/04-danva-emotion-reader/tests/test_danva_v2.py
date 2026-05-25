"""Comprehensive v0.2.0 tests for the upgraded DANVA Emotion Reader."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


from vstack.aar import (
    InMemoryTelemetrySink,
    set_default_sink,
)
from vstack.danva_emotion import (
    DANVA_COMPOSITION,
    DANVA_MODES,
    DANVA_PROFILE_PATTERNS,
    EMOTION_CATEGORIES,
    PLAYBOOKS,
    SEVERITY_ORDER,
    AgentEmotionTrace,
    BaselineComparison,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
    EmotionRecognitionAnalyzer,
    EmotionRecognitionAnalyzerAsync,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_accuracy,
)


def _item(
    item_id: str,
    truth: str,
    inferred: str,
    truth_int: float = 0.7,
    inferred_int: float = 0.5,
    user_input: str = "x",
    cue_explicitness: str = "explicit",
) -> EmotionItem:
    return EmotionItem(
        item_id=item_id,
        user_input=user_input,
        ground_truth_emotion=truth,  # type: ignore[arg-type]
        ground_truth_intensity=truth_int,
        agent_inferred_emotion=inferred,  # type: ignore[arg-type]
        agent_inferred_intensity=inferred_int,
        cue_explicitness=cue_explicitness,  # type: ignore[arg-type]
    )


def _trace(items: list[EmotionItem], **overrides) -> AgentEmotionTrace:  # type: ignore[no-untyped-def]
    base = dict(agent_id="t", items=items)
    base.update(overrides)
    return AgentEmotionTrace(**base)  # type: ignore[arg-type]


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_emotion_categories_unchanged(self) -> None:
        assert EMOTION_CATEGORIES == (
            "happy",
            "sad",
            "angry",
            "fearful",
            "disgust",
            "surprise",
            "neutral",
        )

    def test_modes_three(self) -> None:
        assert set(DANVA_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_fourteen(self) -> None:
        assert len(DANVA_PROFILE_PATTERNS) == 14

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_inverse_polarity(self) -> None:
        assert severity_from_accuracy(0.0) == "critical"
        assert severity_from_accuracy(0.5) == "moderate"
        assert severity_from_accuracy(1.0) == "none"


# ---------------------------------------------------------------------------
# Multi-mode pipeline
# ---------------------------------------------------------------------------


class TestModes:
    def test_quick_mode_at_most_one_call(self) -> None:
        # All angry items wrong -> quality != high-accuracy -> 1 LLM call.
        items = [_item(f"a{i}", "angry", "neutral", 0.9, 0.3) for i in range(3)] + [
            _item("h1", "happy", "happy", 0.8, 0.8)
        ]
        interventions = json.dumps(
            [
                {
                    "target_emotion": "angry",
                    "intervention_type": "add_cue_inventory",
                    "description": "x",
                    "suggested_implementation": "y",
                    "estimated_impact": "high",
                    "rationale": "z",
                }
            ]
        )
        stub = _stub([interventions])
        analyzer = EmotionRecognitionAnalyzer(stub, mode="quick")  # type: ignore[arg-type]
        analysis = analyzer.run(_trace(items))
        assert analysis.mode == "quick"
        assert analysis.llm_calls == 1
        assert len(analysis.interventions) >= 1

    def test_standard_mode_high_accuracy_skips(self) -> None:
        items = [_item(f"h{i}", "happy", "happy", 0.8, 0.8) for i in range(10)]
        stub = _stub([])
        analyzer = EmotionRecognitionAnalyzer(stub, mode="standard")  # type: ignore[arg-type]
        analysis = analyzer.run(_trace(items))
        assert analysis.accuracy_quality == "high-accuracy"
        assert analysis.llm_calls == 0
        assert analysis.interventions == []

    def test_forensic_mode_three_calls(self) -> None:
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("a2", "angry", "neutral", 0.7, 0.4),
            _item("h1", "happy", "happy", 0.8, 0.8),
        ]
        circumplex = json.dumps(
            {
                "valence_truth": -0.3,
                "arousal_truth": 0.5,
                "valence_inferred": 0.0,
                "arousal_inferred": 0.1,
                "euclidean_distance": 0.5,
                "quadrant_truth": "high-neg",
                "quadrant_inferred": "high-pos",
                "quadrant_match": False,
            }
        )
        cascade = json.dumps(
            {
                "cascade_break_point": "fails_at_perceive_cue",
                "perceive_score": 0.3,
                "categorize_score": 0.5,
                "intensity_score": 0.4,
                "respond_score": 0.5,
                "notes": "Misses anger cues at the perception step.",
            }
        )
        interventions = json.dumps(
            [
                {
                    "target_emotion": "angry",
                    "intervention_type": "add_cue_inventory",
                    "description": "Add anger cue inventory.",
                    "suggested_implementation": "Append cue list.",
                    "estimated_impact": "high",
                    "rationale": "x",
                }
            ]
        )
        stub = _stub([circumplex, cascade, interventions])
        analyzer = EmotionRecognitionAnalyzer(stub, mode="forensic")  # type: ignore[arg-type]
        analysis = analyzer.run(_trace(items))
        assert analysis.mode == "forensic"
        assert analysis.llm_calls == 3
        assert analysis.cascade_analysis is not None
        assert analysis.cascade_analysis.cascade_break_point == "fails_at_perceive_cue"


# ---------------------------------------------------------------------------
# Profile pattern classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_anger_blind(self) -> None:
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("a2", "angry", "neutral", 0.7, 0.4),
            _item("h1", "happy", "happy", 0.8, 0.8),
            _item("h2", "happy", "happy", 0.85, 0.8),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert analysis.profile_pattern == "anger_blind"

    def test_balanced_high(self) -> None:
        items = [_item(f"h{i}", "happy", "happy", 0.85, 0.8) for i in range(5)] + [
            _item(f"a{i}", "angry", "angry", 0.85, 0.8) for i in range(5)
        ]
        stub = _stub([])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert analysis.profile_pattern == "balanced_high"

    def test_uncertain_dump(self) -> None:
        items = [_item(f"i{i}", "angry", "uncertain", 0.7, 0.5) for i in range(5)] + [
            _item("h1", "happy", "happy", 0.8, 0.8)
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert analysis.profile_pattern == "uncertain_dump"

    def test_sadness_collapse(self) -> None:
        items = [_item(f"s{i}", "sad", "sad", 0.9, 0.4) for i in range(4)]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert analysis.profile_pattern == "sadness_collapse"


# ---------------------------------------------------------------------------
# Confusion matrix + intensity curves + circumplex
# ---------------------------------------------------------------------------


class TestSyntheses:
    def test_confusion_matrix_built(self) -> None:
        items = [
            _item("a1", "angry", "neutral"),
            _item("a2", "angry", "angry"),
            _item("h1", "happy", "happy"),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        cm = analysis.confusion_matrix
        assert cm is not None
        assert cm.matrix["angry"]["neutral"] == 1
        assert cm.matrix["angry"]["angry"] == 1
        assert cm.diagonal_total == 2

    def test_circumplex_projection_present(self) -> None:
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("h1", "happy", "happy", 0.8, 0.8),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert analysis.circumplex_projection is not None

    def test_intensity_curves_present(self) -> None:
        items = [
            _item("a1", "angry", "angry", 0.9, 0.4),
            _item("a2", "angry", "angry", 0.7, 0.3),
            _item("h1", "happy", "happy", 0.8, 0.8),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert len(analysis.intensity_curves) == 7


# ---------------------------------------------------------------------------
# Telemetry + run-context
# ---------------------------------------------------------------------------


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("a2", "angry", "neutral", 0.7, 0.4),
            _item("h1", "happy", "happy", 0.8, 0.8),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items))  # type: ignore[arg-type]
        assert len(sink.events) == analysis.llm_calls
        for ev in sink.events:
            assert ev.pattern == "danva_emotion"
            assert ev.run_id == analysis.run_id


# ---------------------------------------------------------------------------
# Composition + playbooks + calibration
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(DANVA_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "anger_blind" in keys
        assert "sarcasm_blind" in keys

    def test_anger_blind_recommends_glaser(self) -> None:
        analysis = EmotionRecognitionAnalysis(
            metrics=[],
            overall_accuracy=0.3,
            overall_intensity_mae=0.3,
            weakest_emotion="angry",
            accuracy_quality="low-accuracy",
            interventions=[],
            n_items=4,
            profile_pattern="anger_blind",
        )
        recs, _ = recommended_downstream(analysis)
        assert "vstack.glaser_conversation" in recs

    def test_recommended_upstream_includes_goleman(self) -> None:
        up = recommended_upstream()
        assert "vstack.goleman_ei" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("angry", "under_detection") in keys
        assert ("happy", "sarcasm_blind") in keys
        assert ("all", "uncertain_dump") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("angry", "add_cue_inventory")
        assert pb is not None
        assert pb.failure_mode == "under_detection"


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        analysis = EmotionRecognitionAnalysis(
            metrics=[
                EmotionMetric(
                    emotion="angry",
                    n_items=2,
                    accuracy=0.5,
                    intensity_mae=0.2,
                )
            ],
            overall_accuracy=0.5,
            overall_intensity_mae=0.2,
            weakest_emotion="angry",
            accuracy_quality="developing",
            interventions=[],
            n_items=2,
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(analysis, path)
        restored = load_baseline(path)
        assert restored.weakest_emotion == "angry"

    def test_drift_returns_comparison(self) -> None:
        analysis = EmotionRecognitionAnalysis(
            metrics=[],
            overall_accuracy=0.5,
            overall_intensity_mae=0.2,
            weakest_emotion="angry",
            accuracy_quality="developing",
            interventions=[],
            n_items=2,
        )
        cmp = compare_to_baseline(analysis, analysis)
        assert isinstance(cmp, BaselineComparison)


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
    def test_arun_returns_analysis(self) -> None:
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("h1", "happy", "happy", 0.8, 0.8),
        ]
        stub = _AsyncStub(["[]"])
        analyzer = EmotionRecognitionAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> EmotionRecognitionAnalysis:
            return await analyzer.arun(_trace(items))

        analysis = asyncio.run(call())
        assert analysis.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        items = [
            _item("a1", "angry", "neutral", 0.9, 0.3),
            _item("a2", "angry", "neutral", 0.7, 0.4),
            _item("h1", "happy", "happy", 0.8, 0.8),
            _item("h2", "happy", "happy", 0.85, 0.8),
        ]
        stub = _stub(["[]"])
        analysis = EmotionRecognitionAnalyzer(stub).run(_trace(items, framework="custom"))  # type: ignore[arg-type]
        md = analysis.to_markdown()
        assert "DANVA-Style" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Russell Circumplex Projection" in md
        assert "Composition Handoff" in md
