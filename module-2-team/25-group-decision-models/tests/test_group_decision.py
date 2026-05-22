"""Tests for the Group Decision Models generator + tally."""

from __future__ import annotations

import json

import pytest

from agentcity.group_decision import (
    DECISION_MODELS,
    AgentVote,
    AggregationResult,
    DecisionOption,
    DecisionProtocol,
    DecisionProtocolGenerator,
    DecisionRequest,
    tally_votes,
)


def _request(**overrides: object) -> DecisionRequest:
    base: dict[str, object] = dict(
        decision_id="test",
        title="Pick an option.",
        options=[
            DecisionOption(option_id="a", description="A"),
            DecisionOption(option_id="b", description="B"),
        ],
        agents=["agent-1", "agent-2", "agent-3"],
        stakes="medium",
    )
    base.update(overrides)
    return DecisionRequest(**base)  # type: ignore[arg-type]


def _vote(
    agent: str,
    option: str | None = "a",
    score: int | None = None,
) -> AgentVote:
    return AgentVote(agent_name=agent, option_id=option, score=score)


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _payload(model: str = "majority", quorum: int | None = None) -> str:
    return json.dumps(
        {
            "recommended_model": model,
            "rationale": "test",
            "protocol_steps": ["step 1", "step 2", "step 3"],
            "threshold": f"{model} threshold",
            "quorum": quorum,
            "tie_breaker": "highest confidence",
            "fallback_model": "consensus",
        }
    )


class TestSchemaRoundtrip:
    def test_request_roundtrip(self) -> None:
        request = _request()
        restored = DecisionRequest.model_validate_json(request.model_dump_json())
        assert restored.title == request.title

    def test_protocol_markdown_all_sections(self) -> None:
        protocol = DecisionProtocol(
            decision_id="t",
            title="Pick A or B",
            recommended_model="majority",
            rationale="balanced stakes",
            protocol_steps=["step1", "step2"],
            threshold=">50%",
            quorum=2,
            tie_breaker="highest confidence",
            fallback_model="consensus",
            tally_result=AggregationResult(
                method_used="majority",
                winner="a",
                outcome="decided",
                vote_counts={"a": 2, "b": 1},
                dissenters=["agent-3"],
                explanation="2/3 for a",
            ),
            generator_model="test-model",
        )
        md = protocol.to_markdown()
        assert "Group Decision Protocol" in md
        assert "majority" in md
        assert "Tally Result" in md
        assert "agent-3" in md
        assert "Protocol Steps" in md
        assert "2 agents required" in md

    def test_orchestrator_preamble(self) -> None:
        protocol = DecisionProtocol(
            decision_id="t",
            title="Pick",
            recommended_model="fist_to_five",
            rationale="x",
            protocol_steps=["step1"],
            threshold="mean>=3 no block",
            tie_breaker="confidence",
            fallback_model="consensus",
        )
        preamble = protocol.to_orchestrator_preamble()
        assert "DECISION PROTOCOL" in preamble
        assert "Model: fist_to_five" in preamble
        assert "Threshold" in preamble


