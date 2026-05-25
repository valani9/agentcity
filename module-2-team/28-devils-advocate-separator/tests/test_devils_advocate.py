"""Tests for the Devil's Advocate Role Separator."""

from __future__ import annotations

import json

import pytest

from vstack.devils_advocate import (
    PHASES,
    PhaseEvidence,
    RoleSeparationDetection,
    RoleSeparationDetector,
    RoleSeparationIntervention,
    RoleStep,
    SingleAgentTrace,
)


def _step(content: str, type_: str = "plan", actor: str = "primary") -> RoleStep:
    return RoleStep(type=type_, actor=actor, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> SingleAgentTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        steps=[_step("step", "plan")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return SingleAgentTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _phase(
    phase: str,
    present: bool = True,
    actor: str = "primary",
    score: float = 0.7,
) -> dict[str, object]:
    return {
        "phase": phase,
        "present": present,
        "actor": actor,
        "substantive_score": score,
        "explanation": "test",
        "evidence_quotes": [],
    }


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = SingleAgentTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = RoleSeparationDetection(
            agent_id="t",
            role_separation_quality="fully-conflated",
            role_separation_score=0.1,
            locus_of_judgment="self-reviewed",
            phase_evidence=[
                PhaseEvidence(
                    phase="plan",
                    present=True,
                    actor="primary",
                    substantive_score=0.8,
                    explanation="proposed db",
                    evidence_quotes=["Step 1: 'recommend DynamoDB'"],
                )
            ],
            self_approval_rate=1.0,
            interventions=[
                RoleSeparationIntervention(
                    target_phase="external_critique",
                    intervention_type="add_critic_agent",
                    description="add critic",
                    suggested_implementation="route to second agent",
                    estimated_impact="high",
                    rationale="separates roles",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Role-Separation Detection" in md
        assert "Phase Evidence" in md
        assert "Recommended Interventions" in md
        assert "plan" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = RoleSeparationDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = RoleSeparationDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_steps_rejected(self) -> None:
        det = RoleSeparationDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="steps"):
            det.run(_trace(steps=[]))


class TestDetectionPipeline:
    def test_fully_conflated_self_reviewed(self) -> None:
        phases = json.dumps(
            [
                _phase("plan", True, "primary", 0.8),
                _phase("execute", True, "primary", 0.7),
                _phase("self_evaluate", True, "primary", 0.2),
                _phase("external_critique", False, "primary", 0.0),
            ]
        )
        det = RoleSeparationDetector(_Stub([phases, "[]"]))
        detection = det.run(_trace())
        assert detection.role_separation_quality == "fully-conflated"
        assert detection.locus_of_judgment == "self-reviewed"

    def test_well_separated_external_critique(self) -> None:
        phases = json.dumps(
            [
                _phase("plan", True, "primary", 0.8),
                _phase("execute", True, "primary", 0.7),
                _phase("self_evaluate", False, "primary", 0.0),
                _phase("external_critique", True, "critic", 0.8),
            ]
        )
        det = RoleSeparationDetector(_Stub([phases, "[]"]))
        detection = det.run(_trace())
        assert detection.role_separation_quality == "well-separated"
        assert detection.locus_of_judgment == "externally-reviewed"
        # Well-separated => no interventions proposed
        assert detection.interventions == []

    def test_missing_phases_filled(self) -> None:
        phases = json.dumps([_phase("plan", True, "primary", 0.8)])
        det = RoleSeparationDetector(_Stub([phases, "[]"]))
        detection = det.run(_trace())
        present_phases = {ev.phase for ev in detection.phase_evidence}
        assert present_phases == set(PHASES)

    def test_mixed_locus(self) -> None:
        phases = json.dumps(
            [
                _phase("plan", True, "primary", 0.8),
                _phase("execute", True, "primary", 0.7),
                _phase("self_evaluate", True, "primary", 0.5),
                _phase("external_critique", True, "critic", 0.6),
            ]
        )
        det = RoleSeparationDetector(_Stub([phases, "[]"]))
        detection = det.run(_trace())
        assert detection.locus_of_judgment == "mixed"

    def test_unreviewed_locus(self) -> None:
        phases = json.dumps(
            [
                _phase("plan", True, "primary", 0.8),
                _phase("execute", True, "primary", 0.7),
                _phase("self_evaluate", False, "primary", 0.0),
                _phase("external_critique", False, "primary", 0.0),
            ]
        )
        det = RoleSeparationDetector(_Stub([phases, "[]"]))
        detection = det.run(_trace())
        assert detection.locus_of_judgment == "unreviewed"


class TestSelfApprovalRate:
    def test_no_self_evaluate_steps(self) -> None:
        det = RoleSeparationDetector(_Stub([]))
        rate = det._self_approval_rate(_trace())
        assert rate == 0.0

    def test_all_approvals(self) -> None:
        det = RoleSeparationDetector(_Stub([]))
        trace = _trace(
            steps=[
                _step("plan A", "plan"),
                _step("looks good", "self_evaluate"),
                _step("ship it", "self_evaluate"),
            ]
        )
        assert det._self_approval_rate(trace) == 1.0

    def test_mixed_approvals(self) -> None:
        det = RoleSeparationDetector(_Stub([]))
        trace = _trace(
            steps=[
                _step("plan A", "plan"),
                _step("looks good", "self_evaluate"),
                _step("actually wrong, let me revise", "self_evaluate"),
            ]
        )
        assert det._self_approval_rate(trace) == 0.5
