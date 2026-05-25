"""Tests for the DANVA-style Emotion Reader Diagnostic."""

from __future__ import annotations

import json

import pytest

from vstack.danva_emotion import (
    EMOTION_CATEGORIES,
    AgentEmotionTrace,
    EmotionIntervention,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
    EmotionRecognitionAnalyzer,
)


def _item(
    item_id: str,
    user_input: str,
    truth: str,
    inferred: str,
    truth_int: float = 0.5,
    inferred_int: float = 0.5,
) -> EmotionItem:
    return EmotionItem(
        item_id=item_id,
        user_input=user_input,
        ground_truth_emotion=truth,  # type: ignore[arg-type]
        ground_truth_intensity=truth_int,
        agent_inferred_emotion=inferred,  # type: ignore[arg-type]
        agent_inferred_intensity=inferred_int,
    )


def _trace(items: list[EmotionItem], **overrides: object) -> AgentEmotionTrace:
    base: dict[str, object] = dict(agent_id="test", items=items)
    base.update(overrides)
    return AgentEmotionTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestDeterministicMetrics:
    def test_perfect_accuracy(self) -> None:
        items = [
            _item("i1", "hi", "happy", "happy", 0.5, 0.5),
            _item("i2", "ok", "neutral", "neutral", 0.1, 0.1),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        happy = next(m for m in metrics if m.emotion == "happy")
        assert happy.n_items == 1
        assert happy.accuracy == 1.0
        neutral = next(m for m in metrics if m.emotion == "neutral")
        assert neutral.accuracy == 1.0

    def test_anger_under_detection(self) -> None:
        items = [
            _item("a1", "CAPS", "angry", "neutral", 0.9, 0.3),
            _item("a2", "fed up", "angry", "neutral", 0.7, 0.4),
            _item("h1", "thanks!", "happy", "happy", 0.8, 0.8),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        angry = next(m for m in metrics if m.emotion == "angry")
        assert angry.n_items == 2
        assert angry.accuracy == 0.0
        assert angry.confusion_with == {"neutral": 2}
        # intensity MAE for angry: mean(|0.3-0.9|, |0.4-0.7|) = (0.6+0.3)/2 = 0.45
        assert abs(angry.intensity_mae - 0.45) < 0.01

    def test_empty_emotion_has_zero_n(self) -> None:
        items = [_item("h1", "hi", "happy", "happy")]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        sad = next(m for m in metrics if m.emotion == "sad")
        assert sad.n_items == 0
        assert sad.accuracy == 0.0

    def test_overall_computation(self) -> None:
        items = [
            _item("i1", "x", "happy", "happy", 0.7, 0.7),
            _item("i2", "y", "happy", "happy", 0.7, 0.5),
            _item("i3", "z", "angry", "neutral", 0.8, 0.3),
            _item("i4", "w", "sad", "sad", 0.6, 0.6),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        acc, mae = analyzer._compute_overall(items)
        assert acc == 0.75  # 3/4 correct
        # MAE = (0 + 0.2 + 0.5 + 0) / 4 = 0.175
        assert abs(mae - 0.175) < 0.01


class TestWeakestCoercion:
    def test_picks_lowest_accuracy_with_enough_items(self) -> None:
        items = [
            _item("a1", "x", "angry", "neutral"),
            _item("a2", "y", "angry", "neutral"),
            _item("h1", "z", "happy", "happy"),
            _item("h2", "w", "happy", "happy"),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        assert analyzer._coerce_weakest(metrics) == "angry"

    def test_none_when_all_high(self) -> None:
        items = [
            _item("a1", "x", "angry", "angry"),
            _item("a2", "y", "angry", "angry"),
            _item("h1", "z", "happy", "happy"),
            _item("h2", "w", "happy", "happy"),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        assert analyzer._coerce_weakest(metrics) == "none"

    def test_ignores_single_item_emotions(self) -> None:
        items = [
            _item("d1", "x", "disgust", "neutral"),  # n=1, ignored
            _item("h1", "z", "happy", "happy"),
            _item("h2", "w", "happy", "happy"),
        ]
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        metrics = analyzer._compute_metrics(items)
        # disgust is 0% accurate but has only 1 item → should fall back to "none"
        # because happy is 100%, no candidate with n>=2 is below 0.8
        assert analyzer._coerce_weakest(metrics) == "none"


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace([_item("i1", "hi", "happy", "happy")])
        restored = AgentEmotionTrace.model_validate_json(trace.model_dump_json())
        assert len(restored.items) == 1

    def test_analysis_markdown(self) -> None:
        analysis = EmotionRecognitionAnalysis(
            agent_id="t",
            metrics=[
                EmotionMetric(
                    emotion=e,  # type: ignore[arg-type]
                    n_items=2,
                    accuracy=0.5,
                    intensity_mae=0.2,
                )
                for e in EMOTION_CATEGORIES
            ],
            overall_accuracy=0.5,
            overall_intensity_mae=0.2,
            weakest_emotion="angry",
            accuracy_quality="developing",
            interventions=[
                EmotionIntervention(
                    target_emotion="angry",
                    intervention_type="add_cue_inventory",
                    description="cues",
                    suggested_implementation="prompt",
                    estimated_impact="high",
                    rationale="closes gap",
                )
            ],
            generator_model="test-model",
            n_items=14,
        )
        md = analysis.to_markdown()
        assert "DANVA-Style" in md
        assert "DEVELOPING" in md
        assert "angry" in md


class TestValidation:
    def test_empty_items_rejected(self) -> None:
        with pytest.raises(Exception):
            _trace([])


class TestAnalysisPipeline:
    def test_developing_triggers_interventions(self) -> None:
        items = [
            _item("a1", "x", "angry", "neutral"),
            _item("a2", "y", "angry", "neutral"),
            _item("h1", "z", "happy", "happy"),
            _item("h2", "w", "happy", "happy"),
        ]
        interventions = json.dumps(
            [
                {
                    "target_emotion": "angry",
                    "intervention_type": "add_cue_inventory",
                    "description": "cues",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes",
                }
            ]
        )
        stub = _Stub([interventions])
        analyzer = EmotionRecognitionAnalyzer(stub, model="test-model")
        analysis = analyzer.run(_trace(items))
        assert len(stub.calls) == 1
        assert analysis.accuracy_quality == "developing"
        assert analysis.weakest_emotion == "angry"
        assert len(analysis.interventions) == 1

    def test_high_accuracy_skips_llm(self) -> None:
        items = [_item(f"i{i}", "x", "happy", "happy") for i in range(10)]
        stub = _Stub([])
        analyzer = EmotionRecognitionAnalyzer(stub, model="test-model")
        analysis = analyzer.run(_trace(items))
        assert analysis.accuracy_quality == "high-accuracy"
        assert analysis.interventions == []
        assert len(stub.calls) == 0


class TestAccuracyThresholds:
    @pytest.mark.parametrize(
        "acc,expected",
        [
            (0.9, "high-accuracy"),
            (0.8, "high-accuracy"),
            (0.79, "developing"),
            (0.5, "developing"),
            (0.49, "low-accuracy"),
            (0.0, "low-accuracy"),
        ],
    )
    def test_threshold(self, acc: float, expected: str) -> None:
        analyzer = EmotionRecognitionAnalyzer(_Stub([]))
        assert analyzer._accuracy_quality(acc) == expected
