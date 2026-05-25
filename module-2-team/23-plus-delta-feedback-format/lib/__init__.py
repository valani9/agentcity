"""vstack.plus_delta -- structured plus/delta inter-agent feedback
format generator.

From the facilitator canon (Joiner Associates 1990s; Brown "Dare to
Lead" 2018; retrospective-meeting literature).

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``PlusDeltaFeedbackGenerator`` aliased to
``PlusDeltaFeedbackAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    PLUS_DELTA_COMPOSITION,
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
    PlusDeltaFeedbackAnalyzer,
    PlusDeltaFeedbackAnalyzerAsync,
    PlusDeltaFeedbackGenerator,
)
from .prompts import (
    FORENSIC_BEHAVIORAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SPECIFICITY_PROMPT,
    PLUS_DELTA_PROMPT,
    PLUS_DELTA_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_PLUS_DELTA_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    PLUS_DELTA_MODES,
    PLUS_DELTA_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AttachedPlaybook,
    BaselineComparison,
    BehavioralVsGenericAudit,
    Commitment,
    ComposedPatternHandoff,
    DeltaItem,
    EffortEstimate,
    FeedbackRequest,
    InterventionType,
    PlusDeltaFeedback,
    PlusDeltaIntervention,
    PlusDeltaMode,
    PlusDeltaProfilePattern,
    PlusItem,
    Severity,
    SpecificityAudit,
    severity_from_quality,
)

__all__ = [
    "PlusDeltaFeedbackAnalyzer",
    "PlusDeltaFeedbackAnalyzerAsync",
    "PlusDeltaFeedbackGenerator",
    "LLMClient",
    "AsyncLLMClient",
    "FeedbackRequest",
    "PlusItem",
    "DeltaItem",
    "Commitment",
    "SpecificityAudit",
    "BehavioralVsGenericAudit",
    "PlusDeltaIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "PlusDeltaFeedback",
    "PlusDeltaMode",
    "PlusDeltaProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "PLUS_DELTA_MODES",
    "PLUS_DELTA_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_quality",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "PLUS_DELTA_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "PLUS_DELTA_SYSTEM_PROMPT",
    "PLUS_DELTA_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_PLUS_DELTA_PROMPT",
    "FORENSIC_SPECIFICITY_PROMPT",
    "FORENSIC_BEHAVIORAL_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
