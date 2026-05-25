"""vstack.lencioni -- Patrick Lencioni's Five Dysfunctions of a Team,
applied to multi-agent AI systems.

Anchored in Lencioni (2002), Lencioni (2005), Edmondson (1999),
Hackman (2002), Salas et al. (2018), Schein (1990), Wang et al. (2023).

Three pipeline modes with full v0.2.0 production infrastructure.
Backward-compatible: ``LencioniDiagnostic`` is aliased to ``LencioniAnalyzer``.

Quick start::

    from vstack.lencioni import (
        LencioniAnalyzer,
        MultiAgentTrace,
        AgentMessage,
    )
    from vstack.aar.clients import AnthropicClient

    trace = MultiAgentTrace(
        goal="Generate a marketing campaign",
        agents=["researcher", "strategist", "critic"],
        messages=[...],
        outcome="Campaign launched, performed at 12% of target",
        success=False,
    )
    diagnosis = LencioniAnalyzer(AnthropicClient(), mode="standard").run(trace)
    print(diagnosis.to_markdown())
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    LENCIONI_COMPOSITION,
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
    LencioniAnalyzer,
    LencioniAnalyzerAsync,
    LencioniDiagnostic,
    LLMClient,
)
from .prompts import (
    FORENSIC_CASCADE_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PSYCH_SAFETY_PROMPT,
    INTERVENTIONS_PROMPT,
    LENCIONI_SYSTEM_PROMPT,
    PYRAMID_SCORE_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_PYRAMID_PROMPT,
    assemble_prompt,
)
from .schema import (
    DYSFUNCTIONS,
    INTERVENTION_TYPES,
    LENCIONI_MODES,
    LENCIONI_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentMessage,
    AttachedPlaybook,
    BaselineComparison,
    CascadeAudit,
    ComposedPatternHandoff,
    DysfunctionEvidence,
    EffortEstimate,
    Intervention,
    InterventionType,
    LencioniDiagnosis,
    LencioniMode,
    LencioniProfilePattern,
    MultiAgentTrace,
    PsychSafetyAudit,
    Severity,
    severity_from_score,
)

__all__ = [
    "LencioniAnalyzer",
    "LencioniAnalyzerAsync",
    "LencioniDiagnostic",
    "LLMClient",
    "AsyncLLMClient",
    "AgentMessage",
    "MultiAgentTrace",
    "DysfunctionEvidence",
    "CascadeAudit",
    "PsychSafetyAudit",
    "Intervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "LencioniDiagnosis",
    "LencioniMode",
    "LencioniProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "DYSFUNCTIONS",
    "LENCIONI_MODES",
    "LENCIONI_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_score",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "LENCIONI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "LENCIONI_SYSTEM_PROMPT",
    "PYRAMID_SCORE_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_PYRAMID_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_CASCADE_PROMPT",
    "FORENSIC_PSYCH_SAFETY_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
