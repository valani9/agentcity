"""Tests for the Plus/Delta Feedback Format generator."""

from __future__ import annotations

import json

import pytest

from agentcity.plus_delta import (
    Commitment,
    DeltaItem,
    FeedbackRequest,
    PlusDeltaFeedback,
    PlusDeltaFeedbackGenerator,
    PlusItem,
)


def _request(**overrides: object) -> FeedbackRequest:
    base: dict[str, object] = dict(
        feedback_id="test",
        reviewer_agent="reviewer",
        subject_agent="subject",
        task_context="default task",
        contribution_summary="contribution summary",
        contribution_artifact="some artifact content",
    )
    base.update(overrides)
    return FeedbackRequest(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _payload(
    overall: str = "iterate",
    n_plus: int = 2,
    n_delta: int = 2,
    delta_severities: list[str] | None = None,
) -> str:
    if delta_severities is None:
        delta_severities = ["moderate"] * n_delta
    return json.dumps(
        {
            "plus_items": [
                {
                    "statement": f"plus statement {i}",
                    "evidence": f"plus evidence {i}",
                    "impact": f"plus impact {i}",
                    "keep_doing": f"keep doing {i}",
                }
                for i in range(n_plus)
            ],
            "delta_items": [
                {
                    "statement": f"delta statement {i}",
                    "evidence": f"delta evidence {i}",
                    "impact": f"delta impact {i}",
                    "alternative": f"do X instead {i}",
                    "severity": delta_severities[i],
                }
                for i in range(n_delta)
            ],
            "commitments": [
                {"by_agent": "subject", "commitment": "will improve X"},
            ],
            "overall_assessment": overall,
            "feedback_quality_score": 0.85,
        }
    )


class TestSchemaRoundtrip:
    def test_request_roundtrip(self) -> None:
        request = _request()
        restored = FeedbackRequest.model_validate_json(request.model_dump_json())
        assert restored.reviewer_agent == request.reviewer_agent

    def test_feedback_markdown_all_sections(self) -> None:
        feedback = PlusDeltaFeedback(
            feedback_id="t",
            reviewer_agent="senior",
            subject_agent="junior",
            task_context="refactor task",
            contribution_summary="cleaned up middleware",
            plus_items=[
                PlusItem(
                    statement="split into 3 modules",
                    evidence="Module 1, 2, 3",
                    impact="single responsibility",
                    keep_doing="lead with structure",
                )
            ],
            delta_items=[
                DeltaItem(
                    statement="surface underlying error",
                    evidence="validate_token catches all",
                    impact="ops can't debug",
                    alternative="catch typed errors and re-raise",
                    severity="critical",
                )
            ],
            commitments=[
                Commitment(by_agent="junior", commitment="rewrite validate_token next round")
            ],
            overall_assessment="iterate",
            feedback_quality_score=0.85,
            generator_model="test-model",
        )
        md = feedback.to_markdown()
        assert "Plus/Delta Feedback" in md
        assert "Plus (keep doing)" in md
        assert "Delta (change for next time)" in md
        assert "Commitments" in md
        assert "ITERATE" in md
        assert "critical" in md

    def test_inline_form(self) -> None:
        feedback = PlusDeltaFeedback(
            reviewer_agent="r",
            subject_agent="s",
            task_context="t",
            contribution_summary="c",
            plus_items=[PlusItem(statement="p", evidence="e", impact="i")],
            delta_items=[
                DeltaItem(
                    statement="d",
                    evidence="e",
                    impact="i",
                    alternative="alt",
                    severity="moderate",
                )
            ],
            overall_assessment="iterate",
            feedback_quality_score=0.7,
        )
        inline = feedback.to_inline_feedback()
        assert "FEEDBACK from r -> s" in inline
        assert "Plus:" in inline
        assert "Delta:" in inline


class TestValidation:
    def test_empty_reviewer_rejected(self) -> None:
        gen = PlusDeltaFeedbackGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="reviewer_agent"):
            gen.run(_request(reviewer_agent=""))

    def test_empty_subject_rejected(self) -> None:
        gen = PlusDeltaFeedbackGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="subject_agent"):
            gen.run(_request(subject_agent=""))

    def test_empty_task_context_rejected(self) -> None:
        gen = PlusDeltaFeedbackGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="task_context"):
            gen.run(_request(task_context=""))

    def test_empty_artifact_rejected(self) -> None:
        gen = PlusDeltaFeedbackGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="contribution_artifact"):
            gen.run(_request(contribution_artifact=""))


class TestGenerationPipeline:
    def test_iterate_end_to_end(self) -> None:
        stub = _Stub([_payload(overall="iterate")])
        gen = PlusDeltaFeedbackGenerator(stub, model="test-model")
        feedback = gen.run(_request())

        assert len(stub.calls) == 1
        assert feedback.overall_assessment == "iterate"
        assert len(feedback.plus_items) == 2
        assert len(feedback.delta_items) == 2
        assert len(feedback.commitments) == 1
        assert feedback.feedback_quality_score == 0.85

    def test_max_items_caps_apply(self) -> None:
        # LLM returns 6 plus items; cap is 3
        big = _payload(overall="iterate", n_plus=6, n_delta=6)
        stub = _Stub([big])
        gen = PlusDeltaFeedbackGenerator(stub)
        feedback = gen.run(_request(max_items_per_category=3))
        assert len(feedback.plus_items) == 3
        assert len(feedback.delta_items) == 3

    def test_overall_inferred_from_severity(self) -> None:
        # LLM omits overall_assessment; generator should infer from delta severities
        partial = json.loads(_payload(n_delta=1, delta_severities=["critical"]))
        del partial["overall_assessment"]
        gen = PlusDeltaFeedbackGenerator(_Stub([json.dumps(partial)]))
        feedback = gen.run(_request())
        assert feedback.overall_assessment == "rework"  # critical => rework

    def test_overall_inferred_moderate(self) -> None:
        partial = json.loads(_payload(n_delta=2, delta_severities=["moderate", "nit"]))
        del partial["overall_assessment"]
        gen = PlusDeltaFeedbackGenerator(_Stub([json.dumps(partial)]))
        feedback = gen.run(_request())
        assert feedback.overall_assessment == "iterate"  # moderate => iterate

    def test_overall_inferred_keep_going(self) -> None:
        partial = json.loads(_payload(n_delta=1, delta_severities=["nit"]))
        del partial["overall_assessment"]
        gen = PlusDeltaFeedbackGenerator(_Stub([json.dumps(partial)]))
        feedback = gen.run(_request())
        assert feedback.overall_assessment == "keep-going"  # only nits => keep-going

    def test_empty_response_uses_defaults(self) -> None:
        gen = PlusDeltaFeedbackGenerator(_Stub(["{}"]))
        feedback = gen.run(_request())
        assert feedback.overall_assessment == "keep-going"  # no deltas, no criticals
        assert feedback.plus_items == []
        assert feedback.delta_items == []
        assert feedback.feedback_quality_score == 0.5

    def test_malformed_items_dropped_not_raised(self) -> None:
        bad = json.dumps(
            {
                "plus_items": [
                    {"statement": "good", "evidence": "e", "impact": "i", "keep_doing": ""},
                    "not a dict",
                    {"missing_required": True},
                ],
                "delta_items": [],
                "overall_assessment": "keep-going",
                "feedback_quality_score": 0.5,
            }
        )
        gen = PlusDeltaFeedbackGenerator(_Stub([bad]))
        feedback = gen.run(_request())
        # Only the well-formed plus item survives
        assert len(feedback.plus_items) == 1
        assert feedback.plus_items[0].statement == "good"
