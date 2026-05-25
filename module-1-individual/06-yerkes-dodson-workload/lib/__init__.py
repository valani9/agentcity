"""vstack.yerkes_dodson -- the inverted-U workload-performance curve
applied to AI agents.

Anchored in:
  - Yerkes & Dodson (1908) -- original inverted-U.
  - Sweller (1988, 1994, 2011) Cognitive Load Theory.
  - Kahneman (1973) Attention and Effort.
  - Hancock-Warm (1989) dynamic adaptability.
  - Eysenck-Calvo (1992) Attentional Control Theory.
  - Hebb (1955) arousal-as-precursor.
  - Liu et al. (2024) lost-in-the-middle LLM context-saturation finding.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: ``WorkloadDetector`` remains exported as an alias
for ``YerkesDodsonAnalyzer``.

Quick start
-----------

    from vstack.yerkes_dodson import (
        YerkesDodsonAnalyzer,
        AgentPerformanceTrace,
        PressureInputs,
    )
    from vstack.aar import AnthropicClient

    trace = AgentPerformanceTrace(
        agent_id="research-agent-001",
        task="Compile a 1-page summary on prompt injection defenses.",
        pressure=PressureInputs(
            deadline_pressure="absurd",
            budget_pressure="absurd",
            task_complexity="complex",
        ),
        observed_behaviors=[
            "Agent cited 3 papers without verifying they exist.",
            "Agent shipped without running its own check.",
        ],
        outcome="Summary contains 2 fabricated citations.",
        success=False,
    )
    detection = YerkesDodsonAnalyzer(AnthropicClient(), mode="forensic").run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-yerkes analyze --trace trace.json --mode forensic
    vstack-yerkes playbooks
    vstack-yerkes compose
    vstack-yerkes schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    YERKES_DODSON_COMPOSITION,
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
    LLMClient,
    WorkloadDetector,  # legacy alias
    YerkesDodsonAnalyzer,
    YerkesDodsonAnalyzerAsync,
)
from .prompts import (
    FORENSIC_COGNITIVE_LOAD_PROMPT,
    FORENSIC_CONTEXT_SATURATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_WORKLOAD_PROMPT,
    WORKLOAD_PROMPT,  # legacy alias
    YERKES_DODSON_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    COGNITIVE_LOAD_COMPONENTS,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    WORKLOAD_PROFILE_PATTERNS,
    WORKLOAD_ZONES,
    YERKES_DODSON_MODES,
    AgentPerformanceTrace,
    AttachedPlaybook,
    BaselineComparison,
    CognitiveLoadAnalysis,
    CognitiveLoadComponent,
    ComposedPatternHandoff,
    ContextSaturation,
    EffortEstimate,
    InterventionType,
    PressureInputs,
    Severity,
    WorkloadDetection,
    WorkloadIntervention,
    WorkloadProfilePattern,
    WorkloadZone,
    WorkloadZoneEvidence,
    YerkesDodsonMode,
    severity_from_distance,
)

__all__ = [
    # Analyzer entry points
    "YerkesDodsonAnalyzer",
    "YerkesDodsonAnalyzerAsync",
    "WorkloadDetector",  # v0.0.x legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentPerformanceTrace",
    "PressureInputs",
    # Schema -- output
    "WorkloadZoneEvidence",
    "CognitiveLoadAnalysis",
    "ContextSaturation",
    "WorkloadIntervention",
    "WorkloadDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "WorkloadZone",
    "YerkesDodsonMode",
    "WorkloadProfilePattern",
    "Severity",
    "CognitiveLoadComponent",
    "InterventionType",
    "EffortEstimate",
    "WORKLOAD_ZONES",
    "YERKES_DODSON_MODES",
    "WORKLOAD_PROFILE_PATTERNS",
    "COGNITIVE_LOAD_COMPONENTS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_distance",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "YERKES_DODSON_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "YERKES_DODSON_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_WORKLOAD_PROMPT",
    "FORENSIC_COGNITIVE_LOAD_PROMPT",
    "FORENSIC_CONTEXT_SATURATION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "WORKLOAD_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
