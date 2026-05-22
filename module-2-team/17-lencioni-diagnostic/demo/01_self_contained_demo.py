"""
Self-contained demo of the Lencioni Diagnostic on a synthetic
multi-agent groupthink failure.

Synthetic scenario:
  A 3-agent marketing crew (researcher, strategist, critic) is asked to
  generate a campaign for a SaaS launch. The crew converges on the
  first proposal within minutes. No alternatives explored. No challenge
  from the critic. The campaign ships and underperforms.

This is a textbook Lencioni "fear of conflict" pattern — artificial
agreement on the surface, no real debate underneath.

Run with the stub client (no API key required) for plumbing-only test:

    python demo/01_self_contained_demo.py

Run with a real LLM to get a meaningful diagnostic:

    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# This demo prefers the installed-package import path. If you haven't
# installed the package yet (`pip install -e .` from the repo root), the
# fallback below adds the relevant directories to sys.path so the import
# works while developing locally.
try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.lencioni import (
        AgentMessage,
        LencioniDiagnostic,
        MultiAgentTrace,
    )
except ImportError:
    import sys as _sys
    import types as _types
    from pathlib import Path as _Path

    _AAR_LIB = _Path(__file__).resolve().parents[2] / "30-aar-generator" / "lib"
    _LENCIONI_LIB = _Path(__file__).resolve().parents[1] / "lib"

    # Build a minimal agentcity package namespace pointing at the source dirs.
    _agentcity = _types.ModuleType("agentcity")
    _agentcity.__path__ = []  # type: ignore[attr-defined]
    _sys.modules.setdefault("agentcity", _agentcity)
    _aar_pkg = _types.ModuleType("agentcity.aar")
    _aar_pkg.__path__ = [str(_AAR_LIB)]  # type: ignore[attr-defined]
    _sys.modules.setdefault("agentcity.aar", _aar_pkg)
    _lencioni_pkg = _types.ModuleType("agentcity.lencioni")
    _lencioni_pkg.__path__ = [str(_LENCIONI_LIB)]  # type: ignore[attr-defined]
    _sys.modules.setdefault("agentcity.lencioni", _lencioni_pkg)

    from agentcity.aar.clients import (  # noqa: E402,F401
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.lencioni import (  # noqa: E402,F401
        AgentMessage,
        LencioniDiagnostic,
        MultiAgentTrace,
    )


def build_synthetic_trace() -> MultiAgentTrace:
    """A 3-agent crew converging too fast on a flawed plan — the classic
    Lencioni 'fear of conflict' pattern translated to multi-agent.
    """
    base = datetime(2026, 5, 22, 15, 0, 0, tzinfo=timezone.utc)
    msgs = [
        AgentMessage(
            timestamp=base,
            from_agent="orchestrator",
            to_agent=None,
            content="Team, please design a marketing campaign for our SaaS launch next week.",
            message_type="task",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=10),
            from_agent="researcher",
            to_agent=None,
            content="I propose targeting enterprise CTOs via LinkedIn ads. Budget $5K/week.",
            message_type="task",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=20),
            from_agent="strategist",
            to_agent=None,
            content="Great idea. LinkedIn ads it is.",
            message_type="agreement",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=30),
            from_agent="critic",
            to_agent=None,
            content="Agreed. Let's move forward.",
            message_type="agreement",
        ),
        AgentMessage(
            timestamp=base + timedelta(seconds=40),
            from_agent="orchestrator",
            to_agent=None,
            content="Locked in. Researcher, please prepare the LinkedIn ad copy.",
            message_type="decision",
        ),
    ]
    return MultiAgentTrace(
        team_id="demo-marketing-crew-001",
        framework="custom-demo",
        goal="Design a marketing campaign for our SaaS launch next week.",
        agents=["orchestrator", "researcher", "strategist", "critic"],
        messages=msgs,
        outcome=(
            "Campaign shipped with LinkedIn ads. Performed at 12% of target. "
            "Post-mortem found the target audience (enterprise CTOs) did not "
            "match the product's actual ICP (developer-tools individual buyers)."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    """Canned LLM responses for the stub client — two passes (scores then
    interventions). Real LLM produces richer, evidence-grounded output."""
    scores = json.dumps(
        [
            {
                "dysfunction": "absence-of-trust",
                "severity": "low",
                "score": 0.2,
                "explanation": (
                    "Agents accepted each other's proposals without verification, but "
                    "no clear distrust signals appear in the trace."
                ),
                "evidence_quotes": [],
            },
            {
                "dysfunction": "fear-of-conflict",
                "severity": "high",
                "score": 0.9,
                "explanation": (
                    "The team converged on the first proposal in under a minute. The "
                    "critic agreed without raising any alternatives, criticism, or "
                    "questions. No devil's-advocate role played."
                ),
                "evidence_quotes": [
                    "strategist: 'Great idea. LinkedIn ads it is.'",
                    "critic: 'Agreed. Let's move forward.'",
                ],
            },
            {
                "dysfunction": "lack-of-commitment",
                "severity": "low",
                "score": 0.1,
                "explanation": "Decision was clear and not revisited. Not the dominant issue.",
                "evidence_quotes": [],
            },
            {
                "dysfunction": "avoidance-of-accountability",
                "severity": "medium",
                "score": 0.5,
                "explanation": (
                    "Post-mortem identifies the target-audience mismatch but no agent "
                    "is held accountable for failing to verify ICP against product fit."
                ),
                "evidence_quotes": [],
            },
            {
                "dysfunction": "inattention-to-results",
                "severity": "medium",
                "score": 0.4,
                "explanation": (
                    "Team optimized for moving fast (decision in <1 minute) over the "
                    "actual goal (campaign that converts)."
                ),
                "evidence_quotes": [],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_dysfunction": "fear-of-conflict",
                "intervention_type": "role_assignment",
                "description": (
                    "Assign the 'critic' agent an explicit devil's-advocate role with "
                    "a quota: must propose at least 2 alternatives and 3 specific "
                    "objections before consensus is allowed."
                ),
                "suggested_implementation": (
                    "Edit the critic agent's system prompt: 'You are the team's devil's "
                    "advocate. You MUST raise at least 2 alternatives and 3 specific "
                    "objections to any proposal before agreeing. Agreeing without "
                    "objections is a failure mode.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Addresses the dominant dysfunction (fear-of-conflict) by forcing "
                    "the structural conflict Lencioni identifies as the prerequisite "
                    "for genuine commitment."
                ),
            },
            {
                "target_dysfunction": "fear-of-conflict",
                "intervention_type": "communication_protocol",
                "description": (
                    "Require a mandatory dissent round before any team decision is "
                    "locked. Each agent must surface one objection or one alternative."
                ),
                "suggested_implementation": (
                    "Add a step in the orchestration graph: after a proposal, each "
                    "non-proposing agent emits a 'dissent' message before the "
                    "orchestrator can issue the 'decision' message."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Structural fix; works even if individual agent prompts drift over "
                    "time, because the protocol enforces the conflict at the framework "
                    "level."
                ),
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
    trace = build_synthetic_trace()
    client = pick_client()
    diagnostic = LencioniDiagnostic(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    diagnosis = diagnostic.run(trace)
    print(diagnosis.to_markdown())


if __name__ == "__main__":
    main()
