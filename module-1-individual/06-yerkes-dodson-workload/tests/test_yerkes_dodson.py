"""Tests for the Yerkes-Dodson Optimal Workload Diagnostic."""

from __future__ import annotations

import json

import pytest

from vstack.yerkes_dodson import (
    AgentPerformanceTrace,
    PressureInputs,
    WorkloadDetection,
    WorkloadDetector,
    WorkloadIntervention,
    WorkloadZoneEvidence,
)


def _trace(**overrides: object) -> AgentPerformanceTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        pressure=PressureInputs(),
        observed_behaviors=["did the thing"],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return AgentPerformanceTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _zone(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "zone": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    observed_zone: str = "over_pressure",
    failure_mode: str = "hallucinating",
    distance: float = 0.85,
    n_interventions: int = 2,
) -> str:
    interventions = [
        {
            "target_zone": "optimal",
            "intervention_type": "loosen_deadline",
            "direction": "decrease_pressure",
            "description": "more time",
            "suggested_implementation": "config",
            "estimated_impact": "high",
            "rationale": "restore headroom",
        }
        for _ in range(n_interventions)
    ]
    return json.dumps(
        {
            "zone_evidence": [
                _zone("under_pressure", 0.0),
                _zone("optimal", 0.1),
                _zone("over_pressure", 0.9),
            ],
            "observed_zone": observed_zone,
            "distance_from_optimal": distance,
            "failure_mode": failure_mode,
            "interventions": interventions,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentPerformanceTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = WorkloadDetection(
            agent_id="t",
            observed_zone="over_pressure",
            zone_evidence=[
                WorkloadZoneEvidence(
                    zone="over_pressure",
                    score=0.9,
                    explanation="absurd pressure on complex task",
                    evidence_quotes=["agent cited fabricated paper"],
                )
            ],
            distance_from_optimal=0.85,
            failure_mode="hallucinating",
            interventions=[
                WorkloadIntervention(
                    target_zone="optimal",
                    intervention_type="loosen_deadline",
                    direction="decrease_pressure",
                    description="more time",
                    suggested_implementation="config",
                    estimated_impact="high",
                    rationale="restore headroom",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Yerkes-Dodson" in md
        assert "OVER_PRESSURE" in md
        assert "hallucinating" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = WorkloadDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = WorkloadDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_behaviors_rejected(self) -> None:
        det = WorkloadDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="observed_behaviors"):
            det.run(_trace(observed_behaviors=[]))


class TestDetectionPipeline:
    def test_over_pressure_hallucinating(self) -> None:
        stub = _Stub([_payload()])
        det = WorkloadDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 1
        assert detection.observed_zone == "over_pressure"
        assert detection.failure_mode == "hallucinating"
        assert detection.distance_from_optimal == 0.85
        assert len(detection.zone_evidence) == 3
        assert len(detection.interventions) == 2

    def test_optimal_skips_interventions(self) -> None:
        payload = _payload(
            observed_zone="optimal", failure_mode="focused", distance=0.05, n_interventions=2
        )
        stub = _Stub([payload])
        det = WorkloadDetector(stub, model="test-model")
        detection = det.run(_trace())
        # Even if LLM returns interventions, generator drops them when zone is optimal
        assert detection.observed_zone == "optimal"
        assert detection.failure_mode == "focused"
        assert detection.interventions == []

    def test_missing_zones_filled(self) -> None:
        partial = json.dumps(
            {
                "zone_evidence": [_zone("over_pressure", 0.9)],
                "observed_zone": "over_pressure",
                "distance_from_optimal": 0.85,
                "failure_mode": "hallucinating",
                "interventions": [],
            }
        )
        det = WorkloadDetector(_Stub([partial]))
        detection = det.run(_trace())
        present = {ev.zone for ev in detection.zone_evidence}
        assert present == {"under_pressure", "optimal", "over_pressure"}

    def test_garbage_zone_falls_back_to_highest(self) -> None:
        bad = json.dumps(
            {
                "zone_evidence": [
                    _zone("under_pressure", 0.1),
                    _zone("optimal", 0.2),
                    _zone("over_pressure", 0.8),
                ],
                "observed_zone": "garbage_value",
                "distance_from_optimal": 0.8,
                "failure_mode": "garbage_mode",
                "interventions": [],
            }
        )
        det = WorkloadDetector(_Stub([bad]))
        detection = det.run(_trace())
        # Falls back to highest-scoring zone
        assert detection.observed_zone == "over_pressure"
        # Garbage failure mode falls back based on zone
        assert detection.failure_mode == "corner_cutting"

    def test_empty_response_uses_defaults(self) -> None:
        det = WorkloadDetector(_Stub(["{}"]))
        detection = det.run(_trace())
        assert detection.observed_zone == "optimal"  # default
        assert detection.failure_mode == "focused"
        assert detection.distance_from_optimal == 0.0


class TestFailureModeFallback:
    @pytest.mark.parametrize(
        "zone,expected_mode",
        [
            ("optimal", "focused"),
            ("under_pressure", "wandering"),
            ("over_pressure", "corner_cutting"),
        ],
    )
    def test_zone_to_mode(self, zone: str, expected_mode: str) -> None:
        det = WorkloadDetector(_Stub([]))
        assert det._coerce_failure_mode(None, zone) == expected_mode
