"""vstack.mcallister_trust -- McAllister cognitive vs affective trust
dimensions applied to user-agent conversations.

Anchored in McAllister (1995), Goleman (1995).

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``TrustBalanceDetector`` is aliased to
``TrustBalanceAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    MCALLISTER_COMPOSITION,
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
    TrustBalanceAnalyzer,
    TrustBalanceAnalyzerAsync,
    TrustBalanceDetector,
)
from .prompts import (
    DIMENSION_SCORING_PROMPT,
    FORENSIC_CARE_PROMPT,
    FORENSIC_COMPETENCE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_DIMENSION_SCORING_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    TRUST_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    MCALLISTER_MODES,
    MCALLISTER_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    TRUST_DIMENSIONS,
    AttachedPlaybook,
    BaselineComparison,
    CareSignalsAudit,
    ComposedPatternHandoff,
    CompetenceSignalsAudit,
    ConversationTurn,
    EffortEstimate,
    InterventionType,
    McAllisterMode,
    McAllisterProfilePattern,
    Severity,
    TrustBalanceDetection,
    TrustConversationTrace,
    TrustDimensionEvidence,
    TrustIntervention,
    severity_from_gap,
)

__all__ = [
    "TrustBalanceAnalyzer",
    "TrustBalanceAnalyzerAsync",
    "TrustBalanceDetector",
    "LLMClient",
    "AsyncLLMClient",
    "TrustConversationTrace",
    "ConversationTurn",
    "TrustDimensionEvidence",
    "TrustIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CompetenceSignalsAudit",
    "CareSignalsAudit",
    "TrustBalanceDetection",
    "McAllisterMode",
    "McAllisterProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "TRUST_DIMENSIONS",
    "MCALLISTER_MODES",
    "MCALLISTER_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_gap",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "MCALLISTER_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "TRUST_SYSTEM_PROMPT",
    "DIMENSION_SCORING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DIMENSION_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_COMPETENCE_PROMPT",
    "FORENSIC_CARE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
