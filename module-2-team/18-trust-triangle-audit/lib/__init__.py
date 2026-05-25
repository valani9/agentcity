"""vstack.trust_triangle -- Frei & Morriss's Trust Triangle
(Logic / Authenticity / Empathy), applied to AI agents.

Anchored in Frei & Morriss 2020, Edmondson 1999, Goleman 1995,
Lewis 2020 (RAG), Sharma 2023 (sycophancy).

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``TrustTriangleAuditor`` aliased to
``TrustTriangleAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    TRUST_TRIANGLE_COMPOSITION,
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
    TrustTriangleAnalyzer,
    TrustTriangleAnalyzerAsync,
    TrustTriangleAuditor,
)
from .prompts import (
    FORENSIC_CONTEXT_SENSITIVITY_PROMPT,
    FORENSIC_HALLUCINATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SYCOPHANCY_PROMPT,
    INTERVENTIONS_PROMPT,
    LEG_SCORE_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_LEG_SCORE_PROMPT,
    TRUST_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    LEGS,
    SEVERITY_ORDER,
    TRUST_PROFILE_PATTERNS,
    TRUST_TRIANGLE_MODES,
    AgentInteractionTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    ContextSensitivityAudit,
    EffortEstimate,
    HallucinationAudit,
    InteractionTurn,
    InterventionType,
    LegEvidence,
    Severity,
    SycophancyAudit,
    TrustIntervention,
    TrustProfilePattern,
    TrustTriangleAudit,
    TrustTriangleMode,
    severity_from_wobble,
)

__all__ = [
    "TrustTriangleAnalyzer",
    "TrustTriangleAnalyzerAsync",
    "TrustTriangleAuditor",
    "LLMClient",
    "AsyncLLMClient",
    "AgentInteractionTrace",
    "InteractionTurn",
    "LegEvidence",
    "HallucinationAudit",
    "SycophancyAudit",
    "ContextSensitivityAudit",
    "TrustIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "TrustTriangleAudit",
    "TrustTriangleMode",
    "TrustProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "LEGS",
    "TRUST_TRIANGLE_MODES",
    "TRUST_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_wobble",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "TRUST_TRIANGLE_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "TRUST_SYSTEM_PROMPT",
    "LEG_SCORE_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_LEG_SCORE_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_HALLUCINATION_PROMPT",
    "FORENSIC_SYCOPHANCY_PROMPT",
    "FORENSIC_CONTEXT_SENSITIVITY_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
