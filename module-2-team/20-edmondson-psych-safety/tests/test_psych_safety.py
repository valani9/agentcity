"""Tests for the Psychological Safety Detector."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from vstack.psych_safety import (
    BEHAVIORS,
    AgentMessage,
    BehaviorEvidence,
    MultiAgentSafetyTrace,
    PsychologicalSafetyDetection,
    PsychologicalSafetyDetector,
    SafetyIntervention,
)


def _msg(content: str, frm: str = "alpha", mt: str = "task") -> AgentMessage:
    return AgentMessage(
        timestamp=datetime.now(timezone.utc),
        from_agent=frm,
        content=content,
        message_type=mt,  # type: ignore[arg-type]
    )


def _trace(**overrides: object) -> MultiAgentSafetyTrace:
    base: dict[str, object] = dict(
        team_id="test-team",
        goal="default goal",
        agents=["alpha", "beta"],
        messages=[_msg("hello")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return MultiAgentSafetyTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._responses.pop(0) if self._responses else ""


class TestSchema:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = MultiAgentSafetyTrace.model_validate_json(trace.model_dump_json())
        assert restored.goal == trace.goal

    def test_detection_markdown_all_sections(self) -> None:
        det = PsychologicalSafetyDetection(
            team_id="t",
            safety_score=0.3,
            team_climate="silenced",
            behavior_scores={b: 0.25 for b in BEHAVIORS},
            behaviors=[
                BehaviorEvidence(
                    behavior="voice",
                    presence_score=0.1,
                    severity_of_absence="high",
                    explanation="no disagreement observed",
                    evidence_quotes=["alpha agreed without challenge"],
                )
            ],
            blocking_behaviors=["verifier approved without inspection"],
            interventions=[
                SafetyIntervention(
                    target_behavior="voice",
                    intervention_type="dissent_round",
                    description="mandatory dissent",
                    suggested_implementation="add dissent step",
                    estimated_impact="high",
                    rationale="grows voice",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = det.to_markdown()
        assert "Psychological Safety" in md
        assert "Behavior Presence Scores" in md
        assert "Evidence by Behavior" in md
        assert "Blocking Behaviors" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_goal_rejected(self) -> None:
        det = PsychologicalSafetyDetector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="goal"):
            det.run(_trace(goal=""))

    def test_single_agent_rejected(self) -> None:
        det = PsychologicalSafetyDetector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            det.run(_trace(agents=["solo"]))

    def test_no_messages_rejected(self) -> None:
        det = PsychologicalSafetyDetector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="messages"):
            det.run(_trace(messages=[]))


class TestPipeline:
    def test_end_to_end(self) -> None:
        analysis = json.dumps(
            {
                "behaviors": [
                    {
                        "behavior": "voice",
                        "presence_score": 0.1,
                        "severity_of_absence": "high",
                        "explanation": "silent",
                        "evidence_quotes": [],
                    },
                    {
                        "behavior": "help-seeking",
                        "presence_score": 0.2,
                        "severity_of_absence": "high",
                        "explanation": "no questions",
                        "evidence_quotes": [],
                    },
                    {
                        "behavior": "error-reporting",
                        "presence_score": 0.05,
                        "severity_of_absence": "high",
                        "explanation": "no admissions",
                        "evidence_quotes": [],
                    },
                    {
                        "behavior": "boundary-spanning",
                        "presence_score": 0.0,
                        "severity_of_absence": "high",
                        "explanation": "no challenges",
                        "evidence_quotes": [],
                    },
                ],
                "blocking_behaviors": ["verifier approved without inspection"],
            }
        )
        interventions = json.dumps(
            [
                {
                    "target_behavior": "error-reporting",
                    "intervention_type": "uncertainty_surfacing",
                    "description": "require confidence reports",
                    "suggested_implementation": "prompt patch",
                    "estimated_impact": "high",
                    "rationale": "grows error-reporting",
                }
            ]
        )
        det = PsychologicalSafetyDetector(_Stub([analysis, interventions]))
        detection = det.run(_trace())
        assert detection.team_climate == "silenced"
        assert detection.safety_score < 0.35
        assert len(detection.behaviors) == 4
        assert detection.blocking_behaviors == ["verifier approved without inspection"]

    def test_missing_behaviors_filled(self) -> None:
        analysis = json.dumps(
            {
                "behaviors": [
                    {
                        "behavior": "voice",
                        "presence_score": 0.8,
                        "severity_of_absence": "none",
                        "explanation": "single behavior reported",
                        "evidence_quotes": [],
                    }
                ],
                "blocking_behaviors": [],
            }
        )
        det = PsychologicalSafetyDetector(_Stub([analysis, "[]"]))
        detection = det.run(_trace())
        present = {ev.behavior for ev in detection.behaviors}
        assert present == set(BEHAVIORS)


class TestClimateThresholds:
    @pytest.mark.parametrize(
        "safety,expected",
        [
            (0.1, "silenced"),
            (0.34, "silenced"),
            (0.35, "cautious"),
            (0.64, "cautious"),
            (0.65, "safe"),
            (0.9, "safe"),
        ],
    )
    def test_threshold(self, safety: float, expected: str) -> None:
        det = PsychologicalSafetyDetector(_Stub([]))
        assert det._climate(safety) == expected
