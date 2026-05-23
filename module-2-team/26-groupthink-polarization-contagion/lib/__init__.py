"""agentcity.debate_pathology -- three classic debate-dynamics pathologies
(groupthink, polarization, contagion) applied to multi-agent AI debates.

Anchored in Janis 1972, Stoner 1968, Sunstein 2002, Hatfield/Cacioppo/Rapson 1993.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``DebatePathologyDetector`` aliased to
``DebatePathologyAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    DEBATE_PATHOLOGY_COMPOSITION,
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
    DebatePathologyAnalyzer,
    DebatePathologyAnalyzerAsync,
    DebatePathologyDetector,
    LLMClient,
)
from .prompts import (
    DEBATE_SYSTEM_PROMPT,
    FORENSIC_CONVERGENCE_TIMELINE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_TONE_CASCADE_PROMPT,
    INTERVENTIONS_PROMPT,
    PATHOLOGY_SCORING_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_PATHOLOGY_SCORING_PROMPT,
    assemble_prompt,
)
from .schema import (
    DEBATE_PATHOLOGY_MODES,
    DEBATE_PATHOLOGY_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    PATHOLOGIES,
    SEVERITY_ORDER,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    ConvergenceTimelineAudit,
    DebateIntervention,
    DebateMessage,
    DebatePathologyDetection,
    DebatePathologyMode,
    DebatePathologyProfilePattern,
    EffortEstimate,
    InterventionType,
    MultiAgentDebateTrace,
    PathologyEvidence,
    Severity,
    ToneCascadeAudit,
    severity_from_pathology,
)

__all__ = [
    "DebatePathologyAnalyzer",
    "DebatePathologyAnalyzerAsync",
    "DebatePathologyDetector",
    "LLMClient",
    "AsyncLLMClient",
    "DebateMessage",
    "MultiAgentDebateTrace",
    "PathologyEvidence",
    "ConvergenceTimelineAudit",
    "ToneCascadeAudit",
    "DebateIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "DebatePathologyDetection",
    "DebatePathologyMode",
    "DebatePathologyProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "PATHOLOGIES",
    "DEBATE_PATHOLOGY_MODES",
    "DEBATE_PATHOLOGY_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_pathology",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "DEBATE_PATHOLOGY_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "DEBATE_SYSTEM_PROMPT",
    "PATHOLOGY_SCORING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_PATHOLOGY_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_CONVERGENCE_TIMELINE_PROMPT",
    "FORENSIC_TONE_CASCADE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
