"""agentcity.group_decision -- facilitator-canon decision-aggregation
methods (concurring / majority / consensus / fist-to-five / unanimous)
applied to multi-agent decision-making.

Anchored in Kaner 2014 facilitator canon. Generative pattern:
recommends a decision model + emits a protocol spec, with optional
local vote tally.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``DecisionProtocolGenerator`` aliased to
``DecisionProtocolAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    GROUP_DECISION_COMPOSITION,
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
    DecisionProtocolAnalyzer,
    DecisionProtocolAnalyzerAsync,
    DecisionProtocolGenerator,
    LLMClient,
)
from .prompts import (
    DECISION_PROTOCOL_PROMPT,
    DECISION_SYSTEM_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_METHOD_FIT_PROMPT,
    FORENSIC_TALLY_INTEGRITY_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_DECISION_PROTOCOL_PROMPT,
    assemble_prompt,
)
from .schema import (
    DECISION_MODELS,
    GROUP_DECISION_MODES,
    GROUP_DECISION_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    AgentVote,
    AggregationResult,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DecisionOption,
    DecisionProtocol,
    DecisionRequest,
    EffortEstimate,
    GroupDecisionIntervention,
    GroupDecisionMode,
    GroupDecisionProfilePattern,
    InterventionType,
    MethodFitAudit,
    Severity,
    TallyIntegrityAudit,
    severity_from_fit,
)
from .tally import tally_votes

__all__ = [
    "DecisionProtocolAnalyzer",
    "DecisionProtocolAnalyzerAsync",
    "DecisionProtocolGenerator",
    "LLMClient",
    "AsyncLLMClient",
    "DecisionRequest",
    "DecisionOption",
    "AgentVote",
    "AggregationResult",
    "MethodFitAudit",
    "TallyIntegrityAudit",
    "GroupDecisionIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "DecisionProtocol",
    "GroupDecisionMode",
    "GroupDecisionProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "DECISION_MODELS",
    "GROUP_DECISION_MODES",
    "GROUP_DECISION_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_fit",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "GROUP_DECISION_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "tally_votes",
    "DECISION_SYSTEM_PROMPT",
    "DECISION_PROTOCOL_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DECISION_PROTOCOL_PROMPT",
    "FORENSIC_METHOD_FIT_PROMPT",
    "FORENSIC_TALLY_INTEGRITY_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
