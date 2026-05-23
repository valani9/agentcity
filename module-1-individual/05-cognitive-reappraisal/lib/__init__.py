"""agentcity.cognitive_reappraisal -- Gross's emotion-regulation process
model applied to AI agents.

Anchored in 14 academic sources: Gross 1998/2001/2002/2014, Gross-John
2003 ERQ, McRae-Gross 2020 extended process model, Ochsner 2002,
Buhle 2014, Powers-LaBar 2019, Webb-Miles-Sheeran 2012, Aldao 2010,
Sheppes-Suri-Gross 2015, NH-Wisco-Lyubomirsky 2008, and the 2024-2025
sycophancy-as-suppression-under-pushback LLM literature.

Three pipeline modes (quick / standard / forensic) with full v0.1.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: `ReappraisalDetector` remains exported as alias
of `ReappraisalAnalyzer`.

Quick start
-----------

    from agentcity.cognitive_reappraisal import (
        ReappraisalAnalyzer,
        AgentRegulationTrace,
    )
    from agentcity.aar import AnthropicClient

    trace = AgentRegulationTrace(
        agent_id="support-agent",
        user_input="THIS IS THE THIRD TIME!!! I'm DONE.",
        user_emotion_label="angry",
        user_emotion_intensity=0.9,
        agent_response="I understand your concern. Per our policy, billing is final.",
        agent_internal_state="User is being unreasonable. Apply policy.",
        outcome="User escalated to manager.",
        success=False,
    )
    detection = ReappraisalAnalyzer(AnthropicClient(), mode="forensic").run(trace)
    print(detection.to_markdown())

CLI
---

    agentcity-reappraisal analyze --trace trace.json --mode forensic
    agentcity-reappraisal playbooks
    agentcity-reappraisal compose
    agentcity-reappraisal schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    REAPPRAISAL_COMPOSITION,
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
    ReappraisalAnalyzer,
    ReappraisalAnalyzerAsync,
    ReappraisalDetector,  # legacy alias
)
from .prompts import (
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PROCESS_MODEL_PROMPT,
    FORENSIC_STRATEGY_CHOICE_PROMPT,
    GROSS_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_STRATEGY_PROMPT,
    STRATEGY_PROMPT,
    assemble_prompt,
)
from .schema import (
    EXTENDED_PHASES,
    INTERVENTION_TYPES,
    PROCESS_MODEL_PHASES,
    REAPPRAISAL_MODES,
    REAPPRAISAL_PROFILE_PATTERNS,
    REAPPRAISAL_SUBTYPES,
    REGULATION_STRATEGIES,
    RUMINATION_FLAVORS,
    SEVERITY_ORDER,
    AffectivityProfile,
    AgentRegulationTrace,
    AttachedPlaybook,
    BaselineComparison,
    CascadeAnalysis,
    ComposedPatternHandoff,
    EffortEstimate,
    ExtendedPhase,
    InterventionType,
    ProcessModelPhase,
    ProcessModelPhaseEvidence,
    ReappraisalMode,
    ReappraisalProfilePattern,
    ReappraisalSubType,
    RegulationDetection,
    RegulationIntervention,
    RuminationFlavor,
    Severity,
    Strategy,
    StrategyChoiceAudit,
    StrategyEvidence,
    severity_from_adaptivity,
)

__all__ = [
    # Analyzer entry points
    "ReappraisalAnalyzer",
    "ReappraisalAnalyzerAsync",
    "ReappraisalDetector",  # v0.0.x legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentRegulationTrace",
    # Schema -- output
    "StrategyEvidence",
    "ProcessModelPhaseEvidence",
    "AffectivityProfile",
    "StrategyChoiceAudit",
    "CascadeAnalysis",
    "RegulationIntervention",
    "RegulationDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "Strategy",
    "ReappraisalMode",
    "ReappraisalProfilePattern",
    "Severity",
    "ProcessModelPhase",
    "ReappraisalSubType",
    "RuminationFlavor",
    "ExtendedPhase",
    "InterventionType",
    "EffortEstimate",
    "REGULATION_STRATEGIES",
    "REAPPRAISAL_MODES",
    "REAPPRAISAL_PROFILE_PATTERNS",
    "PROCESS_MODEL_PHASES",
    "REAPPRAISAL_SUBTYPES",
    "RUMINATION_FLAVORS",
    "EXTENDED_PHASES",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_adaptivity",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "REAPPRAISAL_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "GROSS_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_STRATEGY_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_PROCESS_MODEL_PROMPT",
    "FORENSIC_STRATEGY_CHOICE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "STRATEGY_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
