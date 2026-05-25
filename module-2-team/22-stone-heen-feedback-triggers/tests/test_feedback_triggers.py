"""Tests for the Stone & Heen 3-Trigger Feedback Diagnostic."""

from __future__ import annotations

import json

import pytest

from vstack.feedback_triggers import (
    TRIGGERS,
    FeedbackInteractionTrace,
    FeedbackMessage,
    FeedbackTriggerDetection,
    FeedbackTriggerDetector,
    TriggerEvidence,
    TriggerIntervention,
)


def _msg(content: str, source: str = "user", feedback: bool = False) -> FeedbackMessage:
    return FeedbackMessage(source=source, content=content, is_feedback=feedback)  # type: ignore[arg-type]


def _trace(**overrides: object) -> FeedbackInteractionTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        messages=[_msg("you got this wrong", feedback=True), _msg("I disagree", source="agent")],
        outcome="default outcome",
        feedback_incorporated=False,
    )
    base.update(overrides)
    return FeedbackInteractionTrace(**base)  # type: ignore[arg-type]


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
        restored = FeedbackInteractionTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.messages) == 2

    def test_detection_markdown_all_sections(self) -> None:
        detection = FeedbackTriggerDetection(
            agent_id="t",
            dominant_trigger="truth",
            trigger_scores={t: 0.25 for t in TRIGGERS},
            triggers=[
                TriggerEvidence(
                    trigger="truth",
                    score=0.8,
                    severity="high",
                    explanation="argued the user was wrong",
                    evidence_quotes=["Agent: 'Actually my answer is right'"],
                )
            ],
            interventions=[
                TriggerIntervention(
                    target_trigger="truth",
                    intervention_type="acknowledge_first",
                    description="acknowledge feedback before responding",
                    suggested_implementation="prompt patch",
                    estimated_impact="high",
                    rationale="forces engagement with substance",
                )
            ],
            feedback_intake_quality="feedback-rejecting",
            generator_model="test-model",
            feedback_incorporated=False,
        )
        md = detection.to_markdown()
        assert "Feedback-Trigger Detection" in md
        assert "Trigger Scores" in md
        assert "Evidence by Trigger" in md
        assert "Recommended Interventions" in md
        assert "truth" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = FeedbackTriggerDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = FeedbackTriggerDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_messages_rejected(self) -> None:
        det = FeedbackTriggerDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="messages"):
            det.run(_trace(messages=[]))


class TestDetectionPipeline:
    def test_end_to_end(self) -> None:
        scores = json.dumps(
            [
                {
                    "trigger": "truth",
                    "score": 0.85,
                    "severity": "high",
                    "explanation": "argued user was wrong",
                    "evidence_quotes": ["Agent: 'actually my answer is right'"],
                }
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_trigger": "truth",
                    "intervention_type": "acknowledge_first",
                    "description": "acknowledge first",
                    "suggested_implementation": "prompt patch",
                    "estimated_impact": "high",
                    "rationale": "forces engagement",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        det = FeedbackTriggerDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_trigger == "truth"
        assert detection.feedback_intake_quality == "feedback-rejecting"
        assert detection.trigger_scores["truth"] == 0.85
        assert len(detection.triggers) == 3
        assert len(detection.interventions) == 1

    def test_missing_triggers_filled(self) -> None:
        scores = json.dumps(
            [
                {
                    "trigger": "truth",
                    "score": 0.8,
                    "severity": "high",
                    "explanation": "one trigger only",
                    "evidence_quotes": [],
                }
            ]
        )
        det = FeedbackTriggerDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        present = {ev.trigger for ev in detection.triggers}
        assert present == set(TRIGGERS)

    def test_truth_wins_tiebreak(self) -> None:
        scores = json.dumps(
            [
                {
                    "trigger": "truth",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
                {
                    "trigger": "identity",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
            ]
        )
        det = FeedbackTriggerDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_trigger == "truth"

    def test_none_observed_when_low(self) -> None:
        scores = json.dumps(
            [
                {
                    "trigger": trigger,
                    "score": 0.05,
                    "severity": "none",
                    "explanation": "no evidence",
                    "evidence_quotes": [],
                }
                for trigger in TRIGGERS
            ]
        )
        det = FeedbackTriggerDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace(feedback_incorporated=True))
        assert detection.dominant_trigger == "none-observed"
        assert detection.feedback_intake_quality == "absorbs-feedback"
        assert detection.interventions == []


class TestIntakeQualityThresholds:
    @pytest.mark.parametrize(
        "max_score,incorporated,expected",
        [
            (0.1, True, "absorbs-feedback"),
            (0.3, True, "absorbs-feedback"),
            (0.31, True, "trigger-prone"),
            (0.6, False, "feedback-rejecting"),
            (0.9, False, "feedback-rejecting"),
            (0.4, False, "trigger-prone"),
        ],
    )
    def test_threshold(self, max_score: float, incorporated: bool, expected: str) -> None:
        det = FeedbackTriggerDetector(_Stub([]))
        scores = {t: 0.0 for t in TRIGGERS}
        scores["truth"] = max_score
        assert det._intake_quality(scores, incorporated) == expected
