"""
agentcity.aar — Wharton 4-step After-Action Review generator for AI agents.

This package implements pattern #30 of the AgentCity library: After-Action
Reviews applied to AI agent runs, anchored in the Wharton@Work AAR doctrine
and US Army TC 25-20.

Quick start:

    from agentcity.aar import AARGenerator, AgentTrace, TraceStep
    from agentcity.aar.clients import AnthropicClient

    trace = AgentTrace(
        goal="Refactor the auth module to use JWTs",
        steps=[...],
        outcome="Created tokens but broke session middleware",
        success=False,
    )

    aar = AARGenerator(llm_client=AnthropicClient()).generate(trace)
    print(aar.to_markdown())

See README.md for the full pattern explanation, the OB framework anchoring,
and the comparison with adjacent agent-postmortem tooling.
"""

from ._json_parsing import extract_json_array
from ._retry import with_retry
from .clients import (
    AnthropicClient,
    OllamaClient,
    OpenAIClient,
    StubClient,
)
from .generator import AARGenerator, LLMClient
from .schema import AAR, AgentTrace, Lesson, NextStep, TraceStep

__all__ = [
    "AARGenerator",
    "LLMClient",
    "AAR",
    "AgentTrace",
    "Lesson",
    "NextStep",
    "TraceStep",
    "AnthropicClient",
    "OpenAIClient",
    "OllamaClient",
    "StubClient",
    "extract_json_array",
    "with_retry",
]

__version__ = "0.0.2"
