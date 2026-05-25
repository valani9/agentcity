"""vstack.thomas_kilmann -- Thomas-Kilmann's five conflict styles
applied to AI agent interactions.

Anchored in Thomas & Kilmann 1974.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``ConflictStyleSelector`` aliased to
``ConflictStyleAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    THOMAS_KILMANN_COMPOSITION,
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
    ConflictStyleAnalyzer,
    ConflictStyleAnalyzerAsync,
    ConflictStyleSelector,
    LLMClient,
)
from .prompts import (
    FORENSIC_CONSISTENCY_PROMPT,
    FORENSIC_RECOMMENDATIONS_PROMPT,
    FORENSIC_STYLE_FIT_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    RECOMMENDATIONS_PROMPT,
    STANDARD_RECOMMENDATIONS_PROMPT,
    STANDARD_TK_ANALYSIS_PROMPT,
    TK_ANALYSIS_PROMPT,
    TK_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    STYLES,
    THOMAS_KILMANN_MODES,
    THOMAS_KILMANN_PROFILE_PATTERNS,
    AgentInteractionTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    ConflictStyleSelection,
    EffortEstimate,
    InteractionTurn,
    InterventionType,
    PatternConsistencyAudit,
    Severity,
    StyleFitAudit,
    StyleRecommendation,
    StyleScore,
    ThomasKilmannMode,
    ThomasKilmannProfilePattern,
    severity_from_mismatch,
)

__all__ = [
    "ConflictStyleAnalyzer",
    "ConflictStyleAnalyzerAsync",
    "ConflictStyleSelector",
    "LLMClient",
    "AsyncLLMClient",
    "InteractionTurn",
    "AgentInteractionTrace",
    "StyleScore",
    "StyleFitAudit",
    "PatternConsistencyAudit",
    "StyleRecommendation",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "ConflictStyleSelection",
    "ThomasKilmannMode",
    "ThomasKilmannProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "STYLES",
    "THOMAS_KILMANN_MODES",
    "THOMAS_KILMANN_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_mismatch",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "THOMAS_KILMANN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "TK_SYSTEM_PROMPT",
    "TK_ANALYSIS_PROMPT",
    "RECOMMENDATIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_TK_ANALYSIS_PROMPT",
    "STANDARD_RECOMMENDATIONS_PROMPT",
    "FORENSIC_STYLE_FIT_PROMPT",
    "FORENSIC_CONSISTENCY_PROMPT",
    "FORENSIC_RECOMMENDATIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
