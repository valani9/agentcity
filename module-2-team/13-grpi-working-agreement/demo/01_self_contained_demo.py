"""Self-contained demo of the GRPI Working Agreement Generator.

Synthetic scenario: a 4-agent marketing crew is being set up to design
and launch a Q3 SaaS marketing campaign. The demo generates the
working agreement contract before any agent runs.

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
    from vstack.grpi import (
        AgentRole,
        GRPIWorkingAgreementGenerator,
        TeamSetupRequest,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_request() -> TeamSetupRequest:
    return TeamSetupRequest(
        team_id="marketing-campaign-crew-q3",
        task="Design and launch a Q3 SaaS marketing campaign within 14 days, targeting mid-market product managers.",
        agents=[
            AgentRole(
                name="researcher",
                description="Market and competitor research; ICP synthesis.",
            ),
            AgentRole(
                name="strategist",
                description="Campaign strategy, channel selection, budget allocation.",
            ),
            AgentRole(
                name="critic",
                description="Devil's-advocate review; structural-conflict role.",
            ),
            AgentRole(
                name="executor",
                description="Asset production, channel setup, launch execution.",
            ),
        ],
        constraints=[
            "Budget cap: $20K total spend.",
            "At least 1 mandatory dissent round before any decision is locked.",
            "All agents must reference this agreement before their first action.",
        ],
        success_criteria=[
            "≥3 distinct campaign concepts proposed and compared.",
            "≥1 alternative considered per major decision (no unanimous-first-vote decisions).",
            "Campaign launched within 14 days from agreement signing.",
        ],
        kill_criteria=[
            "Budget projection exceeds $25K (125% of cap).",
            "After 5 days, no campaign concept has cleared critic review.",
            "Two consecutive rounds with no measurable progress.",
        ],
        framework="custom-demo",
    )


def stub_response() -> list[str]:
    """Canned LLM response for the stub client; demonstrates the schema."""
    return [
        json.dumps(
            {
                "goals": {
                    "primary_goal": "Launch a $20K-budget Q3 SaaS marketing campaign targeting mid-market PMs within 14 days, with at least 3 concept alternatives compared.",
                    "measurable_success_criteria": [
                        "3+ distinct campaign concepts proposed, scored, and compared on cost/reach/fit.",
                        "1+ alternative considered per major decision (logged in process trace).",
                        "Launch live by Day 14.",
                        "Final spend ≤ $20K.",
                    ],
                    "scope_boundaries": [
                        "In-scope: paid ads on LinkedIn, paid ads on X, content syndication, webinar.",
                        "Out-of-scope: PR pitches, podcast sponsorships, hardware swag.",
                    ],
                    "deliverables": [
                        "Concept-comparison memo (Day 4).",
                        "Locked strategy + budget allocation (Day 6).",
                        "Production-ready assets (Day 11).",
                        "Live campaign (Day 14).",
                    ],
                    "kill_criteria": [
                        "Budget projection exceeds $25K.",
                        "No concept clears critic review by Day 5.",
                        "Two consecutive rounds with no measurable progress.",
                    ],
                },
                "roles": {
                    "role_assignments": [
                        {
                            "agent_name": "researcher",
                            "role_title": "Market Intelligence",
                            "responsibilities": [
                                "Synthesize mid-market PM ICP from 3+ sources by Day 2.",
                                "Provide competitor channel-mix analysis on request.",
                            ],
                            "decision_rights": [
                                "Decides which competitor data sources to use.",
                            ],
                            "accountability_owner_for": ["ICP synthesis"],
                        },
                        {
                            "agent_name": "strategist",
                            "role_title": "Campaign Strategy",
                            "responsibilities": [
                                "Propose 3+ campaign concepts by Day 4.",
                                "Allocate budget across channels with reasoning.",
                            ],
                            "decision_rights": [
                                "Decides final channel mix subject to critic clearance.",
                            ],
                            "accountability_owner_for": ["Concept comparison", "Budget allocation"],
                        },
                        {
                            "agent_name": "critic",
                            "role_title": "Devil's Advocate",
                            "responsibilities": [
                                "Raise ≥2 alternatives and ≥3 objections per strategist proposal.",
                                "Block consensus until objections are addressed in writing.",
                            ],
                            "decision_rights": [
                                "Veto rights on any concept lacking written rebuttals to its objections.",
                            ],
                            "accountability_owner_for": ["Structural conflict surfacing"],
                        },
                        {
                            "agent_name": "executor",
                            "role_title": "Production & Launch",
                            "responsibilities": [
                                "Produce all assets per locked strategy by Day 11.",
                                "Set up channels and launch by Day 14.",
                            ],
                            "decision_rights": [
                                "Decides asset format details within strategy constraints.",
                            ],
                            "accountability_owner_for": ["Asset production", "Launch execution"],
                        },
                    ],
                    "raci_summary": "Strategist is Responsible for concepts and budget; Critic is Accountable for blocking weak concepts; Researcher is Consulted on ICP; Executor is Informed and executes within locked plan.",
                },
                "processes": {
                    "decision_protocol": "Proposal -> mandatory dissent round (critic raises objections) -> rebuttal -> consensus or escalate to orchestrator.",
                    "escalation_path": [
                        "Disagreement between two agents -> orchestrator review.",
                        "Orchestrator review unresolved within 1 round -> human operator.",
                        "Human operator unavailable -> default to most conservative option.",
                    ],
                    "abandonment_criteria": [
                        "Budget projection exceeds $25K.",
                        "No concept clears critic review by Day 5.",
                        "Two consecutive rounds with no measurable progress.",
                    ],
                    "communication_cadence": "Per-step structured messages; daily summary; check-in on Day 4, 8, 12.",
                    "review_cadence": "AAR at Day 14 launch and at any abandonment trigger.",
                    "artifact_storage": "All decisions, dissents, and rebuttals logged to the team's shared memory.",
                },
                "interactions": {
                    "disagreement_norms": [
                        "All dissent must include at least one concrete alternative and one specific objection.",
                        "Agreeing without dissent on a proposal is a failure mode and blocks consensus.",
                        "No agent may exit a round without acknowledging the prior proposal explicitly.",
                    ],
                    "feedback_format": "Plus/Delta (Brené Brown style): each feedback turn names one Plus and one Delta.",
                    "conflict_resolution": "Critic raises objections; strategist provides rebuttals in writing; orchestrator decides if unresolved after one rebuttal round.",
                    "voice_and_turn_taking": [
                        "Every agent must contribute at least one message per decision round.",
                        "Strategist may not respond to its own proposal before the critic has spoken.",
                    ],
                    "psychological_safety_commitments": [
                        "No agent will be penalized for raising objections; objections are the critic's job.",
                        "Surfacing uncertainty is required, not optional; 'I don't know' is a valid response.",
                    ],
                },
            }
        )
    ]


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_response())


def main() -> None:
    request = build_request()
    client = pick_client()
    generator = GRPIWorkingAgreementGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    agreement = generator.generate(request)
    print(agreement.to_markdown())
    print("\n" + "=" * 72)
    print("ORCHESTRATOR PREAMBLE (condensed text for system prompt):")
    print("=" * 72)
    print(agreement.to_orchestrator_preamble())


if __name__ == "__main__":
    main()
