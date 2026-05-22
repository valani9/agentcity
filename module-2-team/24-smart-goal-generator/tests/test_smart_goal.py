"""Tests for the SMART Goal Generator."""

from __future__ import annotations

import json

import pytest

from agentcity.smart_goal import (
    SMART_CRITERIA,
    GoalRequest,
    KillCriterion,
    SMARTCriterion,
    SMARTGoal,
    SMARTGoalGenerator,
    SuccessMetric,
)


def _request(**overrides: object) -> GoalRequest:
    base: dict[str, object] = dict(
        goal_id="test",
        vague_goal="Improve the thing.",
    )
    base.update(overrides)
    return GoalRequest(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _strong_payload() -> str:
    return json.dumps(
        {
            "smart_statement": "Restated goal.",
            "criteria": [
                {"criterion": c, "statement": f"{c} statement", "quality_score": 0.9}
                for c in SMART_CRITERIA
            ],
            "completion_criteria": ["done condition 1", "done condition 2"],
            "success_metrics": [
                {"name": "metric_a", "target": ">=50%", "measurement_method": "Mixpanel"}
            ],
            "kill_criteria": [
                {
                    "name": "budget",
                    "condition": "tokens > 100k",
                    "action_on_trigger": "escalate_to_human",
                },
                {
                    "name": "deadline",
                    "condition": "past deadline",
                    "action_on_trigger": "escalate_to_human",
                },
            ],
            "deadline": "2026-06-30",
            "open_questions": [],
            "overall_smart_score": 0.9,
            "smart_quality": "strong",
        }
    )


class TestSchemaRoundtrip:
    def test_request_roundtrip(self) -> None:
        request = _request()
        restored = GoalRequest.model_validate_json(request.model_dump_json())
        assert restored.vague_goal == request.vague_goal

    def test_goal_markdown_all_sections(self) -> None:
        goal = SMARTGoal(
            goal_id="t",
            original_goal="Improve onboarding.",
            smart_statement="Lift activation from 35% to 50% by Q2.",
            criteria=[
                SMARTCriterion(
                    criterion=c,
                    statement=f"{c} statement",
                    quality_score=0.8,
                )
                for c in SMART_CRITERIA
            ],
            completion_criteria=["50% activation hit"],
            success_metrics=[
                SuccessMetric(name="rate", target=">=50%", measurement_method="Mixpanel")
            ],
            kill_criteria=[
                KillCriterion(
                    name="budget",
                    condition="tokens > 100k",
                    action_on_trigger="escalate_to_human",
                )
            ],
            deadline="2026-06-30",
            open_questions=["Q1?"],
            overall_smart_score=0.85,
            smart_quality="strong",
            generator_model="test-model",
        )
        md = goal.to_markdown()
        assert "SMART Goal" in md
        assert "STRONG" in md
        assert "SMART Criteria" in md
        assert "Completion Criteria" in md
        assert "Success Metrics" in md
        assert "Kill Criteria" in md
        assert "Deadline" in md
        assert "Open Questions" in md

    def test_agent_preamble_includes_kill_criteria(self) -> None:
        goal = SMARTGoal(
            original_goal="x",
            smart_statement="y",
            criteria=[],
            completion_criteria=["a"],
            success_metrics=[SuccessMetric(name="m", target="t", measurement_method="x")],
            kill_criteria=[
                KillCriterion(
                    name="budget",
                    condition="tokens > 100k",
                    action_on_trigger="escalate_to_human",
                )
            ],
            deadline="2026-06-30",
            overall_smart_score=0.8,
            smart_quality="strong",
        )
        preamble = goal.to_agent_preamble()
        assert "SMART GOAL" in preamble
        assert "tokens > 100k" in preamble
        assert "Kill criteria" in preamble


class TestValidation:
    def test_empty_vague_goal_rejected(self) -> None:
        gen = SMARTGoalGenerator(_Stub([_strong_payload()]))
        with pytest.raises(ValueError, match="vague_goal"):
            gen.run(_request(vague_goal=""))


class TestGenerationPipeline:
    def test_strong_end_to_end(self) -> None:
        stub = _Stub([_strong_payload()])
        gen = SMARTGoalGenerator(stub, model="test-model")
        goal = gen.run(_request())

        assert len(stub.calls) == 1
        assert goal.smart_quality == "strong"
        assert goal.overall_smart_score == 0.9
        assert len(goal.criteria) == 5
        assert len(goal.kill_criteria) == 2
        assert len(goal.completion_criteria) == 2
        assert len(goal.success_metrics) == 1
        assert goal.deadline == "2026-06-30"

    def test_missing_criteria_filled(self) -> None:
        # LLM returns only 2 of 5 criteria
        partial = json.loads(_strong_payload())
        partial["criteria"] = partial["criteria"][:2]
        stub = _Stub([json.dumps(partial)])
        gen = SMARTGoalGenerator(stub, model="test-model")
        goal = gen.run(_request())
        present = {c.criterion for c in goal.criteria}
        assert present == set(SMART_CRITERIA)
        # Filler entries have score 0.0
        filler = [c for c in goal.criteria if c.statement == "Not addressed by the generator."]
        assert len(filler) == 3

    def test_no_overall_score_recomputes(self) -> None:
        partial = json.loads(_strong_payload())
        del partial["overall_smart_score"]
        # Per-criteria quality_score is 0.9 across all 5; mean = 0.9
        stub = _Stub([json.dumps(partial)])
        goal = SMARTGoalGenerator(stub).run(_request())
        assert goal.overall_smart_score == pytest.approx(0.9)
        assert goal.smart_quality == "strong"

    def test_quality_reconciled_from_score(self) -> None:
        partial = json.loads(_strong_payload())
        partial["smart_quality"] = "garbage_value"
        partial["overall_smart_score"] = 0.6
        stub = _Stub([json.dumps(partial)])
        goal = SMARTGoalGenerator(stub).run(_request())
        assert goal.smart_quality == "acceptable"

    def test_malformed_kill_criteria_dropped_not_raised(self) -> None:
        partial = json.loads(_strong_payload())
        partial["kill_criteria"] = [
            {"name": "ok", "condition": "x", "action_on_trigger": "y"},
            "not a dict",
            {"missing_required_fields": True},
        ]
        stub = _Stub([json.dumps(partial)])
        goal = SMARTGoalGenerator(stub).run(_request())
        # Only the well-formed entry survives
        assert len(goal.kill_criteria) == 1
        assert goal.kill_criteria[0].name == "ok"

    def test_completely_empty_response_does_not_raise(self) -> None:
        # LLM returns "{}" — generator should fall back to defaults
        stub = _Stub(["{}"])
        goal = SMARTGoalGenerator(stub).run(_request())
        assert goal.smart_quality == "weak"
        assert goal.overall_smart_score == 0.0
        assert goal.deadline == "(not specified)"
        assert len(goal.criteria) == 5  # all filler


class TestQualityReconciliation:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.9, "strong"),
            (0.8, "strong"),
            (0.79, "acceptable"),
            (0.5, "acceptable"),
            (0.49, "weak"),
            (0.0, "weak"),
        ],
    )
    def test_threshold(self, score: float, expected: str) -> None:
        gen = SMARTGoalGenerator(_Stub([]))
        assert gen._reconcile_quality(None, score) == expected
