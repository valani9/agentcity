"""vstack.superflocks -- Heffernan's superflocks fragility pattern for
multi-agent orchestrator routing.

Anchored in Heffernan 2014/2015, Muir 1996, Hackman 2002, Page 2007,
Salas 2018, Bandura 1977, Wang 2023.

Three pipeline modes with full v0.2.0 production infrastructure.
Backward-compatible: ``SuperflocksDetector`` aliased to ``SuperflocksAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    SUPERFLOCKS_COMPOSITION,
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
    SuperflocksAnalyzer,
    SuperflocksAnalyzerAsync,
    SuperflocksDetector,
)
from .prompts import (
    FORENSIC_CAPABILITY_AUDIT_PROMPT,
    FORENSIC_FAILURE_AUDIT_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    METRICS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_METRICS_PROMPT,
    SUPERFLOCKS_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    SUPERFLOCKS_MODES,
    SUPERFLOCKS_PROFILE_PATTERNS,
    AgentCapability,
    AttachedPlaybook,
    BaselineComparison,
    CapabilityComplementarityAudit,
    ComposedPatternHandoff,
    EffortEstimate,
    FailureClusteringAudit,
    FragilityIntervention,
    InterventionType,
    RoutingDecision,
    RoutingTrace,
    Severity,
    SuperflocksDetection,
    SuperflocksMetric,
    SuperflocksMode,
    SuperflocksProfilePattern,
    severity_from_fragility,
)

__all__ = [
    "SuperflocksAnalyzer",
    "SuperflocksAnalyzerAsync",
    "SuperflocksDetector",
    "LLMClient",
    "AsyncLLMClient",
    "RoutingTrace",
    "RoutingDecision",
    "AgentCapability",
    "SuperflocksMetric",
    "CapabilityComplementarityAudit",
    "FailureClusteringAudit",
    "FragilityIntervention",
    "SuperflocksDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    "SuperflocksMode",
    "SuperflocksProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "SUPERFLOCKS_MODES",
    "SUPERFLOCKS_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_fragility",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "SUPERFLOCKS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SUPERFLOCKS_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_METRICS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_CAPABILITY_AUDIT_PROMPT",
    "FORENSIC_FAILURE_AUDIT_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "METRICS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
