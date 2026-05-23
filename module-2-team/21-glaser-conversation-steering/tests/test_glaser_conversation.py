"""Tests for the Glaser Conversation Steering Diagnostic."""

from __future__ import annotations

import json

import pytest

from agentcity.glaser_conversation import (
    NEUROCHEMICAL_STATES,
    ConversationSteeringDetection,
    ConversationSteeringDetector,
    ConversationTrace,
    ConversationTurn,
    NeurochemicalEvidence,
    SteeringIntervention,
)


def _trace(**overrides: object) -> ConversationTrace:
    base: dict[str, object] = dict(
        conversation_id="test",
        task="default task",
        turns=[
            ConversationTurn(turn_index=0, speaker="user", text="hi"),
            ConversationTurn(turn_index=1, speaker="agent", text="hello"),
        ],
        observed_response_pattern=["normal exchange"],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return ConversationTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _ev(state: str, score: float = 0.5) -> dict[str, object]:
    return {
        "state": state,
        "score": score,
        "triggers": [],
        "explanation": f"{state} explanation",
    }


def _payload(
    state: str = "cortisol",
    quality: str = "trust-eroding",
    level: str = "level_ii",
    scores: dict[str, float] | None = None,
) -> str:
    s = scores or {"cortisol": 0.9, "neutral": 0.1, "oxytocin": 0.0}
    return json.dumps(
        {
            "evidence": [
                _ev("cortisol", s["cortisol"]),
                _ev("neutral", s["neutral"]),
                _ev("oxytocin", s["oxytocin"]),
            ],
            "dominant_state": state,
            "conversation_level": level,
            "steering_quality": quality,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = ConversationTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.turns) == 2

    def test_detection_markdown_all_sections(self) -> None:
        detection = ConversationSteeringDetection(
            conversation_id="t",
            dominant_state="cortisol",
            conversation_level="level_ii",
            evidence=[
                NeurochemicalEvidence(
                    state=s,  # type: ignore[arg-type]
                    score=0.5,
                    explanation=f"{s} explanation",
                )
                for s in NEUROCHEMICAL_STATES
            ],
            steering_quality="trust-eroding",
            interventions=[
                SteeringIntervention(
                    target_state="oxytocin",
                    intervention_type="add_open_question",
                    description="add a question",
                    original_phrasing="You're wrong.",
                    suggested_phrasing="Can you share more?",
                    estimated_impact="high",
                    rationale="opens conversation",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Conversation Steering Diagnostic" in md
        assert "TRUST-ERODING" in md
        assert "CORTISOL" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = ConversationSteeringDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = ConversationSteeringDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_turns_rejected(self) -> None:
        # Pydantic catches min_length=1 before reaching the generator
        with pytest.raises(Exception):
            _trace(turns=[])


class TestDetectionPipeline:
    def test_trust_eroding_with_interventions(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_state": "oxytocin",
                    "intervention_type": "add_open_question",
                    "description": "open question",
                    "original_phrasing": "You're wrong.",
                    "suggested_phrasing": "Tell me more.",
                    "estimated_impact": "high",
                    "rationale": "opens",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = ConversationSteeringDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_state == "cortisol"
        assert detection.steering_quality == "trust-eroding"
        assert detection.conversation_level == "level_ii"
        assert len(detection.evidence) == 3
        assert len(detection.interventions) == 1

    def test_trust_building_skips_interventions(self) -> None:
        payload = _payload(
            state="oxytocin",
            quality="trust-building",
            level="level_iii",
            scores={"cortisol": 0.0, "neutral": 0.1, "oxytocin": 0.9},
        )
        stub = _Stub([payload])
        det = ConversationSteeringDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.steering_quality == "trust-building"
        assert detection.interventions == []

    def test_missing_states_filled(self) -> None:
        partial = json.dumps(
            {
                "evidence": [_ev("cortisol", 0.9)],
                "dominant_state": "cortisol",
                "conversation_level": "level_ii",
                "steering_quality": "trust-eroding",
            }
        )
        det = ConversationSteeringDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {ev.state for ev in detection.evidence}
        assert present == set(NEUROCHEMICAL_STATES)

    def test_garbage_state_falls_back_to_highest_score(self) -> None:
        bad = json.dumps(
            {
                "evidence": [
                    _ev("cortisol", 0.8),
                    _ev("neutral", 0.1),
                    _ev("oxytocin", 0.05),
                ],
                "dominant_state": "totally-fake",
                "conversation_level": "level_ii",
                "steering_quality": "trust-eroding",
            }
        )
        det = ConversationSteeringDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_state == "cortisol"

    def test_all_zero_falls_back_to_neutral(self) -> None:
        bad = json.dumps(
            {
                "evidence": [
                    _ev("cortisol", 0.0),
                    _ev("neutral", 0.0),
                    _ev("oxytocin", 0.0),
                ],
                "dominant_state": "garbage",
                "conversation_level": "garbage",
                "steering_quality": "garbage",
            }
        )
        det = ConversationSteeringDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_state == "neutral"
        assert detection.conversation_level == "level_ii"
        # garbage quality + neutral dominant → neutral fallback
        assert detection.steering_quality == "neutral"

    def test_garbage_quality_uses_dominant_state(self) -> None:
        bad = json.dumps(
            {
                "evidence": [
                    _ev("cortisol", 0.8),
                    _ev("neutral", 0.1),
                    _ev("oxytocin", 0.0),
                ],
                "dominant_state": "cortisol",
                "conversation_level": "level_ii",
                "steering_quality": "garbage",
            }
        )
        det = ConversationSteeringDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        # cortisol dominant → trust-eroding
        assert detection.steering_quality == "trust-eroding"
