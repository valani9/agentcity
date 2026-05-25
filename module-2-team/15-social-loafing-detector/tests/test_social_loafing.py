"""Tests for the Social Loafing Detector."""

from __future__ import annotations

import json

import pytest

from vstack.social_loafing import (
    AgentContribution,
    AgentMessage,
    LoafingIntervention,
    MultiAgentTaskTrace,
    SocialLoafingDetection,
    SocialLoafingDetector,
)


def _msg(from_agent: str, message_type: str = "proposal", content: str = "x") -> AgentMessage:
    return AgentMessage(  # type: ignore[arg-type]
        from_agent=from_agent,
        message_type=message_type,
        content=content,
    )


def _trace(**overrides: object) -> MultiAgentTaskTrace:
    base: dict[str, object] = dict(
        team_id="test",
        task="default task",
        agents=["a", "b"],
        messages=[_msg("a"), _msg("b")],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return MultiAgentTaskTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _contribution(
    name: str,
    share: float = 0.5,
    sub: int = 1,
    cos: int = 0,
    loaf: float = 0.0,
    role: str = "primary-contributor",
) -> dict[str, object]:
    return {
        "agent_name": name,
        "contribution_share": share,
        "substantive_work_count": sub,
        "cosmetic_work_count": cos,
        "loafing_score": loaf,
        "role": role,
        "explanation": "test",
        "evidence_quotes": [],
    }


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = MultiAgentTaskTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.messages) == 2

    def test_detection_markdown_all_sections(self) -> None:
        detection = SocialLoafingDetection(
            team_id="t",
            agent_contributions=[
                AgentContribution(
                    agent_name="a",
                    contribution_share=0.8,
                    substantive_work_count=4,
                    cosmetic_work_count=0,
                    loafing_score=0.0,
                    role="primary-contributor",
                    explanation="did all the work",
                    evidence_quotes=[],
                ),
                AgentContribution(
                    agent_name="b",
                    contribution_share=0.05,
                    substantive_work_count=0,
                    cosmetic_work_count=2,
                    loafing_score=0.95,
                    role="loafer",
                    explanation="rubber-stamps",
                    evidence_quotes=["b: 'LGTM'"],
                ),
            ],
            gini_coefficient=0.7,
            loafing_quality="severe-loafing",
            interventions=[
                LoafingIntervention(
                    target_agent="b",
                    intervention_type="individual_accountability",
                    description="name the deliverable",
                    suggested_implementation="prompt patch",
                    estimated_impact="high",
                    rationale="counters loafing",
                )
            ],
            generator_model="test-model",
            success=True,
        )
        md = detection.to_markdown()
        assert "Social Loafing Detection" in md
        assert "Per-Agent Contribution" in md
        assert "Recommended Interventions" in md
        assert "0.70" in md  # gini


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = SocialLoafingDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = SocialLoafingDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_single_agent_rejected(self) -> None:
        det = SocialLoafingDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            det.run(_trace(agents=["a"]))

    def test_empty_messages_rejected(self) -> None:
        det = SocialLoafingDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="messages"):
            det.run(_trace(messages=[]))


class TestDetectionPipeline:
    def test_severe_loafing(self) -> None:
        contributions = json.dumps(
            [
                _contribution("a", 0.85, 5, 0, 0.05, "primary-contributor"),
                _contribution("b", 0.02, 0, 1, 1.0, "loafer"),
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_agent": "b",
                    "intervention_type": "individual_accountability",
                    "description": "name deliverable",
                    "suggested_implementation": "patch",
                    "estimated_impact": "high",
                    "rationale": "counters loafing",
                }
            ]
        )
        stub = _Stub([contributions, interventions])
        det = SocialLoafingDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.loafing_quality == "severe-loafing"
        # 2-agent case caps Gini at 0.5; concentration on one agent is ~0.48.
        assert detection.gini_coefficient >= 0.4
        assert len(detection.interventions) == 1

    def test_no_loafing_skips_interventions(self) -> None:
        contributions = json.dumps(
            [
                _contribution("a", 0.5, 2, 0, 0.0, "primary-contributor"),
                _contribution("b", 0.5, 2, 0, 0.0, "primary-contributor"),
            ]
        )
        stub = _Stub([contributions, "[]"])
        det = SocialLoafingDetector(stub, model="test-model")
        detection = det.run(_trace())
        # no-loafing => single LLM call only
        assert len(stub.calls) == 1
        assert detection.loafing_quality == "no-loafing"
        assert detection.interventions == []

    def test_absent_agents_filled(self) -> None:
        contributions = json.dumps([_contribution("a", 0.9, 5, 0, 0.0, "primary-contributor")])
        det = SocialLoafingDetector(_Stub([contributions, "[]"]))
        detection = det.run(_trace())
        # Agent "b" wasn't in the LLM response — should be filled as absent
        names = {c.agent_name for c in detection.agent_contributions}
        assert names == {"a", "b"}
        absent = next(c for c in detection.agent_contributions if c.agent_name == "b")
        assert absent.role == "absent"


class TestGini:
    def test_perfectly_equal(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contributions = [
            AgentContribution(
                agent_name=n,
                contribution_share=0.25,
                substantive_work_count=1,
                cosmetic_work_count=0,
                loafing_score=0.0,
                role="primary-contributor",
                explanation="x",
            )
            for n in ["a", "b", "c", "d"]
        ]
        gini = det._gini(contributions)
        assert gini == 0.0

    def test_one_does_everything(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contributions = [
            AgentContribution(
                agent_name="a",
                contribution_share=1.0,
                substantive_work_count=10,
                cosmetic_work_count=0,
                loafing_score=0.0,
                role="primary-contributor",
                explanation="x",
            ),
            AgentContribution(
                agent_name="b",
                contribution_share=0.0,
                substantive_work_count=0,
                cosmetic_work_count=0,
                loafing_score=1.0,
                role="absent",
                explanation="x",
            ),
        ]
        gini = det._gini(contributions)
        # Two-agent case: max gini is 0.5
        assert gini >= 0.4

    def test_zero_total_share(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contributions = [
            AgentContribution(
                agent_name=n,
                contribution_share=0.0,
                substantive_work_count=0,
                cosmetic_work_count=0,
                loafing_score=1.0,
                role="absent",
                explanation="x",
            )
            for n in ["a", "b"]
        ]
        assert det._gini(contributions) == 0.0


class TestLoafingQualityThresholds:
    def _contribs(self, shares: list[float], roles: list[str]) -> list[AgentContribution]:
        return [
            AgentContribution(
                agent_name=f"agent{i}",
                contribution_share=share,
                substantive_work_count=1,
                cosmetic_work_count=0,
                loafing_score=1.0 if role in ("loafer", "absent") else 0.0,
                role=role,  # type: ignore[arg-type]
                explanation="x",
            )
            for i, (share, role) in enumerate(zip(shares, roles))
        ]

    def test_no_loafing_balanced(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contribs = self._contribs([0.33, 0.33, 0.33], ["primary-contributor"] * 3)
        assert det._loafing_quality(contribs, 0.0) == "no-loafing"

    def test_severe_loafing_half_loafers(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contribs = self._contribs([0.5, 0.0], ["primary-contributor", "loafer"])
        assert det._loafing_quality(contribs, 0.5) == "severe-loafing"

    def test_mild_loafing_one_quarter(self) -> None:
        det = SocialLoafingDetector(_Stub([]))
        contribs = self._contribs([0.3, 0.3, 0.3, 0.1], ["primary-contributor"] * 3 + ["loafer"])
        assert det._loafing_quality(contribs, 0.35) == "mild-loafing"
