"""agentcity.glaser_conversation -- Glaser's Conversational Intelligence
(C-IQ) cortisol/oxytocin steering diagnostic applied to AI agent
conversations.

Anchored in Glaser 2014, Lieberman 2013 (neurochemistry), Stone-Heen 2014
(difficult conversations).

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``ConversationSteeringDetector`` aliased to
``ConversationSteeringAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    GLASER_COMPOSITION,
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
    ConversationSteeringAnalyzer,
    ConversationSteeringAnalyzerAsync,
    ConversationSteeringDetector,
    LLMClient,
)
from .prompts import (
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_LEVEL_TRANSITION_PROMPT,
    FORENSIC_TRIGGER_INVENTORY_PROMPT,
    GLASER_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_STATE_PROMPT,
    STATE_PROMPT,
    assemble_prompt,
)
from .schema import (
    CONVERSATION_LEVELS,
    GLASER_MODES,
    GLASER_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    NEUROCHEMICAL_STATES,
    SEVERITY_ORDER,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    ConversationSteeringDetection,
    ConversationTrace,
    ConversationTurn,
    EffortEstimate,
    GlaserMode,
    GlaserProfilePattern,
    InterventionType,
    LevelTransitionAudit,
    NeurochemicalEvidence,
    Severity,
    SteeringIntervention,
    TriggerInventoryAudit,
    severity_from_cortisol,
)

__all__ = [
    "ConversationSteeringAnalyzer",
    "ConversationSteeringAnalyzerAsync",
    "ConversationSteeringDetector",
    "LLMClient",
    "AsyncLLMClient",
    "ConversationTrace",
    "ConversationTurn",
    "NeurochemicalEvidence",
    "TriggerInventoryAudit",
    "LevelTransitionAudit",
    "SteeringIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "ConversationSteeringDetection",
    "GlaserMode",
    "GlaserProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "CONVERSATION_LEVELS",
    "NEUROCHEMICAL_STATES",
    "GLASER_MODES",
    "GLASER_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_cortisol",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "GLASER_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "GLASER_SYSTEM_PROMPT",
    "STATE_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_STATE_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_TRIGGER_INVENTORY_PROMPT",
    "FORENSIC_LEVEL_TRANSITION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
