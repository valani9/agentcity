"""Tests for the Cognitive Reappraisal Diagnostic."""

from __future__ import annotations

import json

import pytest

from agentcity.cognitive_reappraisal import (
    REGULATION_STRATEGIES,
    AgentRegulationTrace,
    ReappraisalDetector,
    RegulationDetection,
    RegulationIntervention,
    StrategyEvidence,
)


def _trace(**overrides: object) -> AgentRegulationTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        user_input="I'M DONE!!!",
        user_emotion_label="angry",
        user_emotion_intensity=0.9,
        agent_response="I understand. Per policy...",
        agent_internal_state="User unreasonable. Apply policy.",
        outcome="User escalated.",
        success=False,
    )
    base.update(overrides)
    return AgentRegulationTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _ev(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "strategy": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    dominant: str = "suppression",
    adaptivity: str = "maladaptive",
    scores: dict[str, float] | None = None,
) -> str:
    s = scores or {
        "reappraisal": 0.05,
        "suppression": 0.85,
        "rumination": 0.3,
        "avoidance": 0.5,
        "expression": 0.0,
        "none": 0.0,
    }
    return json.dumps(
        {
            "strategy_evidence": [_ev(k, v) for k, v in s.items()],
            "dominant_strategy": dominant,
            "adaptivity": adaptivity,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentRegulationTrace.model_validate_json(trace.model_dump_json())
        assert restored.user_input == trace.user_input

    def test_detection_markdown(self) -> None:
        detection = RegulationDetection(
            agent_id="t",
            strategy_evidence=[
                StrategyEvidence(
                    strategy=s,  # type: ignore[arg-type]
                    score=0.5,
                    explanation=f"{s} explanation",
                )
                for s in REGULATION_STRATEGIES
            ],
            dominant_strategy="suppression",
            adaptivity="maladaptive",
            interventions=[
                RegulationIntervention(
                    target_strategy="reappraisal",
                    direction="increase",
                    intervention_type="add_reframe_step",
                    description="reframe",
                    suggested_implementation="prompt",
                    estimated_impact="high",
                    rationale="closes",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Cognitive Reappraisal" in md
        assert "MALADAPTIVE" in md
        assert "suppression" in md


class TestValidation:
    def test_empty_user_input_rejected(self) -> None:
        det = ReappraisalDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="user_input"):
            det.run(_trace(user_input=""))

    def test_empty_agent_response_rejected(self) -> None:
        det = ReappraisalDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="agent_response"):
            det.run(_trace(agent_response=""))

    def test_empty_outcome_rejected(self) -> None:
        det = ReappraisalDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))


class TestDetectionPipeline:
    def test_maladaptive_triggers_interventions(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_strategy": "reappraisal",
                    "direction": "increase",
                    "intervention_type": "add_reframe_step",
                    "description": "reframe",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = ReappraisalDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 2
        assert detection.dominant_strategy == "suppression"
        assert detection.adaptivity == "maladaptive"
        assert len(detection.interventions) == 1

    def test_adaptive_skips_interventions(self) -> None:
        payload = _payload(
            dominant="reappraisal",
            adaptivity="adaptive",
            scores={
                "reappraisal": 0.9,
                "suppression": 0.1,
                "rumination": 0.1,
                "avoidance": 0.1,
                "expression": 0.0,
                "none": 0.0,
            },
        )
        stub = _Stub([payload])
        det = ReappraisalDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.adaptivity == "adaptive"
        assert detection.interventions == []

    def test_missing_strategies_filled(self) -> None:
        partial = json.dumps(
            {
                "strategy_evidence": [_ev("suppression", 0.8)],
                "dominant_strategy": "suppression",
                "adaptivity": "maladaptive",
            }
        )
        det = ReappraisalDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {ev.strategy for ev in detection.strategy_evidence}
        assert present == set(REGULATION_STRATEGIES)

    def test_garbage_dominant_falls_back_to_highest(self) -> None:
        bad = json.dumps(
            {
                "strategy_evidence": [
                    _ev("reappraisal", 0.05),
                    _ev("suppression", 0.85),
                    _ev("rumination", 0.3),
                    _ev("avoidance", 0.5),
                    _ev("expression", 0.0),
                    _ev("none", 0.0),
                ],
                "dominant_strategy": "totally-fake",
                "adaptivity": "maladaptive",
            }
        )
        det = ReappraisalDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_strategy == "suppression"

    def test_garbage_adaptivity_uses_dominant_fallback(self) -> None:
        bad = json.dumps(
            {
                "strategy_evidence": [
                    _ev("reappraisal", 0.05),
                    _ev("suppression", 0.85),
                    _ev("rumination", 0.3),
                    _ev("avoidance", 0.5),
                    _ev("expression", 0.0),
                    _ev("none", 0.0),
                ],
                "dominant_strategy": "suppression",
                "adaptivity": "garbage",
            }
        )
        det = ReappraisalDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        # suppression dominant → maladaptive
        assert detection.adaptivity == "maladaptive"
