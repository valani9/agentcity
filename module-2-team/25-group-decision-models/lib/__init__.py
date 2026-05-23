"""agentcity.group_decision — facilitator-canon decision-aggregation
methods (concurring / majority / consensus / fist-to-five / unanimous)
applied to multi-agent decision-making.

Generative pattern. Takes a decision context and recommends the right
aggregation method + emits the protocol spec. Optionally tallies a
supplied vote set locally (deterministic Python, no extra LLM call).

Quick start:

    from agentcity.group_decision import (
        DecisionProtocolGenerator,
        DecisionRequest,
        DecisionOption,
        AgentVote,
    )
    from agentcity.aar.clients import AnthropicClient

    request = DecisionRequest(
        decision_id="db-choice-2026-05-22",
        title="Choose a database for the new analytics workload.",
        options=[
            DecisionOption(option_id="postgres", description="Postgres with read replicas."),
            DecisionOption(option_id="dynamodb", description="DynamoDB serverless."),
            DecisionOption(option_id="clickhouse", description="ClickHouse OLAP."),
        ],
        agents=["architect", "sre", "data-eng", "security"],
        stakes="high",
        reversibility="partial",
        buy_in_required=True,
    )
    protocol = DecisionProtocolGenerator(AnthropicClient()).run(request)
    print(protocol.to_markdown())
    # protocol.to_orchestrator_preamble() returns a condensed text block.

    # Once votes are in, pass them in to get the tally:
    votes = [
        AgentVote(agent_name="architect", option_id="postgres", score=4),
        AgentVote(agent_name="sre", option_id="postgres", score=4),
        AgentVote(agent_name="data-eng", option_id="clickhouse", score=3),
        AgentVote(agent_name="security", option_id="postgres", score=5),
    ]
    final = DecisionProtocolGenerator(AnthropicClient()).run(request, votes=votes)
    print(final.tally_result.winner)  # 'postgres'
"""

from .generator import DecisionProtocolGenerator, LLMClient
from .schema import (
    DECISION_MODELS,
    AgentVote,
    AggregationResult,
    DecisionOption,
    DecisionProtocol,
    DecisionRequest,
)
from .tally import tally_votes

__all__ = [
    "DecisionProtocolGenerator",
    "LLMClient",
    "DecisionRequest",
    "DecisionOption",
    "AgentVote",
    "AggregationResult",
    "DecisionProtocol",
    "DECISION_MODELS",
    "tally_votes",
]

__version__ = "0.1.0"
