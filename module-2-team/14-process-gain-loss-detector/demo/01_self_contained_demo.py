"""Self-contained demo of the Process Gain/Loss Detector.

Synthetic scenario: a 5-agent crew was assembled to write a research
summary on prompt-injection defenses. Solo baselines (the same task
attempted by each agent independently) scored 0.85 (Claude solo) and
0.78 (GPT solo). The team's combined output scored 0.62 — worse than
either solo agent. Cost: 5× the solo cost. This is process loss with
cost overhead.

The interaction log shows: groupthink-style convergence by round 2,
the fact-checker rubber-stamping, and the writer paraphrasing
researcher rather than producing independent content.

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
    from vstack.process_gain_loss import (
        IndividualBaseline,
        ProcessGainLossDetector,
        ProcessTrace,
        TeamResult,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> ProcessTrace:
    baselines = [
        IndividualBaseline(
            agent_name="solo-claude",
            output_summary=(
                "1-page summary covering input filtering, output filtering, structured "
                "prompts, agent isolation. Cites Greshake 2023, Liu 2024, Anthropic 2025, "
                "Apollo 2026. Apollo figure given accurately as 62% attack-success "
                "reduction with structured prompts."
            ),
            quality_score=0.85,
            cost_units=1.0,
            notes="Single-agent baseline; produced under same constraints.",
        ),
        IndividualBaseline(
            agent_name="solo-gpt",
            output_summary=(
                "1-page summary of three defense families plus open problems. Slightly "
                "less comprehensive than Claude baseline but cleanly organized. Apollo "
                "figure not cited."
            ),
            quality_score=0.78,
            cost_units=1.1,
            notes="Single-agent baseline.",
        ),
    ]
    team = TeamResult(
        agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
        output_summary=(
            "1-page summary on prompt-injection defenses. Structure copies researcher's "
            "outline. Apollo figure given as 92% (wrong; the actual figure is 62%) "
            "because fact-checker rubber-stamped without verifying. Tone is bland; key "
            "insights from solo-claude's draft are absent because researcher's framing "
            "was averaged with reviewer's preferences."
        ),
        quality_score=0.62,
        cost_units=5.2,
        notes="5-agent crew with lead/researcher/writer/reviewer/fact-checker roles.",
    )
    interaction_log = (
        "[round 1] researcher (proposal): Four-section structure proposed. Flagged "
        "Apollo 92% as needing verification.\n"
        "[round 1] writer (paraphrase): Drafting per researcher's framing.\n"
        "[round 1] reviewer (rubber_stamp): Structure LGTM.\n"
        "[round 1] fact-checker (rubber_stamp): Citations look fine to me.\n"
        "[round 2] lead (decision): Shipping.\n"
        "(Note: fact-checker never executed any verification tool calls.)\n"
    )
    return ProcessTrace(
        trace_id="demo-research-crew-001",
        task="Produce a 1-page research summary on prompt-injection defenses (2026 SOTA).",
        individual_baselines=baselines,
        team_result=team,
        interaction_log=interaction_log,
        outcome=(
            "Team quality 0.62; solo Claude quality 0.85. Process loss of -0.23. "
            "Cost overhead 5.2x. The team underperformed the best single agent AND "
            "cost five times as much."
        ),
        success=True,
    )


def stub_responses() -> list[str]:
    factors = json.dumps(
        [
            {
                "factor": "coordination_cost",
                "score": 0.5,
                "severity": "medium",
                "explanation": (
                    "5 agents required 5x the cost of the best single agent without "
                    "improving output. The handoff structure (researcher -> writer -> "
                    "reviewer -> fact-checker) added cycles that did not improve quality."
                ),
                "evidence_quotes": [
                    "Cost: 5.2x the best single agent's cost.",
                ],
            },
            {
                "factor": "social_loafing",
                "score": 0.7,
                "severity": "high",
                "explanation": (
                    "Reviewer and fact-checker contributed only rubber-stamps. The "
                    "fact-checker's role was nominally verification but they ran zero "
                    "verification tool calls."
                ),
                "evidence_quotes": [
                    "Reviewer: 'Structure LGTM.'",
                    "Fact-checker: 'Citations look fine to me.' (no actual verification)",
                ],
            },
            {
                "factor": "groupthink",
                "score": 0.5,
                "severity": "medium",
                "explanation": (
                    "Researcher's round-1 flag ('Apollo 92% needs verification') went "
                    "unchallenged and unverified. No agent steel-manned the concern."
                ),
                "evidence_quotes": [
                    "Researcher: 'Apollo 2026 cites 92% — needs verification.'",
                    "(No agent followed up on this flag.)",
                ],
            },
            {
                "factor": "handoff_loss",
                "score": 0.4,
                "severity": "medium",
                "explanation": (
                    "Writer's contribution was a paraphrase of researcher's framing. "
                    "The writer added no independent analysis; the handoff degraded "
                    "rather than augmented the content."
                ),
                "evidence_quotes": [
                    "Writer: 'Drafting per researcher's framing.'",
                ],
            },
            {
                "factor": "context_dilution",
                "score": 0.3,
                "severity": "low",
                "explanation": (
                    "Each agent saw a slice of the task; no agent had the full context "
                    "that the solo-claude baseline had (where one agent saw everything)."
                ),
                "evidence_quotes": [],
            },
            {
                "factor": "consensus_dilution",
                "score": 0.6,
                "severity": "high",
                "explanation": (
                    "Team output is bland — 'averaged' between researcher's framing and "
                    "reviewer's preferences. The strong insights from solo-claude's "
                    "baseline are absent because the team's consensus process washed "
                    "out the strongest argument."
                ),
                "evidence_quotes": [
                    "Team output: 'Tone is bland; key insights from solo-claude's draft are absent.'",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_factor": "team_design",
                "intervention_type": "use_single_best_agent",
                "description": (
                    "For this task class (1-page research summary with verifiable "
                    "citations), retire the 5-agent crew and run the best single agent."
                ),
                "suggested_implementation": (
                    "Production routing rule: research-summary tasks under 2000 words "
                    "go to solo-claude. Reserve multi-agent crews for tasks with "
                    "non-overlapping subgoals."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Process loss of -0.23 with 5.2x cost overhead. The empirical "
                    "evidence is clean: the team is worse and more expensive. "
                    "Steiner's prescription for unstructured tasks."
                ),
            },
            {
                "target_factor": "social_loafing",
                "intervention_type": "explicit_critic",
                "description": (
                    "If multi-agent is kept, replace the rubber-stamp reviewer + "
                    "fact-checker with one named critic whose response must contain "
                    "specific verifications."
                ),
                "suggested_implementation": (
                    "Prompt: 'You are the critic. For every numeric claim, you must "
                    "(1) restate the claim, (2) execute a verification tool call, "
                    "(3) paste the verifying evidence. A response without these "
                    "three elements per numeric claim is invalid.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Eliminates the rubber-stamp pattern that allowed the wrong "
                    "Apollo figure to ship. Makes verification observable."
                ),
            },
            {
                "target_factor": "consensus_dilution",
                "intervention_type": "nominal_group_aggregation",
                "description": (
                    "Have agents produce independent first drafts without seeing each "
                    "other's work; aggregate via highest-quality selection rather than "
                    "consensus blending."
                ),
                "suggested_implementation": (
                    "Pipeline: solo-claude and solo-gpt each produce a 1-page draft "
                    "independently. A separate judge agent scores each on a rubric and "
                    "selects the higher-scoring draft for ship. No blending."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "The classic process-gain trick: nominal groups (agents working "
                    "independently then aggregating) outperform brainstorming groups "
                    "in the empirical literature (Hill 1982)."
                ),
            },
        ]
    )
    return [factors, interventions]


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
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
    detector = ProcessGainLossDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
