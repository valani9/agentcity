"""vstack.schein_culture -- Edgar Schein's three-layer culture model
(artifacts / espoused values / underlying assumptions) applied to AI
agent behavior.

Anchored in Schein 1985, 2010, 2017.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``CultureAuditDetector`` aliased to
``CultureAuditAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    SCHEIN_COMPOSITION,
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
    CultureAuditAnalyzer,
    CultureAuditAnalyzerAsync,
    CultureAuditDetector,
    LLMClient,
)
from .prompts import (
    FORENSIC_ALIGNMENT_DRIFT_PROMPT,
    FORENSIC_HIDDEN_ASSUMPTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SCHEIN_ANALYSIS_PROMPT,
    SCHEIN_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_SCHEIN_ANALYSIS_PROMPT,
    assemble_prompt,
)
from .schema import (
    CULTURE_LAYERS,
    INTERVENTION_TYPES,
    SCHEIN_MODES,
    SCHEIN_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentCultureTrace,
    AlignmentDriftAudit,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CultureAuditDetection,
    CultureIntervention,
    CultureObservation,
    EffortEstimate,
    HiddenAssumptionAudit,
    InterventionType,
    LayerEvidence,
    ScheinMode,
    ScheinProfilePattern,
    Severity,
    severity_from_misalignment,
)

__all__ = [
    "CultureAuditAnalyzer",
    "CultureAuditAnalyzerAsync",
    "CultureAuditDetector",
    "LLMClient",
    "AsyncLLMClient",
    "CultureObservation",
    "AgentCultureTrace",
    "LayerEvidence",
    "AlignmentDriftAudit",
    "HiddenAssumptionAudit",
    "CultureIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CultureAuditDetection",
    "ScheinMode",
    "ScheinProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "CULTURE_LAYERS",
    "SCHEIN_MODES",
    "SCHEIN_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_misalignment",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "SCHEIN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SCHEIN_SYSTEM_PROMPT",
    "SCHEIN_ANALYSIS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_SCHEIN_ANALYSIS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_ALIGNMENT_DRIFT_PROMPT",
    "FORENSIC_HIDDEN_ASSUMPTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
