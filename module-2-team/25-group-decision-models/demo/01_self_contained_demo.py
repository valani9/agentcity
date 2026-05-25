"""Self-contained demo of the Group Decision Models generator.

Synthetic scenario: a 4-agent architecture team must choose a database
for a new high-stakes, partially-reversible analytics workload. The
agents have moderate expertise asymmetry and post-decision buy-in is
required (they'll all be implementing). The generator recommends
fist-to-five (the right call when lukewarm support is the biggest risk
and buy-in matters) and runs the local tally on a supplied vote set.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    vstack_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.group_decision import (
        AgentVote,
        DecisionOption,
        DecisionProtocolGenerator,
        DecisionRequest,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_request() -> DecisionRequest:
    return DecisionRequest(
        decision_id="db-choice-2026-05-22",
        title="Choose a database for the new analytics workload.",
        options=[
            DecisionOption(
                option_id="postgres",
                description="Postgres with read replicas. Mature; SQL; team has 6 prior systems.",
            ),
            DecisionOption(
                option_id="dynamodb",
                description="DynamoDB serverless. Low ops cost; no JOINs; team has limited experience.",
            ),
            DecisionOption(
                option_id="clickhouse",
                description="ClickHouse OLAP. Strong for analytics queries; ops complexity high.",
            ),
        ],
        agents=["architect", "sre", "data-eng", "security"],
        stakes="high",
        reversibility="partial",
        time_pressure="moderate",
        expertise_asymmetry="moderate",
        regulatory_exposure=False,
        buy_in_required=True,
    )


def build_votes() -> list[AgentVote]:
    return [
        AgentVote(
            agent_name="architect",
            option_id="postgres",
            score=4,
            confidence=0.85,
            comment="Postgres covers JOIN + ACID; team has the most experience.",
        ),
        AgentVote(
            agent_name="sre",
            option_id="postgres",
            score=4,
            confidence=0.8,
            comment="Pgbouncer + read replicas handle our load; ops is predictable.",
        ),
        AgentVote(
            agent_name="data-eng",
            option_id="clickhouse",
            score=3,
            confidence=0.6,
            comment="ClickHouse would be better for the analytics queries specifically.",
        ),
        AgentVote(
            agent_name="security",
            option_id="postgres",
            score=5,
            confidence=0.9,
            comment="Postgres has the strongest auth + row-level security story.",
        ),
    ]


def stub_response() -> str:
    return json.dumps(
        {
            "recommended_model": "fist_to_five",
            "rationale": (
                "High-stakes, partially-reversible decision with required post-decision "
                "buy-in. Majority voting would hide the lukewarm score from data-eng; "
                "consensus is too slow; fist-to-five surfaces the degree of support per "
                "agent and lets a 'fist' (score=0) block while still aggregating quickly."
            ),
            "protocol_steps": [
                "Each agent privately scores their support for each option (0-5 fist-to-five).",
                "Reveal all scores simultaneously to remove conformity pressure.",
                "Any score of 0 blocks the corresponding option, regardless of mean.",
                "Of the un-blocked options, the one with the highest mean >= 3.0 wins.",
                "If no option clears the threshold, fall back to consensus discussion.",
                "Record dissenters (agents at score <=2 on the winner) for follow-up.",
            ],
            "threshold": (
                "Mean fist-to-five >= 3.0 on the winning option, with no agent at "
                "score 0 (block) on that option."
            ),
            "quorum": 4,
            "tie_breaker": (
                "Highest aggregate confidence on the tied options, then re-vote with "
                "discussion if still tied."
            ),
            "fallback_model": "consensus",
        }
    )


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient([stub_response()])


def main() -> None:
    request = build_request()
    votes = build_votes()
    client = pick_client()
    generator = DecisionProtocolGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    protocol = generator.run(request, votes=votes)
    print(protocol.to_markdown())
    print("\n\n--- Orchestrator preamble (for system prompt) ---\n")
    print(protocol.to_orchestrator_preamble())


if __name__ == "__main__":
    main()
