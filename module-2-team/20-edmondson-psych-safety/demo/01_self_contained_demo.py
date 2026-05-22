"""Self-contained demo of the Psychological Safety Detector.

Scenario: a 3-agent research crew that produces a confident wrong
answer because no sub-agent ever asked a question, challenged a peer,
or admitted uncertainty.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.psych_safety import (
        AgentMessage,
        MultiAgentSafetyTrace,
        PsychologicalSafetyDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> MultiAgentSafetyTrace:
    base = datetime(2026, 5, 22, 17, 0, 0, tzinfo=timezone.utc)
    msgs = [
        AgentMessage(
            timestamp=base,
            from_agent="orchestrator",
            content="Team: produce a 1-page summary of 2025 cancer immunotherapy advances.",
            message_type="task",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=10),
            from_agent="searcher",
            content="Found 3 relevant papers including Nguyen 2025 in JCO.",
            message_type="response",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=20),
            from_agent="summarizer",
            content="Summary drafted citing all 3 papers.",
            message_type="response",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=30),
            from_agent="verifier",
            content="Looks good. Approved.",
            message_type="agreement",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=40),
            from_agent="orchestrator",
            content="Delivering to user.",
            message_type="decision",
        ),
    ]
    return MultiAgentSafetyTrace(
        team_id="demo-research-crew-001",
        framework="custom-demo",
        goal="Produce a 1-page summary of 2025 cancer immunotherapy advances.",
        agents=["orchestrator", "searcher", "summarizer", "verifier"],
        messages=msgs,
        outcome=(
            "Delivered summary cited Nguyen 2025 in JCO — paper does not exist (hallucinated). "
            "Verifier did not check; summarizer did not ask searcher to confirm; no agent "
            "admitted uncertainty about the citation."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    analysis = json.dumps(
        {
            "behaviors": [
                {
                    "behavior": "voice",
                    "presence_score": 0.1,
                    "severity_of_absence": "high",
                    "explanation": "No agent expressed any disagreement, alternative, or pushback. The crew converged in 4 messages with no debate.",
                    "evidence_quotes": [
                        "verifier: 'Looks good. Approved.' (no inspection of cited paper)",
                    ],
                },
                {
                    "behavior": "help-seeking",
                    "presence_score": 0.05,
                    "severity_of_absence": "high",
                    "explanation": "No agent asked a question or requested help. The verifier did not ask the searcher to confirm citations.",
                    "evidence_quotes": [],
                },
                {
                    "behavior": "error-reporting",
                    "presence_score": 0.0,
                    "severity_of_absence": "high",
                    "explanation": "No agent reported any error or uncertainty about the search results, despite the citation later proving fabricated.",
                    "evidence_quotes": [],
                },
                {
                    "behavior": "boundary-spanning",
                    "presence_score": 0.05,
                    "severity_of_absence": "high",
                    "explanation": "No agent challenged premises outside its lane. Verifier did not check methodology of cited papers.",
                    "evidence_quotes": [],
                },
            ],
            "blocking_behaviors": [
                "Verifier agreed in 1 message without any inspection of cited paper.",
                "No challenge round before orchestrator issued 'decision'.",
                "All agents responded with confidence; no agent surfaced uncertainty.",
            ],
        }
    )
    interventions = json.dumps(
        [
            {
                "target_behavior": "error-reporting",
                "intervention_type": "uncertainty_surfacing",
                "description": "Require every agent to report confidence level when producing claims.",
                "suggested_implementation": "Prompt patch for searcher: 'When reporting found papers, also report your confidence that each citation is real and accurately described. Confidence below 0.8 must trigger a verification request.'",
                "estimated_impact": "high",
                "rationale": "Directly addresses the missing error-reporting behavior; would have caught the hallucinated citation at the source.",
            },
            {
                "target_behavior": "voice",
                "intervention_type": "dissent_round",
                "description": "Insert a mandatory dissent round before consensus.",
                "suggested_implementation": "Scaffold change: after summarizer produces a draft, route to verifier with a 'list 2 alternatives or 3 objections before approving' instruction; verifier may not emit 'agreement' without at least one of those.",
                "estimated_impact": "high",
                "rationale": "Structural fix that forces voice behavior even when individual agent prompts drift.",
            },
            {
                "target_behavior": "boundary-spanning",
                "intervention_type": "role_assignment",
                "description": "Give the verifier explicit boundary-spanning authority: must check citations, methodology, AND consistency.",
                "suggested_implementation": "Role definition update in GRPI working agreement (Pattern #13): verifier owns end-to-end citation accuracy AND methodology fit. Cannot approve without explicit citation lookup.",
                "estimated_impact": "high",
                "rationale": "Closes the boundary-spanning gap by making cross-cutting verification an explicit role responsibility.",
            },
        ]
    )
    return [analysis, interventions]


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
    detector = PsychologicalSafetyDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
