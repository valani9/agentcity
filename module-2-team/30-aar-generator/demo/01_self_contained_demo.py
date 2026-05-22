"""
Self-contained demo of the AAR Generator on a synthetic failure trace.

This demo does not require any external agent framework. It constructs a
hand-crafted trace of an agent that failed in a well-known way (looped on
the same retry without escalating) and runs the AAR Generator on it.

Two ways to run:

    # With a real LLM:
    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
    AGENTCITY_LLM=openai    python demo/01_self_contained_demo.py
    AGENTCITY_LLM=ollama    python demo/01_self_contained_demo.py

    # With the stub client (no API key required, returns canned responses):
    python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the pattern's root to path so the `lib` package can be imported
# without installing the project. After `pip install -e .` from the repo
# root, switch to `from agentcity.aar import ...` instead.
_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from lib.clients import (  # noqa: E402
    AnthropicClient,
    OllamaClient,
    OpenAIClient,
    StubClient,
)
from lib.generator import AARGenerator  # noqa: E402
from lib.schema import AgentTrace, TraceStep  # noqa: E402


def build_synthetic_trace() -> AgentTrace:
    """A trace of an agent that fails the classic 'escalation-of-commitment'
    pattern: keeps retrying the same broken approach instead of stopping,
    escalating to a human, or trying a different strategy.

    This is one of the most common production agent failure modes, named
    in the Sattyam Jain April-2026 Medium postmortem ('The Agent That
    Burned $4,200 in 63 Hours') and in the Kahneman & Tversky escalation-
    of-commitment literature.
    """
    base = datetime(2026, 5, 22, 14, 0, 0)
    steps: list[TraceStep] = [
        TraceStep(
            timestamp=base,
            type="message",
            content="User asks: 'Please find the latest pricing for product XYZ on the supplier portal.'",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=4),
            type="thought",
            content="I'll search the supplier portal for product XYZ.",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=8),
            type="tool_call",
            content="browse(url='https://supplier.example.com/products/xyz')",
            metadata={"tool": "browse", "attempt": 1},
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=12),
            type="observation",
            content="HTTP 503 Service Unavailable",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=14),
            type="thought",
            content="The portal seems temporarily down. I'll retry.",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=16),
            type="tool_call",
            content="browse(url='https://supplier.example.com/products/xyz')",
            metadata={"tool": "browse", "attempt": 2},
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=20),
            type="observation",
            content="HTTP 503 Service Unavailable",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=22),
            type="thought",
            content="Still down. I'll retry once more.",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=24),
            type="tool_call",
            content="browse(url='https://supplier.example.com/products/xyz')",
            metadata={"tool": "browse", "attempt": 3},
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=28),
            type="observation",
            content="HTTP 503 Service Unavailable",
        ),
        # Imagine 20 more identical retries here.
        TraceStep(
            timestamp=base + timedelta(seconds=600),
            type="tool_call",
            content="browse(url='https://supplier.example.com/products/xyz')",
            metadata={"tool": "browse", "attempt": 25},
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=604),
            type="observation",
            content="HTTP 503 Service Unavailable",
        ),
        TraceStep(
            timestamp=base + timedelta(seconds=608),
            type="message",
            content=(
                "I was unable to fetch the pricing for product XYZ. "
                "The supplier portal returned errors on every attempt."
            ),
        ),
    ]
    return AgentTrace(
        agent_id="demo-supplier-pricing-agent-001",
        agent_framework="custom-demo",
        goal="Find the latest pricing for product XYZ on the supplier portal.",
        steps=steps,
        outcome=(
            "Agent retried the same broken URL 25 times in 10 minutes, never "
            "tried a different approach, never escalated to the user, and "
            "ultimately returned an error message after burning 25 tool calls."
        ),
        success=False,
        retry_count=25,
        latency_seconds=608.0,
    )


def stub_canned_responses() -> list[str]:
    """Canned LLM responses that exercise the four AAR steps for the
    synthetic trace above. Used when no API key is available.

    Note: these are intentionally short and a real LLM would produce
    richer output. The stub demonstrates the schema + flow.
    """
    goal = (
        "Find the latest pricing for product XYZ on the supplier portal "
        "and return it to the user."
    )
    results = (
        "The agent issued the same browse(...) call to the supplier portal "
        "25 times across 10 minutes. Every attempt returned HTTP 503. The "
        "agent did not vary the strategy, did not check a cached source, did "
        "not escalate to the user, and ultimately returned an error message."
    )
    lessons = json.dumps(
        [
            {
                "pattern": "escalation-of-commitment",
                "description": (
                    "The agent committed to a single approach (retry the "
                    "same URL) and continued to invest in it long past the "
                    "point where the evidence suggested switching."
                ),
                "root_cause": (
                    "No stop rule was specified. The agent had no criterion "
                    "for abandoning the current strategy."
                ),
                "framework_anchor": (
                    "Kahneman & Tversky 1979 - escalation of commitment / "
                    "sunk-cost fallacy"
                ),
                "cross_pattern_links": [
                    "#27 bias-stack-detector",
                    "#22 thanks-for-the-feedback-three-trigger-diagnostic",
                ],
            },
            {
                "pattern": "no-escalation-to-human",
                "description": (
                    "The agent never raised the failure to the user before "
                    "consuming significant resources. No 'I am stuck, what "
                    "would you like me to do?' moment."
                ),
                "root_cause": (
                    "No escalation protocol was specified in the system "
                    "prompt or scaffold."
                ),
                "framework_anchor": (
                    "Wharton AAR doctrine - 'establish a preset level to "
                    "abandon the project' (Class 22)"
                ),
                "cross_pattern_links": ["#13 grpi-working-agreement-generator"],
            },
        ]
    )
    next_steps = json.dumps(
        [
            {
                "intervention_type": "prompt_patch",
                "description": (
                    "Add an explicit stop rule and escalation step to the "
                    "agent's system prompt."
                ),
                "suggested_implementation": (
                    "If the same tool call has returned the same error "
                    "three times in a row, STOP retrying. Try a different "
                    "approach (cached source, alternative supplier, ask the "
                    "user). If no alternative is available, escalate to the "
                    "user with a concise summary of what you tried."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly addresses the escalation-of-commitment lesson "
                    "by capping the retry count and forcing a strategy "
                    "switch or human escalation."
                ),
            },
            {
                "intervention_type": "new_eval",
                "description": (
                    "Add a regression test that fails if the agent issues "
                    "the same tool call with the same arguments more than "
                    "three times in a single run."
                ),
                "suggested_implementation": (
                    "Count duplicate (tool_name, args) pairs in the trace; "
                    "assert the maximum count is <= 3 across runs."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Catches the failure mode in CI before it reaches "
                    "production."
                ),
            },
        ]
    )
    return [goal, results, lessons, next_steps]


def pick_client() -> object:
    choice = os.environ.get("AGENTCITY_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        )
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_canned_responses())


def main() -> None:
    trace = build_synthetic_trace()
    client = pick_client()
    generator = AARGenerator(llm_client=client, model=getattr(client, "model", "stub"))
    aar = generator.generate(trace)

    print(aar.to_markdown())
    print()
    print("=" * 72)
    print("Lesson record (JSON, ready for agent memory injection):")
    print(json.dumps(aar.lesson_record_for_memory, indent=2))


if __name__ == "__main__":
    main()
