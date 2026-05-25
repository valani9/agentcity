"""vstack.devils_advocate -- Critical-Evaluator / Devil's Advocate
role-separation diagnostic for single-agent traces.

Anchored in Janis 1972 groupthink, Schwenk 1990 structured dissent,
Klein 2007 pre-mortem.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``RoleSeparationDetector`` aliased to
``RoleSeparationAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    DEVILS_ADVOCATE_COMPOSITION,
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
    RoleSeparationAnalyzer,
    RoleSeparationAnalyzerAsync,
    RoleSeparationDetector,
)
from .prompts import (
    FORENSIC_APPROVAL_RATE_PROMPT,
    FORENSIC_CRITIC_VOICE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    ROLE_ANALYSIS_PROMPT,
    SEPARATOR_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_ROLE_ANALYSIS_PROMPT,
    assemble_prompt,
)
from .schema import (
    DEVILS_ADVOCATE_MODES,
    DEVILS_ADVOCATE_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    PHASES,
    SEVERITY_ORDER,
    ApprovalRateAudit,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CriticVoiceAudit,
    DevilsAdvocateMode,
    DevilsAdvocateProfilePattern,
    EffortEstimate,
    InterventionType,
    PhaseEvidence,
    RoleSeparationDetection,
    RoleSeparationIntervention,
    RoleStep,
    Severity,
    SingleAgentTrace,
    severity_from_separation,
)

__all__ = [
    "RoleSeparationAnalyzer",
    "RoleSeparationAnalyzerAsync",
    "RoleSeparationDetector",
    "LLMClient",
    "AsyncLLMClient",
    "RoleStep",
    "SingleAgentTrace",
    "PhaseEvidence",
    "ApprovalRateAudit",
    "CriticVoiceAudit",
    "RoleSeparationIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "RoleSeparationDetection",
    "DevilsAdvocateMode",
    "DevilsAdvocateProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "PHASES",
    "DEVILS_ADVOCATE_MODES",
    "DEVILS_ADVOCATE_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_separation",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "DEVILS_ADVOCATE_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SEPARATOR_SYSTEM_PROMPT",
    "ROLE_ANALYSIS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_ROLE_ANALYSIS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_APPROVAL_RATE_PROMPT",
    "FORENSIC_CRITIC_VOICE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
