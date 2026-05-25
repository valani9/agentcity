"""vstack.process_gain_loss -- Steiner / Robbins-&-Judge process-gain
and process-loss diagnostic for multi-agent systems.

Anchored in: Steiner (1972), Hill (1982), Hackman-Vidmar (1970),
Diehl-Stroebe (1987), Salas et al. (2018), Robbins & Judge OB textbook,
Wang et al. (2023) Cooperative LLM Agents.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure.

Backward-compatible: ``ProcessGainLossDetector`` remains exported as
alias of ``ProcessGainLossAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    PROCESS_COMPOSITION,
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
    ProcessGainLossAnalyzer,
    ProcessGainLossAnalyzerAsync,
    ProcessGainLossDetector,
)
from .prompts import (
    FACTOR_PROMPT,
    FORENSIC_COUNTERFACTUAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_LOG_AUDIT_PROMPT,
    INTERVENTIONS_PROMPT,
    PROCESS_GAIN_LOSS_SYSTEM_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_FACTORS_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    PROCESS_FACTORS,
    PROCESS_MODES,
    PROCESS_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CounterfactualAudit,
    EffortEstimate,
    IndividualBaseline,
    InteractionLogAudit,
    InterventionType,
    ProcessFactor,
    ProcessFactorEvidence,
    ProcessFactorOrTeamDesign,
    ProcessGainLossDetection,
    ProcessGainLossMode,
    ProcessIntervention,
    ProcessProfilePattern,
    ProcessTrace,
    Severity,
    TeamResult,
    severity_from_loss,
)

__all__ = [
    "ProcessGainLossAnalyzer",
    "ProcessGainLossAnalyzerAsync",
    "ProcessGainLossDetector",
    "LLMClient",
    "AsyncLLMClient",
    "ProcessTrace",
    "IndividualBaseline",
    "TeamResult",
    "ProcessFactorEvidence",
    "InteractionLogAudit",
    "CounterfactualAudit",
    "ProcessIntervention",
    "ProcessGainLossDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    "ProcessFactor",
    "ProcessFactorOrTeamDesign",
    "ProcessGainLossMode",
    "ProcessProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "PROCESS_FACTORS",
    "PROCESS_MODES",
    "PROCESS_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_loss",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "PROCESS_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "PROCESS_GAIN_LOSS_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_FACTORS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_LOG_AUDIT_PROMPT",
    "FORENSIC_COUNTERFACTUAL_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FACTOR_PROMPT",
    "INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
