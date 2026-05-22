"""Tests for the McGregor Theory X/Y Orchestrator Mode Detector."""

from __future__ import annotations

import json

import pytest

from agentcity.mcgregor import (
    ModeIndicators,
    OrchestratorIntervention,
    OrchestratorModeDetection,
    OrchestratorModeDetector,
    OrchestratorStep,
    OrchestratorTrace,
    TaskProperties,
)


def _step(
    content: str = "x",
    step_type: str = "delegate",
    actor: str = "orchestrator",
    sub_agent: str | None = "runner",
) -> OrchestratorStep:
    return OrchestratorStep(  # type: ignore[arg-type]
        step_type=step_type,
        actor=actor,
        sub_agent=sub_agent,
        content=content,
    )


def _props(**overrides: object) -> TaskProperties:
    base: dict[str, object] = dict(
        risk_level="low",
        complexity="routine",
        reversibility="reversible",
        regulatory_exposure=False,
        agent_capability="proven",
    )
    base.update(overrides)
    return TaskProperties(**base)  # type: ignore[arg-type]


def _trace(**overrides: object) -> OrchestratorTrace:
    base: dict[str, object] = dict(
        trace_id="test",
        task="default task",
        sub_agents=["runner"],
        task_properties=_props(),
        steps=[_step()],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return OrchestratorTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _mode_payload(
    observed: str = "theory_x",
    optimal: str = "theory_y",
    mismatch: float = 0.8,
    quality: str = "severe-mismatch",
) -> str:
    return json.dumps(
        {
            "observed_mode": observed,
            "optimal_mode": optimal,
            "mode_mismatch": mismatch,
            "indicators": {
                "check_in_frequency": 0.9,
                "autonomy_granted": 0.1,
                "pre_approval_required": 0.9,
                "intervention_rate": 0.4,
                "explanation": "Pre-approval before every step.",
                "evidence_quotes": ["Approved. Execute step 2."],
            },
            "mode_quality": quality,
            "rationale": "Low-risk routine task does not need step-by-step approval.",
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = OrchestratorTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = OrchestratorModeDetection(
            trace_id="t",
            observed_mode="theory_x",
            optimal_mode="theory_y",
            mode_mismatch=0.8,
            indicators=ModeIndicators(
                check_in_frequency=0.9,
                autonomy_granted=0.1,
                pre_approval_required=0.9,
                intervention_rate=0.4,
                explanation="x",
                evidence_quotes=["q"],
            ),
            mode_quality="severe-mismatch",
            rationale="x",
            interventions=[
                OrchestratorIntervention(
                    target_mode="theory_y",
                    intervention_type="remove_pre_approval_gates",
                    description="drop gates",
                    suggested_implementation="cfg",
                    estimated_impact="high",
                    rationale="closes overhead",
                )
            ],
            generator_model="test-model",
            success=True,
        )
        md = detection.to_markdown()
        assert "Orchestrator Mode Detection" in md
        assert "SEVERE-MISMATCH" in md
        assert "theory_x" in md
        assert "theory_y" in md
        assert "Mode Indicators" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = OrchestratorModeDetector(_Stub([_mode_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = OrchestratorModeDetector(_Stub([_mode_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_sub_agents_rejected(self) -> None:
        det = OrchestratorModeDetector(_Stub([_mode_payload(), "[]"]))
        with pytest.raises(ValueError, match="sub_agents"):
            det.run(_trace(sub_agents=[]))

    def test_empty_steps_rejected(self) -> None:
        det = OrchestratorModeDetector(_Stub([_mode_payload(), "[]"]))
        with pytest.raises(ValueError, match="steps"):
            det.run(_trace(steps=[]))


class TestDetectionPipeline:
    def test_severe_mismatch(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_mode": "theory_y",
                    "intervention_type": "remove_pre_approval_gates",
                    "description": "drop gates",
                    "suggested_implementation": "cfg",
                    "estimated_impact": "high",
                    "rationale": "closes overhead",
                }
            ]
        )
        stub = _Stub([_mode_payload(), interventions])
        det = OrchestratorModeDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.observed_mode == "theory_x"
        assert detection.optimal_mode == "theory_y"
        assert detection.mode_mismatch == 0.8
        assert detection.mode_quality == "severe-mismatch"
        assert len(detection.interventions) == 1

    def test_well_matched_skips_interventions(self) -> None:
        stub = _Stub(
            [
                _mode_payload(
                    observed="theory_y", optimal="theory_y", mismatch=0.05, quality="well-matched"
                )
            ]
        )
        det = OrchestratorModeDetector(stub, model="test-model")
        detection = det.run(_trace())
        # well-matched => single call only
        assert len(stub.calls) == 1
        assert detection.mode_quality == "well-matched"
        assert detection.interventions == []

    def test_invalid_mode_coerces_to_hybrid(self) -> None:
        bad = json.dumps(
            {
                "observed_mode": "garbage",
                "optimal_mode": "garbage",
                "mode_mismatch": 0.6,
                "indicators": {
                    "check_in_frequency": 0.5,
                    "autonomy_granted": 0.5,
                    "pre_approval_required": 0.5,
                    "intervention_rate": 0.5,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
                "mode_quality": "mild-mismatch",
                "rationale": "x",
            }
        )
        det = OrchestratorModeDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.observed_mode == "hybrid"
        assert detection.optimal_mode == "hybrid"

    def test_quality_inferred_from_mismatch(self) -> None:
        bad = json.dumps(
            {
                "observed_mode": "theory_x",
                "optimal_mode": "theory_y",
                "mode_mismatch": 0.7,
                "indicators": {
                    "check_in_frequency": 0.5,
                    "autonomy_granted": 0.5,
                    "pre_approval_required": 0.5,
                    "intervention_rate": 0.5,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
                "mode_quality": "garbage",
                "rationale": "x",
            }
        )
        # mismatch 0.7 => severe-mismatch
        det = OrchestratorModeDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.mode_quality == "severe-mismatch"

    def test_completely_empty_response_does_not_raise(self) -> None:
        stub = _Stub(["{}"])
        det = OrchestratorModeDetector(stub, model="test-model")
        detection = det.run(_trace())
        # All defaults
        assert detection.observed_mode == "hybrid"
        assert detection.optimal_mode == "hybrid"
        assert detection.mode_mismatch == 0.0
        assert detection.mode_quality == "well-matched"


class TestModeQualityThresholds:
    @pytest.mark.parametrize(
        "mismatch,expected",
        [
            (0.0, "well-matched"),
            (0.2, "well-matched"),
            (0.21, "mild-mismatch"),
            (0.5, "mild-mismatch"),
            (0.51, "severe-mismatch"),
            (1.0, "severe-mismatch"),
        ],
    )
    def test_threshold(self, mismatch: float, expected: str) -> None:
        det = OrchestratorModeDetector(_Stub([]))
        assert det._mode_quality(mismatch, "") == expected

    def test_explicit_quality_passed_through(self) -> None:
        det = OrchestratorModeDetector(_Stub([]))
        # Even with low mismatch, an explicit "severe-mismatch" should pass through
        assert det._mode_quality(0.1, "severe-mismatch") == "severe-mismatch"
