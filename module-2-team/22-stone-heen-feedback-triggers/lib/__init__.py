"""vstack.feedback_triggers -- Stone & Heen's three feedback triggers
(truth, relationship, identity) applied to user-agent feedback exchanges.

Anchored in Stone & Heen (2014) and Edmondson (1999) psychological safety.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``FeedbackTriggerDetector`` aliased to
``FeedbackTriggerAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    FEEDBACK_TRIGGERS_COMPOSITION,
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
    FeedbackTriggerAnalyzer,
    FeedbackTriggerAnalyzerAsync,
    FeedbackTriggerDetector,
    LLMClient,
)
from .prompts import (
    FORENSIC_DEFENSE_PATTERN_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_SOURCE_ATTRIBUTION_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_TRIGGER_SCORING_PROMPT,
    TRIGGER_SCORING_PROMPT,
    TRIGGER_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    FEEDBACK_PROFILE_PATTERNS,
    FEEDBACK_TRIGGERS_MODES,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    TRIGGERS,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DefensePatternAudit,
    EffortEstimate,
    FeedbackInteractionTrace,
    FeedbackMessage,
    FeedbackProfilePattern,
    FeedbackTriggerDetection,
    FeedbackTriggersMode,
    InterventionType,
    Severity,
    SourceAttributionAudit,
    TriggerEvidence,
    TriggerIntervention,
    severity_from_trigger,
)

__all__ = [
    "FeedbackTriggerAnalyzer",
    "FeedbackTriggerAnalyzerAsync",
    "FeedbackTriggerDetector",
    "LLMClient",
    "AsyncLLMClient",
    "FeedbackMessage",
    "FeedbackInteractionTrace",
    "TriggerEvidence",
    "DefensePatternAudit",
    "SourceAttributionAudit",
    "TriggerIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "FeedbackTriggerDetection",
    "FeedbackTriggersMode",
    "FeedbackProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "TRIGGERS",
    "FEEDBACK_TRIGGERS_MODES",
    "FEEDBACK_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_trigger",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "FEEDBACK_TRIGGERS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "TRIGGER_SYSTEM_PROMPT",
    "TRIGGER_SCORING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_TRIGGER_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_DEFENSE_PATTERN_PROMPT",
    "FORENSIC_SOURCE_ATTRIBUTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
