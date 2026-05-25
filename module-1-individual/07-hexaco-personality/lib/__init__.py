"""vstack.hexaco -- Lee & Ashton's HEXACO personality model applied
to AI agents. The H-factor (Honesty-Humility) is the safety dimension.

Anchored in:
  - Lee & Ashton (2004, 2012, 2018) -- HEXACO + HEXACO-100.
  - Ashton & Lee (2007) -- empirical case for the 6-factor structure.
  - Bourdage et al. (2007) -- counterproductive-work-behavior anchor.
  - Howard & van Zandvoort (2024) -- HEXACO profiling of GPT-4.
  - Anthropic Claude Constitution (2023) -- HHH mapping.
  - Paulhus & Williams (2002) Dark Triad -- LLM analog of low-H.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: ``HEXACOPersonalityDetector`` remains exported as
an alias for ``HEXACOPersonalityAnalyzer``.

Quick start
-----------

    from vstack.hexaco import (
        HEXACOPersonalityAnalyzer,
        AgentPersonalityTrace,
    )
    from vstack.aar import AnthropicClient

    trace = AgentPersonalityTrace(
        agent_id="research-agent-001",
        task="Compile a 1-page summary on prompt injection defenses.",
        task_class="high_stakes_advisor",
        observed_behaviors=["Agent cited 3 unverified papers."],
        safety_relevant_events=["Agent bypassed fact-check step."],
        outcome="Summary contains 2 fabricated citations.",
        success=False,
    )
    detection = HEXACOPersonalityAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-hexaco analyze --trace trace.json --mode forensic
    vstack-hexaco playbooks
    vstack-hexaco compose
    vstack-hexaco schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    HEXACO_COMPOSITION,
    recommended_downstream,
    recommended_upstream,
)
from ._playbooks import (
    PLAYBOOKS,
    all_playbook_keys,
    find_playbook,
    find_playbook_for_intervention,
)
from .generator import (
    AsyncLLMClient,
    HEXACOPersonalityAnalyzer,
    HEXACOPersonalityAnalyzerAsync,
    HEXACOPersonalityDetector,  # legacy alias
    LLMClient,
)
from .prompts import (
    FORENSIC_FACETS_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SAFETY_AUDIT_PROMPT,
    HEXACO_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy alias
    PROFILE_PROMPT,  # legacy alias
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_PROFILE_PROMPT,
    assemble_prompt,
)
from .schema import (
    FACETS_BY_FACTOR,
    HEXACO_FACETS,
    HEXACO_FACTORS,
    HEXACO_MODES,
    HEXACO_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    TASK_CLASSES,
    AgentPersonalityTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    FacetScore,
    FactorScore,
    HEXACODetection,
    HEXACOFacet,
    HEXACOFactor,
    HEXACOFactorOrNone,
    HEXACOIntervention,
    HEXACOMode,
    HEXACOProfilePattern,
    InterventionType,
    SafetyEventAudit,
    Severity,
    TaskClass,
    severity_from_fit,
)

__all__ = [
    # Analyzer entry points
    "HEXACOPersonalityAnalyzer",
    "HEXACOPersonalityAnalyzerAsync",
    "HEXACOPersonalityDetector",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentPersonalityTrace",
    # Schema -- output
    "FactorScore",
    "FacetScore",
    "SafetyEventAudit",
    "HEXACOIntervention",
    "HEXACODetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "HEXACOFactor",
    "HEXACOFactorOrNone",
    "HEXACOFacet",
    "HEXACOMode",
    "HEXACOProfilePattern",
    "TaskClass",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "HEXACO_FACTORS",
    "HEXACO_FACETS",
    "FACETS_BY_FACTOR",
    "HEXACO_MODES",
    "HEXACO_PROFILE_PATTERNS",
    "TASK_CLASSES",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_fit",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "HEXACO_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "HEXACO_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_PROFILE_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_FACETS_PROMPT",
    "FORENSIC_SAFETY_AUDIT_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "PROFILE_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
