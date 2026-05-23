"""agentcity.social_loafing -- Latané, Williams & Harkins (1979) applied to
multi-agent AI systems.

Three pipeline modes with full v0.2.0 production infrastructure.
Backward-compatible: ``SocialLoafingDetector`` aliased to ``SocialLoafingAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    SOCIAL_LOAFING_COMPOSITION,
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
    SocialLoafingAnalyzer,
    SocialLoafingAnalyzerAsync,
    SocialLoafingDetector,
)
from .prompts import (
    FORENSIC_ANONYMITY_PROMPT,
    FORENSIC_FREE_RIDING_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    LOAFING_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SOCIAL_LOAFING_SYSTEM_PROMPT,
    STANDARD_CONTRIBUTION_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    SOCIAL_LOAFING_MODES,
    SOCIAL_LOAFING_PROFILE_PATTERNS,
    AgentContribution,
    AgentMessage,
    AnonymityAudit,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    FreeRidingChain,
    InterventionType,
    LoafingIntervention,
    MultiAgentTaskTrace,
    Severity,
    SocialLoafingDetection,
    SocialLoafingMode,
    SocialLoafingProfilePattern,
    severity_from_gini,
)

__all__ = [
    "SocialLoafingAnalyzer",
    "SocialLoafingAnalyzerAsync",
    "SocialLoafingDetector",
    "LLMClient",
    "AsyncLLMClient",
    "MultiAgentTaskTrace",
    "AgentMessage",
    "AgentContribution",
    "AnonymityAudit",
    "FreeRidingChain",
    "LoafingIntervention",
    "SocialLoafingDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    "SocialLoafingMode",
    "SocialLoafingProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "SOCIAL_LOAFING_MODES",
    "SOCIAL_LOAFING_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_gini",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "SOCIAL_LOAFING_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SOCIAL_LOAFING_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_CONTRIBUTION_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_ANONYMITY_PROMPT",
    "FORENSIC_FREE_RIDING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "LOAFING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
