"""Tests for the Thomas-Kilmann Conflict Style Selector."""

from __future__ import annotations

import json

import pytest

from vstack.thomas_kilmann import (
    STYLES,
    AgentInteractionTrace,
    ConflictStyleSelection,
    ConflictStyleSelector,
    InteractionTurn,
    StyleRecommendation,
    StyleScore,
)


def _turn(role: str, content: str) -> InteractionTurn:
    return InteractionTurn(role=role, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentInteractionTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        turns=[_turn("user", "hi"), _turn("agent", "hello")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentInteractionTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._responses.pop(0) if self._responses else ""


class TestSchema:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentInteractionTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_selection_markdown_all_sections(self) -> None:
        sel = ConflictStyleSelection(
            agent_id="t",
            observed_style="accommodating",
            optimal_style="collaborating",
            style_mismatch=0.7,
            assertiveness_score=0.1,
            cooperativeness_score=0.9,
            observed_style_scores={s: 0.0 for s in STYLES},
            style_evidence=[
                StyleScore(
                    style="accommodating",
                    score=0.9,
                    explanation="yielded to user demand",
                    evidence_quotes=["agent: refund 100%"],
                )
            ],
            rationale="collaborating would have surfaced underlying need",
            recommendations=[
                StyleRecommendation(
                    intervention_type="prompt_patch",
                    description="explore underlying need",
                    suggested_implementation="ask for underlying need first",
                    estimated_impact="high",
                    rationale="shifts from accommodating to collaborating",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = sel.to_markdown()
        assert "Thomas-Kilmann Conflict Style Selection" in md
        assert "Style Scores" in md
        assert "Rationale" in md
        assert "Evidence by Style" in md
        assert "Recommendations" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        sel = ConflictStyleSelector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="task"):
            sel.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        sel = ConflictStyleSelector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            sel.run(_trace(outcome=""))

    def test_empty_turns_rejected(self) -> None:
        sel = ConflictStyleSelector(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="turns"):
            sel.run(_trace(turns=[]))


class TestPipeline:
    def test_end_to_end_with_mismatch_triggers_recommendations(self) -> None:
        selection = json.dumps(
            {
                "observed_style": "accommodating",
                "optimal_style": "collaborating",
                "style_mismatch": 0.7,
                "assertiveness_score": 0.1,
                "cooperativeness_score": 0.9,
                "observed_style_scores": {s: 0.0 for s in STYLES},
                "style_evidence": [
                    {
                        "style": "accommodating",
                        "score": 0.9,
                        "explanation": "yielded",
                        "evidence_quotes": [],
                    }
                ],
                "rationale": "collaborating preferred",
            }
        )
        recs = json.dumps(
            [
                {
                    "intervention_type": "prompt_patch",
                    "description": "explore underlying need",
                    "suggested_implementation": "ask question",
                    "estimated_impact": "high",
                    "rationale": "shifts style",
                }
            ]
        )
        stub = _Stub([selection, recs])
        sel_runner = ConflictStyleSelector(stub, model="test-model")
        sel_out = sel_runner.run(_trace())
        assert sel_out.observed_style == "accommodating"
        assert sel_out.optimal_style == "collaborating"
        assert sel_out.style_mismatch == 0.7
        assert len(sel_out.recommendations) == 1

    def test_no_recommendations_when_styles_match(self) -> None:
        """When observed == optimal and mismatch is low, no recommendations."""
        selection = json.dumps(
            {
                "observed_style": "collaborating",
                "optimal_style": "collaborating",
                "style_mismatch": 0.0,
                "assertiveness_score": 0.7,
                "cooperativeness_score": 0.8,
                "observed_style_scores": {s: 0.0 for s in STYLES},
                "style_evidence": [],
                "rationale": "agent matched the optimal style",
            }
        )
        sel_runner = ConflictStyleSelector(_Stub([selection]))
        sel_out = sel_runner.run(_trace(success=True))
        assert sel_out.observed_style == "collaborating"
        assert sel_out.optimal_style == "collaborating"
        assert sel_out.recommendations == []

    def test_coercion_handles_malformed_styles(self) -> None:
        """Bad LLM output for style fields should fall back to safe defaults."""
        selection = json.dumps(
            {
                "observed_style": "not-a-real-style",
                "optimal_style": "also-invalid",
                "style_mismatch": "not a number",
                "assertiveness_score": 99,
                "cooperativeness_score": -5,
                "observed_style_scores": {"competing": "nope"},
                "style_evidence": [],
                "rationale": "",
            }
        )
        sel_runner = ConflictStyleSelector(_Stub([selection, "[]"]))
        sel_out = sel_runner.run(_trace())
        assert sel_out.observed_style == "mixed"  # safe default
        assert sel_out.optimal_style == "collaborating"  # safe default
        assert 0.0 <= sel_out.assertiveness_score <= 1.0
        assert 0.0 <= sel_out.cooperativeness_score <= 1.0
