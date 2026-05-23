"""agentcity.org_structure -- Org-Structure Matrix diagnostic for AI agent
crews. Module 3 (organizational) pattern.

Six dimensions: specialization, formalization, centralization, hierarchy,
span_of_control, departmentalization. Maps each crew to a structural
archetype (flat-peer, hierarchical, centralized-functional,
decentralized-product, matrix, mixed) and reports the fit gap against
the task class.

Where Schein's Iceberg (#31) measures coherence and Robbins/Judge's
7-Characteristics (#32) measures cultural fit, this pattern measures
*structural* fit.

v0.2.0 features:
  - Three pipeline modes (quick/standard/forensic)
  - 10 StructureProfilePattern variants + 7-point Severity scale
  - Forensic ReportingGraphAudit + DecisionBottleneckAudit passes
  - Calibration baseline roundtrip + drift comparison
  - Cross-pattern composition manifest
  - 12 (dimension, failure_mode) playbooks anchored to Galbraith /
    Mintzberg
  - Production infra via agentcity.aar shared module

Quick start:

    from agentcity.org_structure import (
        StructureMatrixAnalyzer,
        CrewStructureTrace,
        AgentRole,
    )
    from agentcity.aar import AnthropicClient

    trace = CrewStructureTrace(
        crew_id="incident-001",
        task="Triage prod outage",
        task_class="incident_response",
        agents=[
            AgentRole(agent_id="a1", role_name="generalist"),
            AgentRole(agent_id="a2", role_name="generalist"),
        ],
        observed_behaviors=["both agents propose conflicting fixes"],
        outcome="conflict unresolved",
        success=False,
    )
    analysis = StructureMatrixAnalyzer(AnthropicClient()).run(trace)
    print(analysis.to_markdown())
    # profile_pattern: too_flat_for_critical_task
"""

from ._calibration import (
    compare_to_baseline,
    load_baseline,
    record_baseline,
)
from ._composition import (
    STRUCTURE_COMPOSITION,
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
    StructureMatrixAnalyzer,
    StructureMatrixAnalyzerAsync,
)
from .schema import (
    SEVERITY_ORDER,
    STRUCTURE_ARCHETYPES,
    STRUCTURE_DIMENSIONS,
    STRUCTURE_MODES,
    STRUCTURE_PROFILE_PATTERNS,
    AgentRole,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CrewStructureTrace,
    DecisionBottleneckAudit,
    EffortEstimate,
    InterventionType,
    ReportingGraphAudit,
    Severity,
    StructureAnalysis,
    StructureArchetype,
    StructureDimensionScore,
    StructureIntervention,
    StructureMode,
    StructureProfilePattern,
    TaskClass,
    severity_from_misfit,
)

__all__ = [
    "AgentRole",
    "AsyncLLMClient",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CrewStructureTrace",
    "DecisionBottleneckAudit",
    "EffortEstimate",
    "InterventionType",
    "LLMClient",
    "PLAYBOOKS",
    "ReportingGraphAudit",
    "SEVERITY_ORDER",
    "STRUCTURE_ARCHETYPES",
    "STRUCTURE_COMPOSITION",
    "STRUCTURE_DIMENSIONS",
    "STRUCTURE_MODES",
    "STRUCTURE_PROFILE_PATTERNS",
    "Severity",
    "StructureAnalysis",
    "StructureArchetype",
    "StructureDimensionScore",
    "StructureIntervention",
    "StructureMatrixAnalyzer",
    "StructureMatrixAnalyzerAsync",
    "StructureMode",
    "StructureProfilePattern",
    "TaskClass",
    "all_playbook_keys",
    "compare_to_baseline",
    "find_playbook",
    "find_playbook_for_intervention",
    "load_baseline",
    "record_baseline",
    "recommended_downstream",
    "recommended_upstream",
    "severity_from_misfit",
]

__version__ = "0.2.0"
