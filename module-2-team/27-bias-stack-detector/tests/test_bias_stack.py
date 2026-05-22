"""Tests for the Bias-Stack Detector."""

from __future__ import annotations

import json

import pytest

from agentcity.bias_stack import (
    BIASES,
    AgentReasoningTrace,
    BiasEvidence,
    BiasIntervention,
    BiasStackDetection,
    BiasStackDetector,
    ReasoningStep,
)


def _step(content: str, type_: str = "thought") -> ReasoningStep:
    return ReasoningStep(type=type_, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentReasoningTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        steps=[_step("hello")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentReasoningTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentReasoningTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = BiasStackDetection(
            agent_id="t",
            dominant_bias="anchoring",
            bias_scores={b: 0.25 for b in BIASES},
            biases=[
                BiasEvidence(
                    bias="anchoring",
                    score=0.8,
                    severity="high",
                    explanation="locked on first hypothesis",
                    evidence_quotes=["Step 1: 'probably pool issue'"],
                )
            ],
            interventions=[
                BiasIntervention(
                    target_bias="anchoring",
                    intervention_type="first_principles_reset",
                    description="reset hypotheses after each observation",
                    suggested_implementation="prompt patch",
                    estimated_impact="high",
                    rationale="counters anchoring",
                )
            ],
            overall_reasoning_quality="severely-biased",
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Bias-Stack Detection" in md
        assert "Bias Scores" in md
        assert "Evidence by Bias" in md
        assert "Recommended Interventions" in md
        assert "anchoring" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = BiasStackDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = BiasStackDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_steps_rejected(self) -> None:
        det = BiasStackDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="steps"):
            det.run(_trace(steps=[]))


class TestDetectionPipeline:
    def test_end_to_end(self) -> None:
        scores = json.dumps(
            [
                {
                    "bias": "anchoring",
                    "score": 0.85,
                    "severity": "high",
                    "explanation": "locked on first hypothesis",
                    "evidence_quotes": ["step 1 hypothesis"],
                }
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_bias": "anchoring",
                    "intervention_type": "first_principles_reset",
                    "description": "force reset",
                    "suggested_implementation": "prompt patch text",
                    "estimated_impact": "high",
                    "rationale": "counters anchoring",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        det = BiasStackDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_bias == "anchoring"
        assert detection.overall_reasoning_quality == "severely-biased"
        assert detection.bias_scores["anchoring"] == 0.85
        assert len(detection.biases) == 4
        assert len(detection.interventions) == 1

    def test_missing_biases_filled(self) -> None:
        scores = json.dumps(
            [
                {
                    "bias": "anchoring",
                    "score": 0.8,
                    "severity": "high",
                    "explanation": "one bias only",
                    "evidence_quotes": [],
                }
            ]
        )
        det = BiasStackDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        present = {ev.bias for ev in detection.biases}
        assert present == set(BIASES)

    def test_anchoring_wins_tiebreak(self) -> None:
        scores = json.dumps(
            [
                {
                    "bias": "anchoring",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
                {
                    "bias": "escalation-of-commitment",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
            ]
        )
        det = BiasStackDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_bias == "anchoring"

    def test_none_observed_when_low(self) -> None:
        scores = json.dumps(
            [
                {
                    "bias": bias,
                    "score": 0.05,
                    "severity": "none",
                    "explanation": "no evidence",
                    "evidence_quotes": [],
                }
                for bias in BIASES
            ]
        )
        det = BiasStackDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace(success=True))
        assert detection.dominant_bias == "none-observed"
        assert detection.overall_reasoning_quality == "well-calibrated"
        assert detection.interventions == []


class TestQualityThresholds:
    @pytest.mark.parametrize(
        "max_score,expected",
        [
            (0.1, "well-calibrated"),
            (0.3, "well-calibrated"),
            (0.31, "bias-prone"),
            (0.6, "bias-prone"),
            (0.61, "severely-biased"),
            (0.9, "severely-biased"),
        ],
    )
    def test_threshold(self, max_score: float, expected: str) -> None:
        det = BiasStackDetector(_Stub([]))
        scores = {b: 0.0 for b in BIASES}
        scores["anchoring"] = max_score
        assert det._reasoning_quality(scores) == expected
