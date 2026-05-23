"""Tests for the 4 Motivation Traps Detector."""

from __future__ import annotations

import json

import pytest

from agentcity.motivation_traps import (
    MOTIVATION_TRAPS,
    AgentMotivationTrace,
    MotivationDetection,
    MotivationIntervention,
    MotivationTrapsDetector,
    TrapEvidence,
)


def _trace(**overrides: object) -> AgentMotivationTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        task_class="research",
        observed_behaviors=["did the thing"],
        self_reports=["I can't do this"],
        abandonment_signal="refused after one attempt",
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentMotivationTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _ev(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "trap": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "abandoning",
    dominant: str = "self_efficacy",
    scores: dict[str, float] | None = None,
) -> str:
    s = scores or {"values": 0.1, "self_efficacy": 0.8, "emotions": 0.15, "attribution": 0.7}
    return json.dumps(
        {
            "trap_evidence": [
                _ev("values", s["values"]),
                _ev("self_efficacy", s["self_efficacy"]),
                _ev("emotions", s["emotions"]),
                _ev("attribution", s["attribution"]),
            ],
            "dominant_trap": dominant,
            "motivation_quality": quality,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentMotivationTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = MotivationDetection(
            agent_id="t",
            task_class="research",
            trap_evidence=[
                TrapEvidence(
                    trap=t,  # type: ignore[arg-type]
                    score=0.5,
                    explanation=f"{t} explanation",
                )
                for t in MOTIVATION_TRAPS
            ],
            dominant_trap="self_efficacy",
            motivation_quality="at-risk",
            interventions=[
                MotivationIntervention(
                    target_trap="self_efficacy",
                    intervention_type="scaffold_subtasks",
                    description="add subtasks",
                    suggested_implementation="new prompt",
                    estimated_impact="high",
                    rationale="closes gap",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "4 Motivation Traps Diagnostic" in md
        assert "AT-RISK" in md
        assert "self_efficacy" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = MotivationTrapsDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = MotivationTrapsDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_abandonment_signal_rejected(self) -> None:
        det = MotivationTrapsDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="abandonment_signal"):
            det.run(_trace(abandonment_signal=""))


class TestDetectionPipeline:
    def test_abandoning_with_dominant_trap(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_trap": "self_efficacy",
                    "intervention_type": "scaffold_subtasks",
                    "description": "scaffold",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = MotivationTrapsDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.motivation_quality == "abandoning"
        assert detection.dominant_trap == "self_efficacy"
        assert len(detection.trap_evidence) == 4
        assert len(detection.interventions) == 1

    def test_motivated_skips_interventions(self) -> None:
        payload = _payload(
            quality="motivated",
            dominant="none",
            scores={"values": 0.1, "self_efficacy": 0.1, "emotions": 0.1, "attribution": 0.1},
        )
        stub = _Stub([payload])
        det = MotivationTrapsDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.motivation_quality == "motivated"
        assert detection.dominant_trap == "none"
        assert detection.interventions == []

    def test_missing_traps_filled(self) -> None:
        partial = json.dumps(
            {
                "trap_evidence": [_ev("self_efficacy", 0.8)],
                "dominant_trap": "self_efficacy",
                "motivation_quality": "abandoning",
            }
        )
        det = MotivationTrapsDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {ev.trap for ev in detection.trap_evidence}
        assert present == set(MOTIVATION_TRAPS)

    def test_garbage_dominant_falls_back_to_highest(self) -> None:
        bad = json.dumps(
            {
                "trap_evidence": [
                    _ev("values", 0.1),
                    _ev("self_efficacy", 0.8),
                    _ev("emotions", 0.2),
                    _ev("attribution", 0.7),
                ],
                "dominant_trap": "totally-fake",
                "motivation_quality": "abandoning",
            }
        )
        det = MotivationTrapsDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_trap == "self_efficacy"

    def test_garbage_dominant_with_all_low_falls_back_to_none(self) -> None:
        bad = json.dumps(
            {
                "trap_evidence": [
                    _ev("values", 0.1),
                    _ev("self_efficacy", 0.2),
                    _ev("emotions", 0.1),
                    _ev("attribution", 0.15),
                ],
                "dominant_trap": "totally-fake",
                "motivation_quality": "motivated",
            }
        )
        det = MotivationTrapsDetector(_Stub([bad]))
        detection = det.run(_trace())
        assert detection.dominant_trap == "none"


class TestQualityFallback:
    def test_quality_falls_back_to_scoring(self) -> None:
        # LLM returns garbage quality; should be inferred from dominant trap's score
        bad = json.dumps(
            {
                "trap_evidence": [
                    _ev("values", 0.1),
                    _ev("self_efficacy", 0.7),
                    _ev("emotions", 0.1),
                    _ev("attribution", 0.1),
                ],
                "dominant_trap": "self_efficacy",
                "motivation_quality": "garbage",
            }
        )
        det = MotivationTrapsDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        # score 0.7 > 0.6 → abandoning
        assert detection.motivation_quality == "abandoning"
