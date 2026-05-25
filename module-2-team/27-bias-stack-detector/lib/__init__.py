"""vstack.bias_stack -- Kahneman/Tversky's four classic cognitive biases
(anchoring, overconfidence, confirmation, escalation-of-commitment)
applied to AI agent reasoning traces.

Anchored in Tversky & Kahneman 1974, Kahneman 2011, Nickerson 1998
confirmation bias, Staw 1976 escalation-of-commitment.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``BiasStackDetector`` aliased to ``BiasStackAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    BIAS_STACK_COMPOSITION,
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
    BiasStackAnalyzer,
    BiasStackAnalyzerAsync,
    BiasStackDetector,
    LLMClient,
)
from .prompts import (
    BIAS_SCORING_PROMPT,
    BIAS_SYSTEM_PROMPT,
    FORENSIC_ANCHORING_PROMPT,
    FORENSIC_CALIBRATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_BIAS_SCORING_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    BIAS_STACK_MODES,
    BIAS_STACK_PROFILE_PATTERNS,
    BIASES,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    AgentReasoningTrace,
    AnchoringTraceAudit,
    AttachedPlaybook,
    BaselineComparison,
    BiasEvidence,
    BiasIntervention,
    BiasStackDetection,
    BiasStackMode,
    BiasStackProfilePattern,
    ComposedPatternHandoff,
    ConfidenceCalibrationAudit,
    EffortEstimate,
    InterventionType,
    ReasoningStep,
    Severity,
    severity_from_bias,
)

__all__ = [
    "BiasStackAnalyzer",
    "BiasStackAnalyzerAsync",
    "BiasStackDetector",
    "LLMClient",
    "AsyncLLMClient",
    "ReasoningStep",
    "AgentReasoningTrace",
    "BiasEvidence",
    "ConfidenceCalibrationAudit",
    "AnchoringTraceAudit",
    "BiasIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "BiasStackDetection",
    "BiasStackMode",
    "BiasStackProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "BIASES",
    "BIAS_STACK_MODES",
    "BIAS_STACK_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_bias",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "BIAS_STACK_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "BIAS_SYSTEM_PROMPT",
    "BIAS_SCORING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_BIAS_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_CALIBRATION_PROMPT",
    "FORENSIC_ANCHORING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
