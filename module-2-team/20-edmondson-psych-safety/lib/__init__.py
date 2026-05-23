"""agentcity.psych_safety -- Edmondson Psychological Safety diagnostic
for multi-agent AI systems.

Anchored in Edmondson 1999, Edmondson 2018, Janis 1972 groupthink,
Wang 2023 cooperative LLM agents.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``PsychologicalSafetyDetector`` aliased to
``PsychologicalSafetyAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    PSYCH_SAFETY_COMPOSITION,
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
    PsychologicalSafetyAnalyzer,
    PsychologicalSafetyAnalyzerAsync,
    PsychologicalSafetyDetector,
)
from .prompts import (
    BEHAVIOR_SCORING_PROMPT,
    FORENSIC_ERROR_REPORTING_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_VOICE_AUDIT_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    STANDARD_BEHAVIOR_SCORING_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    BEHAVIORS,
    INTERVENTION_TYPES,
    PSYCH_SAFETY_MODES,
    PSYCH_SAFETY_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentMessage,
    AttachedPlaybook,
    BaselineComparison,
    BehaviorEvidence,
    ComposedPatternHandoff,
    EffortEstimate,
    ErrorReportingAudit,
    InterventionType,
    MultiAgentSafetyTrace,
    PsychologicalSafetyDetection,
    PsychSafetyMode,
    PsychSafetyProfilePattern,
    SafetyIntervention,
    Severity,
    VoiceSignalAudit,
    severity_from_absence,
)

__all__ = [
    "PsychologicalSafetyAnalyzer",
    "PsychologicalSafetyAnalyzerAsync",
    "PsychologicalSafetyDetector",
    "LLMClient",
    "AsyncLLMClient",
    "AgentMessage",
    "MultiAgentSafetyTrace",
    "BehaviorEvidence",
    "VoiceSignalAudit",
    "ErrorReportingAudit",
    "SafetyIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "PsychologicalSafetyDetection",
    "PsychSafetyMode",
    "PsychSafetyProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "BEHAVIORS",
    "PSYCH_SAFETY_MODES",
    "PSYCH_SAFETY_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_absence",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "PSYCH_SAFETY_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SAFETY_SYSTEM_PROMPT",
    "BEHAVIOR_SCORING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_BEHAVIOR_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_VOICE_AUDIT_PROMPT",
    "FORENSIC_ERROR_REPORTING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
