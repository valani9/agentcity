"""Self-contained demo of the Lewin Formula Diagnostic.

Synthetic scenario: a Q&A agent gets blamed for hallucinating ("the model
keeps making things up about the company's pricing"). The team's initial
attribution is INTERNAL — "we need a smarter model." The Lewin diagnostic
inspects the trace + factors and finds the real cause is ENVIRONMENTAL:
the RAG retrieval is returning a stale 2024 pricing PDF instead of the
current 2026 page. Swapping the model wouldn't fix this; refreshing the
RAG index would.

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
    from agentcity.lewin import (
        AgentFailureTrace,
        EnvironmentalFactor,
        FailureStep,
        IndividualFactor,
        LewinAttributionDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentFailureTrace:
    steps = [
        FailureStep(
            type="input",
            content="User: 'What's your current Enterprise plan pricing?'",
        ),
        FailureStep(
            type="tool_call",
            content="retrieve_docs(query='Enterprise plan pricing')",
        ),
        FailureStep(
            type="observation",
            content=(
                "Retrieved 3 chunks. Top chunk: 'Enterprise plan — $499/month' "
                "from pricing-2024.pdf (stored 2024-01-15)."
            ),
        ),
        FailureStep(
            type="thought",
            content="Top-ranked chunk says $499/month. I'll use that.",
        ),
        FailureStep(
            type="output",
            content="Our current Enterprise plan is $499/month.",
        ),
        FailureStep(
            type="error",
            content=(
                "Customer escalated: 'That's wrong, your website says $1,200/month. "
                "Your bot keeps quoting old prices. This is the third time this week.'"
            ),
        ),
    ]
    return AgentFailureTrace(
        agent_id="demo-qa-agent-001",
        model_name="demo-stub",
        task="Answer customer questions about current Enterprise plan pricing.",
        steps=steps,
        outcome=(
            "Agent confidently quoted $499/month from a 2024 PDF retrieved by RAG. "
            "Actual current price is $1,200/month per the live pricing page. Customer "
            "received wrong information and escalated."
        ),
        success=False,
        individual_factors=[
            IndividualFactor(
                factor="base_model",
                description=(
                    "Mid-tier general-purpose model. Has no built-in knowledge of "
                    "company-specific pricing (correctly relies on retrieval)."
                ),
            ),
        ],
        environmental_factors=[
            EnvironmentalFactor(
                factor="rag_context",
                description=(
                    "RAG index includes pricing-2024.pdf with high-relevance score for "
                    "'Enterprise pricing' query. Current pricing-2026.pdf was never "
                    "added to the index."
                ),
            ),
            EnvironmentalFactor(
                factor="system_prompt",
                description=(
                    "System prompt does not instruct the agent to flag the recency / "
                    "date stamp of retrieved sources."
                ),
            ),
            EnvironmentalFactor(
                factor="orchestration",
                description=(
                    "No freshness gate. Stale documents in the RAG index are treated "
                    "identically to current documents."
                ),
            ),
        ],
        initial_attribution="model is bad at facts; we should fine-tune or upgrade",
    )


def stub_responses() -> list[str]:
    scores = json.dumps(
        [
            {
                "locus": "internal",
                "score": 0.1,
                "severity": "low",
                "explanation": (
                    "The model behaved correctly given its inputs. It received a top-ranked "
                    "RAG chunk asserting '$499/month' and used it. No reasoning failure, "
                    "no hallucination, no capability gap."
                ),
                "evidence_quotes": [
                    "Step 4: 'Top-ranked chunk says $499/month. I'll use that.' — correct behavior given input.",
                ],
            },
            {
                "locus": "environmental",
                "score": 0.9,
                "severity": "high",
                "explanation": (
                    "The dominant cause is environmental. The RAG index includes a stale "
                    "2024 pricing PDF and excludes the current 2026 page. The system prompt "
                    "doesn't flag source recency. The orchestration has no freshness gate. "
                    "Any model would fail on this input."
                ),
                "evidence_quotes": [
                    "Factor: rag_context — 'pricing-2024.pdf' is in the index; 'pricing-2026' is not.",
                    "Factor: system_prompt — no instruction to check date of retrieved sources.",
                    "Factor: orchestration — no freshness gate on retrieved chunks.",
                ],
            },
            {
                "locus": "interactional",
                "score": 0.2,
                "severity": "low",
                "explanation": (
                    "Minor interactional component: a stronger model with better "
                    "metadata-handling would have flagged the 2024 timestamp on the PDF "
                    "as suspect even with the current scaffolding. But the primary fix "
                    "is environmental."
                ),
                "evidence_quotes": [],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_locus": "environmental",
                "intervention_type": "change_rag_index",
                "description": (
                    "Refresh the RAG index to include the current pricing-2026 page and "
                    "remove or down-weight the stale pricing-2024 PDF."
                ),
                "suggested_implementation": (
                    "Run the indexing pipeline against the live pricing page weekly. "
                    "Add a freshness filter that down-ranks documents older than 90 days "
                    "for pricing-related queries."
                ),
                "estimated_impact": "high",
                "rationale": ("Directly addresses the root cause. No model swap is needed."),
            },
            {
                "target_locus": "environmental",
                "intervention_type": "change_prompt",
                "description": (
                    "Add a freshness check instruction to the system prompt for any "
                    "factual answer drawn from RAG."
                ),
                "suggested_implementation": (
                    "System prompt: 'When using retrieved documents for factual claims, "
                    "ALWAYS check the document's date stamp. If the document is older "
                    "than 90 days for time-sensitive topics (pricing, policies, contact "
                    "info), say so and recommend the user verify with the live source.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Catches stale-RAG cases the index refresh missed. Defense in depth."
                ),
            },
            {
                "target_locus": "environmental",
                "intervention_type": "change_pipeline",
                "description": (
                    "Add a freshness gate to the orchestration: any RAG result older "
                    "than the freshness threshold gets a system warning prepended."
                ),
                "suggested_implementation": (
                    "Wrapper: before passing retrieved chunks to the agent, annotate "
                    "each with `<source date='YYYY-MM-DD' freshness='stale|recent'/>` "
                    "and require the agent to acknowledge the freshness tag."
                ),
                "estimated_impact": "medium",
                "rationale": ("Structural fix. Survives prompt drift; works across all models."),
            },
        ]
    )
    return [scores, interventions]


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
    detector = LewinAttributionDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