class TestValidation:
    def test_empty_title_rejected(self) -> None:
        gen = DecisionProtocolGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="title"):
            gen.run(_request(title=""))

    def test_single_option_rejected(self) -> None:
        gen = DecisionProtocolGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="at least 2 options"):
            gen.run(_request(options=[DecisionOption(option_id="a", description="A")]))

    def test_single_agent_rejected(self) -> None:
        gen = DecisionProtocolGenerator(_Stub([_payload()]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            gen.run(_request(agents=["only-agent"]))


class TestGeneratorPipeline:
    def test_majority_recommendation(self) -> None:
        stub = _Stub([_payload(model="majority")])
        gen = DecisionProtocolGenerator(stub, model="test-model")
        protocol = gen.run(_request())
        assert len(stub.calls) == 1
        assert protocol.recommended_model == "majority"
        assert len(protocol.protocol_steps) == 3
        assert protocol.threshold == "majority threshold"
        assert protocol.fallback_model == "consensus"
        assert protocol.tally_result is None  # no votes supplied

    def test_forced_model_overrides_llm(self) -> None:
        # LLM says majority; request forces consensus
        stub = _Stub([_payload(model="majority")])
        gen = DecisionProtocolGenerator(stub, model="test-model")
        protocol = gen.run(_request(forced_model="consensus"))
        assert protocol.recommended_model == "consensus"

    def test_garbage_model_falls_back_to_majority(self) -> None:
        bad = json.dumps(
            {
                "recommended_model": "garbage_value",
                "protocol_steps": [],
                "threshold": "",
                "quorum": None,
                "tie_breaker": "",
                "fallback_model": None,
            }
        )
        gen = DecisionProtocolGenerator(_Stub([bad]))
        protocol = gen.run(_request())
        assert protocol.recommended_model == "majority"
        # Default protocol steps populate when LLM returned none
        assert len(protocol.protocol_steps) >= 2

    def test_empty_llm_response_uses_defaults(self) -> None:
        gen = DecisionProtocolGenerator(_Stub(["{}"]))
        protocol = gen.run(_request())
        assert protocol.recommended_model == "majority"
        # Default majority threshold is ">50% of cast votes."
        assert ">50%" in protocol.threshold
        assert len(protocol.protocol_steps) >= 2

    def test_votes_trigger_tally(self) -> None:
        stub = _Stub([_payload(model="majority")])
        gen = DecisionProtocolGenerator(stub, model="test-model")
        votes = [_vote("agent-1", "a"), _vote("agent-2", "a"), _vote("agent-3", "b")]
        protocol = gen.run(_request(), votes=votes)
        assert protocol.tally_result is not None
        assert protocol.tally_result.winner == "a"
        assert protocol.tally_result.outcome == "decided"
        assert protocol.tally_result.dissenters == ["agent-3"]


# --- Tally tests (one class per method) ---------------------------------


class TestTallyConcurring:
    def test_clean_concurrence(self) -> None:
        votes = [_vote("a", "x"), _vote("b", None), _vote("c", None)]
        result = tally_votes("concurring", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "x"

    def test_blocked_by_dissent(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "y")]
        result = tally_votes("concurring", votes, quorum=None)
        assert result.outcome == "blocked"
        assert result.winner is None

    def test_blocked_by_explicit_fist(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x", score=0)]
        result = tally_votes("concurring", votes, quorum=None)
        assert result.outcome == "blocked"

    def test_all_abstain(self) -> None:
        votes = [_vote("a", None), _vote("b", None)]
        result = tally_votes("concurring", votes, quorum=None)
        assert result.outcome == "insufficient_votes"


class TestTallyMajority:
    def test_clear_majority(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", "y")]
        result = tally_votes("majority", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "x"
        assert result.vote_counts == {"x": 2, "y": 1}

    def test_tied(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "y")]
        result = tally_votes("majority", votes, quorum=None)
        assert result.outcome == "tied"

    def test_quorum_failure(self) -> None:
        votes = [_vote("a", "x")]
        result = tally_votes("majority", votes, quorum=3)
        assert result.outcome == "no_quorum"


class TestTallyConsensus:
    def test_consensus_reached(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", "x")]
        result = tally_votes("consensus", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "x"

    def test_blocked_by_one_dissent(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", "y")]
        result = tally_votes("consensus", votes, quorum=None)
        assert result.outcome == "blocked"
        assert "c" in result.dissenters


class TestTallyFistToFive:
    def test_mean_above_threshold(self) -> None:
        votes = [
            _vote("a", "x", score=4),
            _vote("b", "x", score=5),
            _vote("c", "x", score=3),
        ]
        result = tally_votes("fist_to_five", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "x"
        assert result.fist_to_five_averages == {"x": 4.0}

    def test_block_wins_over_high_mean(self) -> None:
        votes = [
            _vote("a", "x", score=5),
            _vote("b", "x", score=5),
            _vote("c", "x", score=0),
        ]
        result = tally_votes("fist_to_five", votes, quorum=None)
        assert result.outcome == "blocked"
        assert "c" in result.dissenters

    def test_no_option_reaches_threshold(self) -> None:
        votes = [_vote("a", "x", score=2), _vote("b", "x", score=2)]
        result = tally_votes("fist_to_five", votes, quorum=None)
        assert result.outcome == "insufficient_votes"

    def test_picks_higher_mean_unblocked(self) -> None:
        votes = [
            _vote("a", "x", score=3),
            _vote("b", "x", score=3),
            _vote("c", "y", score=5),
            _vote("d", "y", score=5),
        ]
        result = tally_votes("fist_to_five", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "y"
        assert result.fist_to_five_averages == {"x": 3.0, "y": 5.0}


class TestTallyUnanimous:
    def test_all_agree(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", "x")]
        result = tally_votes("unanimous", votes, quorum=None)
        assert result.outcome == "decided"
        assert result.winner == "x"

    def test_blocked_by_dissent(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", "y")]
        result = tally_votes("unanimous", votes, quorum=None)
        assert result.outcome == "blocked"

    def test_one_abstain(self) -> None:
        votes = [_vote("a", "x"), _vote("b", "x"), _vote("c", None)]
        result = tally_votes("unanimous", votes, quorum=None)
        assert result.outcome == "insufficient_votes"


class TestDecisionModelsConstant:
    def test_models_constant_includes_all(self) -> None:
        assert set(DECISION_MODELS) == {
            "concurring",
            "majority",
            "consensus",
            "fist_to_five",
            "unanimous",
        }
