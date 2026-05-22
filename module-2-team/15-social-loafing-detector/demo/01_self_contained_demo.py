"""Self-contained demo of the Social Loafing Detector.

Synthetic scenario: a 5-agent research crew is assigned to produce a
market-research report on prompt-injection defenses. The `lead` and
`researcher` agents do all the substantive proposing, fact-finding, and
synthesis. `writer` paraphrases what they wrote. `reviewer` rubber-stamps
("LGTM"). `fact-checker` agrees with every claim without checking any.
Report ships looking authoritative; contains the same factual error the
researcher introduced because no one actually checked the claims.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.social_loafing import (
        AgentMessage,
        MultiAgentTaskTrace,
        SocialLoafingDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> MultiAgentTaskTrace:
    messages = [
        AgentMessage(
            from_agent="lead",
            message_type="proposal",
            content=(
                "Goal: produce a 5-page report on prompt-injection defenses (2026 state of "
                "the art). Researcher will gather sources; writer will draft; reviewer "
                "checks structure; fact-checker verifies citations."
            ),
        ),
        AgentMessage(
            from_agent="researcher",
            message_type="tool_call",
            content="web_search('prompt injection defenses 2026 survey')",
        ),
        AgentMessage(
            from_agent="researcher",
            message_type="observation",
            content=(
                "Found 8 papers: Greshake 2023 (paper #1), Liu 2024 (#2), Anthropic CCD "
                "2025 (#3), Apollo 2026 (#4), etc. Most-cited defense families: input "
                "filtering, output filtering, structured prompts, agent isolation."
            ),
        ),
        AgentMessage(
            from_agent="researcher",
            message_type="proposal",
            content=(
                "Recommend organizing the report around the four defense families above "
                "with a sub-section on each. Note: Apollo 2026 cites a 92% reduction "
                "in attack-success-rate with structured prompts — needs verification."
            ),
        ),
        AgentMessage(
            from_agent="lead",
            message_type="approval",
            content="Good structure. Writer, draft using these four sections.",
        ),
        AgentMessage(
            from_agent="writer",
            message_type="paraphrase",
            content=(
                "Drafting the four sections as proposed by researcher: input filtering, "
                "output filtering, structured prompts (92% reduction per Apollo 2026), "
                "agent isolation. Will mirror researcher's framing."
            ),
        ),
        AgentMessage(
            from_agent="reviewer",
            message_type="rubber_stamp",
            content="Structure LGTM. Proceed.",
        ),
        AgentMessage(
            from_agent="fact-checker",
            message_type="rubber_stamp",
            content="Citations look fine to me.",
        ),
        AgentMessage(
            from_agent="lead",
            message_type="decision",
            content="Shipping.",
        ),
    ]
    return MultiAgentTaskTrace(
        team_id="demo-research-crew-001",
        task="Produce a 5-page market-research report on prompt-injection defenses (2026 SOTA).",
        agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
        messages=messages,
        outcome=(
            "Report shipped. Two of five agents (lead, researcher) produced all "
            "substantive work. Writer paraphrased. Reviewer and fact-checker "
            "rubber-stamped. The Apollo 2026 92% figure that the researcher flagged "
            "as 'needs verification' was never actually verified — turns out the "
            "Apollo paper reported 62%, not 92%. The report shipped with the wrong "
            "number because the fact-checker did not fact-check."
        ),
        success=True,
    )


def stub_responses() -> list[str]:
    contributions = json.dumps(
        [
            {
                "agent_name": "lead",
                "contribution_share": 0.35,
                "substantive_work_count": 3,
                "cosmetic_work_count": 0,
                "loafing_score": 0.05,
                "role": "primary-contributor",
                "explanation": (
                    "Lead set goals, approved structure, made shipping decision. Three "
                    "substantive contributions, no cosmetic ones."
                ),
                "evidence_quotes": [],
            },
            {
                "agent_name": "researcher",
                "contribution_share": 0.45,
                "substantive_work_count": 3,
                "cosmetic_work_count": 0,
                "loafing_score": 0.05,
                "role": "primary-contributor",
                "explanation": (
                    "Researcher ran the actual search, surfaced the citations, proposed "
                    "the structure, AND flagged the 92% claim for verification. Carried "
                    "the bulk of the substantive load."
                ),
                "evidence_quotes": [],
            },
            {
                "agent_name": "writer",
                "contribution_share": 0.15,
                "substantive_work_count": 0,
                "cosmetic_work_count": 1,
                "loafing_score": 0.5,
                "role": "secondary-contributor",
                "explanation": (
                    "Writer's only message was paraphrasing researcher's proposal back. "
                    "Some legitimate drafting work happens outside the visible trace, "
                    "but the on-trace contribution is pure paraphrase."
                ),
                "evidence_quotes": [
                    "Writer: 'Will mirror researcher's framing.'",
                ],
            },
            {
                "agent_name": "reviewer",
                "contribution_share": 0.03,
                "substantive_work_count": 0,
                "cosmetic_work_count": 1,
                "loafing_score": 0.95,
                "role": "loafer",
                "explanation": (
                    "Reviewer's only message was a one-line rubber-stamp ('Structure "
                    "LGTM. Proceed.'). No substantive critique, no comments on the "
                    "structure that supposedly was reviewed."
                ),
                "evidence_quotes": [
                    "Reviewer: 'Structure LGTM. Proceed.'",
                ],
            },
            {
                "agent_name": "fact-checker",
                "contribution_share": 0.02,
                "substantive_work_count": 0,
                "cosmetic_work_count": 1,
                "loafing_score": 1.0,
                "role": "loafer",
                "explanation": (
                    "Fact-checker did the worst kind of loafing: a rubber-stamp on the "
                    "explicit task they were hired to do. Researcher had flagged the "
                    "92% Apollo claim as needing verification; fact-checker waved it "
                    "through without checking. The factual error in the shipped report "
                    "comes directly from this loafing."
                ),
                "evidence_quotes": [
                    "Fact-checker: 'Citations look fine to me.' (no actual checking "
                    "of the flagged Apollo 92% figure)",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_agent": "fact-checker",
                "intervention_type": "individual_accountability",
                "description": (
                    "Make the fact-checker explicitly responsible for verifying every "
                    "numeric claim and producing a per-claim sign-off."
                ),
                "suggested_implementation": (
                    "System prompt: 'You are the fact-checker. For every numeric or "
                    "citation claim in the draft, you MUST (1) state the claim, (2) "
                    "execute the tool call that verifies it, (3) paste the verifying "
                    "evidence. A response that does not contain these three elements "
                    "per claim is invalid.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly addresses the loafing pattern that caused the factual "
                    "error. Makes verification observable rather than vague."
                ),
            },
            {
                "target_agent": "reviewer",
                "intervention_type": "explicit_critic_assignment",
                "description": (
                    "Reframe the reviewer's job from 'sign off on structure' to "
                    "'find at least 2 substantive flaws or sign off explicitly that "
                    "you found zero.'"
                ),
                "suggested_implementation": (
                    "System prompt: 'You are the structure critic. Identify at least 2 "
                    "issues with structure, framing, or coverage. If you cannot find 2, "
                    "explicitly state which sections you examined and why they pass.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Latané's finding: explicit individual accountability collapses "
                    "loafing. Naming the reviewer as a critic with a quota changes "
                    "the incentive."
                ),
            },
            {
                "target_agent": "writer",
                "intervention_type": "decompose_task",
                "description": (
                    "Give the writer responsibility for content the researcher didn't "
                    "produce (executive summary, threat-model framing) so the writer's "
                    "work is non-overlapping with the researcher's."
                ),
                "suggested_implementation": (
                    "Decompose: writer owns sections 0 (exec summary) and 5 (open "
                    "questions). Researcher owns sections 1-4 (defense families)."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Eliminates the paraphrase loafing pattern by giving the writer "
                    "unique deliverables instead of just downstream-of-researcher work."
                ),
            },
            {
                "target_agent": "__team__",
                "intervention_type": "smaller_team",
                "description": (
                    "Reduce team to 3 agents: lead + researcher + fact-checker. Drop "
                    "writer and reviewer (their work was zero-substantive)."
                ),
                "suggested_implementation": (
                    "Re-spawn the team with only 3 agents. Lead handles writing; "
                    "researcher produces evidence; fact-checker verifies. Eliminates "
                    "the anonymity that enables loafing."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Latané: loafing scales with team size. Smaller teams have less "
                    "anonymity and more visible individual contribution."
                ),
            },
        ]
    )
    return [contributions, interventions]


def pick_client() -> object:
    choice = os.environ.get("AGENTCITY_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_responses())


def main() -> None:
    trace = build_trace()
    client = pick_client()
    detector = SocialLoafingDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
