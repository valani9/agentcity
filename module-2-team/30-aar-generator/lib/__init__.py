"""
vstack.aar — Wharton 4-step After-Action Review generator for AI agents.

This package implements pattern #30 of the vstack library: After-Action
Reviews applied to AI agent runs, anchored in the Wharton@Work AAR doctrine
and US Army TC 25-20.

Quick start:

    from vstack.aar import AARGenerator, AgentTrace, TraceStep
    from vstack.aar.clients import AnthropicClient

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

from ._analyzer import AARAnalyzer, AARAnalyzerAsync, AsyncLLMClient
from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    AAR_COMPOSITION,
    recommended_downstream,
    recommended_upstream,
)
from ._guards import detect_injection, fence, sanitize_for_prompt
from ._json_parsing import extract_json_array
from ._logging import (
    JsonFormatter,
    configure_json_logging,
    current_pattern,
    current_run_id,
    get_logger,
    new_run_id,
    run_context,
)
from ._playbooks import (
    PLAYBOOKS,
    all_playbook_keys,
    find_playbook,
    find_playbook_for_intervention,
)
from ._retry import with_retry
from ._telemetry import (
    InMemoryTelemetrySink,
    NullTelemetrySink,
    TelemetryEvent,
    TelemetrySink,
    get_default_sink,
    record_llm_call,
    set_default_sink,
    time_call,
)
from .clients import (
    DEFAULT_TIMEOUT_SECONDS,
    AnthropicAsyncClient,
    AnthropicClient,
    LLMUsage,
    OllamaAsyncClient,
    OllamaClient,
    OpenAIAsyncClient,
    OpenAIClient,
    StubClient,
)
from .generator import AARGenerator, LLMClient
from .schema import (
    AAR,
    AAR_MODES,
    AAR_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AARMode,
    AARProfilePattern,
    AgentTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    Lesson,
    LessonGroundednessAudit,
    NextStep,
    Severity,
    TraceQualityAudit,
    TraceStep,
    severity_from_gap,
)

__all__ = [
    # Pattern #30 -- AAR (legacy v0.0.x surface preserved)
    "AARGenerator",
    "LLMClient",
    "AAR",
    "AgentTrace",
    "Lesson",
    "NextStep",
    "TraceStep",
    # v0.2.0 analyzer surface
    "AARAnalyzer",
    "AARAnalyzerAsync",
    "AsyncLLMClient",
    "AARMode",
    "AARProfilePattern",
    "Severity",
    "EffortEstimate",
    "AAR_MODES",
    "AAR_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "TraceQualityAudit",
    "LessonGroundednessAudit",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "severity_from_gap",
    # v0.2.0 calibration + composition + playbooks
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "AAR_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # LLM client adapters (sync + async)
    "AnthropicClient",
    "OpenAIClient",
    "OllamaClient",
    "StubClient",
    "AnthropicAsyncClient",
    "OpenAIAsyncClient",
    "OllamaAsyncClient",
    "LLMUsage",
    "DEFAULT_TIMEOUT_SECONDS",
    # Shared retry / JSON parsing
    "extract_json_array",
    "with_retry",
    # Structured logging
    "JsonFormatter",
    "configure_json_logging",
    "current_pattern",
    "current_run_id",
    "get_logger",
    "new_run_id",
    "run_context",
    # Token / cost telemetry
    "InMemoryTelemetrySink",
    "NullTelemetrySink",
    "TelemetryEvent",
    "TelemetrySink",
    "get_default_sink",
    "record_llm_call",
    "set_default_sink",
    "time_call",
    # Input guards
    "detect_injection",
    "fence",
    "sanitize_for_prompt",
]

__version__ = "0.2.0"
