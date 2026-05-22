"""Deterministic vote-tally logic for the five decision-aggregation models.

This is pure Python — no LLM call — so it runs locally after the recommended
protocol has been picked. The LLM picks the method; this module runs it on
the actual votes.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from .schema import AgentVote, AggregationResult


def tally_votes(
    method: Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"],
    votes: list[AgentVote],
    quorum: int | None,
) -> AggregationResult:
    """Run the chosen aggregation method against the supplied votes."""
    if not votes:
        return AggregationResult(
            method_used=method,
            winner=None,
            outcome="insufficient_votes",
            vote_counts={},
            explanation="No votes were supplied.",
        )

    if quorum is not None and len(votes) < quorum:
        return AggregationResult(
            method_used=method,
            winner=None,
            outcome="no_quorum",
            vote_counts={},
            explanation=f"Only {len(votes)} votes recorded; quorum is {quorum}.",
        )

    if method == "concurring":
        return _tally_concurring(votes)
    if method == "majority":
        return _tally_majority(votes)
    if method == "consensus":
        return _tally_consensus(votes)
    if method == "fist_to_five":
        return _tally_fist_to_five(votes)
    if method == "unanimous":
        return _tally_unanimous(votes)
    return AggregationResult(
        method_used=method,
        winner=None,
        outcome="insufficient_votes",
        explanation=f"Unknown method: {method}",
    )


# --- Per-method tally functions -----------------------------------------


def _tally_concurring(votes: list[AgentVote]) -> AggregationResult:
    """First non-abstain vote with no objections wins.

    Objections are votes for a different option OR a vote with score == 0
    (an explicit block, even if the method is nominally not fist-to-five —
    we treat an explicit block as a veto-of-concurrence).
    """
    counts = _option_counts(votes)
    blockers = [v.agent_name for v in votes if v.score == 0]
    if blockers:
        return AggregationResult(
            method_used="concurring",
            winner=None,
            outcome="blocked",
            vote_counts=counts,
            dissenters=blockers,
            explanation=f"Explicit block from: {', '.join(blockers)}.",
        )

    first_non_abstain = next((v for v in votes if v.option_id is not None), None)
    if first_non_abstain is None:
        return AggregationResult(
            method_used="concurring",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            explanation="No agent cast a positive vote; all abstained.",
        )

    winning_option = first_non_abstain.option_id
    dissenters = [
        v.agent_name for v in votes if v.option_id is not None and v.option_id != winning_option
    ]
    if dissenters:
        return AggregationResult(
            method_used="concurring",
            winner=None,
            outcome="blocked",
            vote_counts=counts,
            dissenters=dissenters,
            explanation=(
                "Concurring requires no objection; the following agents voted "
                f"differently: {', '.join(dissenters)}."
            ),
        )
    return AggregationResult(
        method_used="concurring",
        winner=winning_option,
        outcome="decided",
        vote_counts=counts,
        dissenters=[],
        explanation=(f"Decisive vote by {first_non_abstain.agent_name}; no objections."),
    )


def _tally_majority(votes: list[AgentVote]) -> AggregationResult:
    """Plurality with a >50% threshold on cast (non-abstain) votes."""
    cast = [v for v in votes if v.option_id is not None]
    counts = _option_counts(votes)
    if not cast:
        return AggregationResult(
            method_used="majority",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            explanation="All agents abstained.",
        )
    most_common = Counter(v.option_id for v in cast).most_common()
    top_option, top_count = most_common[0]
    needed = (len(cast) // 2) + 1
    if top_count < needed:
        # Could be a tie at the top
        if len(most_common) > 1 and most_common[1][1] == top_count:
            return AggregationResult(
                method_used="majority",
                winner=None,
                outcome="tied",
                vote_counts=counts,
                dissenters=[],
                explanation=(f"Top options tied at {top_count} votes; need {needed} for majority."),
            )
        return AggregationResult(
            method_used="majority",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            explanation=(
                f"Top option had {top_count}/{len(cast)} votes; majority requires {needed}."
            ),
        )
    dissenters = [
        v.agent_name for v in votes if v.option_id is not None and v.option_id != top_option
    ]
    return AggregationResult(
        method_used="majority",
        winner=top_option,
        outcome="decided",
        vote_counts=counts,
        dissenters=dissenters,
        explanation=f"Majority: {top_count}/{len(cast)} for `{top_option}`.",
    )


def _tally_consensus(votes: list[AgentVote]) -> AggregationResult:
    """Consensus: everyone affirms (or at least does not block).

    A blocker is an agent who explicitly voted for a different option or
    has score == 0.
    """
    counts = _option_counts(votes)
    cast = [v for v in votes if v.option_id is not None]
    if not cast:
        return AggregationResult(
            method_used="consensus",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            explanation="No positive votes cast.",
        )
    # Identify the most-voted option; treat that as the consensus proposal.
    most_common = Counter(v.option_id for v in cast).most_common()
    top_option, _ = most_common[0]
    blockers = [
        v.agent_name
        for v in votes
        if (v.option_id is not None and v.option_id != top_option) or v.score == 0
    ]
    if blockers:
        return AggregationResult(
            method_used="consensus",
            winner=None,
            outcome="blocked",
            vote_counts=counts,
            dissenters=blockers,
            explanation=(
                f"Consensus blocked. {len(blockers)} dissenter(s): {', '.join(blockers)}."
            ),
        )
    return AggregationResult(
        method_used="consensus",
        winner=top_option,
        outcome="decided",
        vote_counts=counts,
        dissenters=[],
        explanation="No blocks; consensus reached.",
    )


def _tally_fist_to_five(votes: list[AgentVote]) -> AggregationResult:
    """Fist-to-five: per-agent score 0-5. Block (0) wins over average.

    Pass criterion: every agent's score >= 2 AND mean >= 3 for the chosen
    option. A 0 ("fist") is a hard block regardless of mean.
    """
    counts = _option_counts(votes)
    by_option: dict[str, list[AgentVote]] = {}
    for v in votes:
        if v.option_id is None or v.score is None:
            continue
        by_option.setdefault(v.option_id, []).append(v)

    if not by_option:
        return AggregationResult(
            method_used="fist_to_five",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            explanation="No fist-to-five scores recorded.",
        )

    averages = {
        opt: round(sum(v.score for v in votes_list if v.score is not None) / len(votes_list), 2)
        for opt, votes_list in by_option.items()
    }
    # Find the option with the highest average that has no blockers (score=0).
    candidates = sorted(by_option.items(), key=lambda kv: -averages[kv[0]])
    for option_id, option_votes in candidates:
        blockers = [v.agent_name for v in option_votes if v.score == 0]
        if blockers:
            continue
        if averages[option_id] >= 3.0:
            return AggregationResult(
                method_used="fist_to_five",
                winner=option_id,
                outcome="decided",
                vote_counts=counts,
                fist_to_five_averages=averages,
                dissenters=[
                    v.agent_name for v in option_votes if v.score is not None and v.score <= 2
                ],
                explanation=(
                    f"`{option_id}` selected with mean score {averages[option_id]:.2f}; "
                    "no blocking fists."
                ),
            )

    # If every option has a blocker, surface that.
    all_blockers: list[str] = []
    for opt, opt_votes in by_option.items():
        all_blockers.extend(v.agent_name for v in opt_votes if v.score == 0)
    if all_blockers:
        return AggregationResult(
            method_used="fist_to_five",
            winner=None,
            outcome="blocked",
            vote_counts=counts,
            fist_to_five_averages=averages,
            dissenters=list(dict.fromkeys(all_blockers)),
            explanation="Every option had at least one blocking fist (score=0).",
        )
    return AggregationResult(
        method_used="fist_to_five",
        winner=None,
        outcome="insufficient_votes",
        vote_counts=counts,
        fist_to_five_averages=averages,
        explanation="No option reached the mean-score threshold of 3.0.",
    )


def _tally_unanimous(votes: list[AgentVote]) -> AggregationResult:
    """Unanimous: every agent must positively vote for the SAME option."""
    counts = _option_counts(votes)
    cast = [v for v in votes if v.option_id is not None]
    if len(cast) != len(votes):
        abstainers = [v.agent_name for v in votes if v.option_id is None]
        return AggregationResult(
            method_used="unanimous",
            winner=None,
            outcome="insufficient_votes",
            vote_counts=counts,
            dissenters=abstainers,
            explanation=(
                f"Unanimous requires positive votes from every agent; "
                f"{len(abstainers)} abstained: {', '.join(abstainers)}."
            ),
        )
    options_voted = {v.option_id for v in cast}
    if len(options_voted) == 1:
        winning = cast[0].option_id
        return AggregationResult(
            method_used="unanimous",
            winner=winning,
            outcome="decided",
            vote_counts=counts,
            dissenters=[],
            explanation="All agents voted for the same option.",
        )
    return AggregationResult(
        method_used="unanimous",
        winner=None,
        outcome="blocked",
        vote_counts=counts,
        dissenters=[v.agent_name for v in cast if v.option_id != cast[0].option_id],
        explanation="Unanimous failed; agents voted for different options.",
    )


# --- Helpers ------------------------------------------------------------


def _option_counts(votes: list[AgentVote]) -> dict[str, int]:
    return dict(Counter(v.option_id for v in votes if v.option_id is not None))
