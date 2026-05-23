"""Tests for the Strengths-as-Weaknesses Detector."""

from __future__ import annotations

import json

import pytest

from agentcity.grant_strengths import (
    STRENGTHS,
    AgentBehaviorStep,
    AgentBehaviorTrace,
    StrengthIntervention,
    StrengthOveruseDetection,
    StrengthOveruseEvidence,
    StrengthsOveruseDetector,
)


def _step(content: str = "x", type_: str = "output") -> AgentBehaviorStep:
    return AgentBehaviorStep(type=type_, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentBehaviorTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        steps=[_step()],
        outcome="default outcome",
        success=False,
        harm_visible=False,
    )
    base.update(overrides)
    return AgentBehaviorTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _strength(name: str, overuse: float = 0.5, sev: str = "medium") -> dict[str, object]:
    return {
        "strength": name,
        "overuse_score": overuse,
        "severity": sev,
        "explanation": "test",
        "evidence_quotes": [],
    }


def _payload(
    dominant: str = "helpfulness",
    quality: str = "overused",
    harm: str = "high",
    helpfulness_score: float = 0.95,
) -> str:
    return json.dumps(
        {
            "strengths": [
                _strength("helpfulness", helpfulness_score, "high"),
                _strength("agreeableness", 0.3, "low"),
                _strength("thoroughness", 0.0, "none"),
                _strength("caution", 0.0, "none"),
                _strength("confidence", 0.0, "none"),
                _strength("brevity", 0.0, "none"),
                _strength("precision", 0.0, "none"),
            ],
            "dominant_overuse": dominant,
            "harm_caused": harm,
            "overuse_quality": quality,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentBehaviorTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = StrengthOveruseDetection(
            agent_id="t",
            dominant_overuse="helpfulness",
            strength_scores={s: 0.1 for s in STRENGTHS},
            strengths=[
                StrengthOveruseEvidence(
                    strength="helpfulness",
                    overuse_score=0.9,
                    severity="high",
                    explanation="dropped a table because user asked nicely",
                    evidence_quotes=["DROP TABLE users"],
                )
            ],
            harm_caused="high",
            overuse_quality="overused",
            interventions=[
                StrengthIntervention(
                    target_strength="helpfulness",
                    intervention_type="add_destructive_action_gate",
                    description="add a gate",
                    suggested_implementation="pipeline",
                    estimated_impact="high",
                    rationale="bounds without removing",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Strengths-as-Weaknesses Detection" in md
        assert "OVERUSED" in md
        assert "helpfulness" in md
        assert "high" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = StrengthsOveruseDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = StrengthsOveruseDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_steps_rejected(self) -> None:
        det = StrengthsOveruseDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="steps"):
            det.run(_trace(steps=[]))


class TestDetectionPipeline:
    def test_helpfulness_overuse(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_strength": "helpfulness",
                    "intervention_type": "add_destructive_action_gate",
                    "description": "gate",
                    "suggested_implementation": "pipeline",
                    "estimated_impact": "high",
                    "rationale": "bounds helpfulness",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = StrengthsOveruseDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_overuse == "helpfulness"
        assert detection.overuse_quality == "overused"
        assert detection.harm_caused == "high"
        assert detection.strength_scores["helpfulness"] == 0.95
        assert len(detection.strengths) == 7
        assert len(detection.interventions) == 1

    def test_healthy_skips_interventions(self) -> None:
        payload = json.dumps(
            {
                "strengths": [_strength(s, 0.0, "none") for s in STRENGTHS],
                "dominant_overuse": "none-observed",
                "harm_caused": "none",
                "overuse_quality": "healthy",
            }
        )
        stub = _Stub([payload])
        det = StrengthsOveruseDetector(stub, model="test-model")
        detection = det.run(_trace(success=True))
        # healthy => single call only
        assert len(stub.calls) == 1
        assert detection.overuse_quality == "healthy"
        assert detection.dominant_overuse == "none-observed"
        assert detection.interventions == []

    def test_missing_strengths_filled(self) -> None:
        partial = json.dumps(
            {
                "strengths": [_strength("helpfulness", 0.9, "high")],
                "dominant_overuse": "helpfulness",
                "harm_caused": "high",
                "overuse_quality": "overused",
            }
        )
        det = StrengthsOveruseDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {ev.strength for ev in detection.strengths}
        assert present == set(STRENGTHS)

    def test_garbage_dominant_falls_back_to_scores(self) -> None:
        payload = _payload(dominant="garbage_value")
        det = StrengthsOveruseDetector(_Stub([payload, "[]"]))
        detection = det.run(_trace())
        # Fallback should pick the highest-scoring strength: helpfulness
        assert detection.dominant_overuse == "helpfulness"


class TestOveruseQualityThresholds:
    @pytest.mark.parametrize(
        "max_score,expected",
        [
            (0.0, "healthy"),
            (0.2, "healthy"),
            (0.3, "borderline"),
            (0.5, "borderline"),
            (0.6, "overused"),
            (0.9, "overused"),
        ],
    )
    def test_threshold(self, max_score: float, expected: str) -> None:
        det = StrengthsOveruseDetector(_Stub([]))
        scores = {s: 0.0 for s in STRENGTHS}
        scores["helpfulness"] = max_score
        assert det._overuse_quality(scores, "") == expected
