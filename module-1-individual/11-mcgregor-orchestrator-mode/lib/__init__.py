"""agentcity.mcgregor -- Douglas McGregor's Theory X / Theory Y
framework applied to orchestrator-agent oversight design.

Anchored in:
  - McGregor (1960) *The Human Side of Enterprise*.
  - McGregor (1966) *Leadership and Motivation*.
  - Schein (1990) *Organizational Culture and Leadership*.
  - Pfeffer & Salancik (1978) *External Control of Organizations*.
  - Argyris (1957) *Personality and Organization*.
  - Eisenhardt (1989) agency theory.
  - Wang et al. (2023) cooperative LLM agents + modern orchestration.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure.

Backward-compatible: ``OrchestratorModeDetector`` remains exported as
an alias for ``McGregorOrchestratorAnalyzer``.

Quick start
-----------

    from agentcity.mcgregor import (
        McGregorOrchestratorAnalyzer,
        OrchestratorTrace,
        OrchestratorStep,
        TaskProperties,
    )
    from agentcity.aar import AnthropicClient

    trace = OrchestratorTrace(
        trace_id="ci-runner-001",
        task="Run the test suite on every PR and report results.",
        sub_agents=["runner-1"],
        task_properties=TaskProperties(
            risk_level="low",
            complexity="routine",
            reversibility="reversible",
            agent_capability="proven",
        ),
        steps=[OrchestratorStep(step_type="delegate", actor="orchestrator", content="run tests")],
        outcome="Each test run required pre-approval; 5x slower than needed.",
        success=True,
    )
    detection = McGregorOrchestratorAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    agentcity-mcgregor analyze --trace trace.json --mode forensic
    agentcity-mcgregor playbooks
    agentcity-mcgregor compose
    agentcity-mcgregor schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    MCGREGOR_COMPOSITION,
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
    McGregorOrchestratorAnalyzer,
    McGregorOrchestratorAnalyzerAsync,
    OrchestratorModeDetector,  # legacy alias
)
from .prompts import (
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_OPTIMALITY_PROMPT,
    FORENSIC_STEP_AUDIT_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy
    MCGREGOR_SYSTEM_PROMPT,
    MODE_PROMPT,  # legacy
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_MODE_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    MCGREGOR_MODES,
    MCGREGOR_PROFILE_PATTERNS,
    MODES,
    SEVERITY_ORDER,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    InterventionType,
    McGregorMode,
    McGregorProfilePattern,
    ModeIndicators,
    OptimalityJustification,
    OrchestratorIntervention,
    OrchestratorMode,
    OrchestratorModeDetection,
    OrchestratorStep,
    OrchestratorTrace,
    Severity,
    StepAudit,
    TaskProperties,
    severity_from_mismatch,
)

__all__ = [
    # Analyzer entry points
    "McGregorOrchestratorAnalyzer",
    "McGregorOrchestratorAnalyzerAsync",
    "OrchestratorModeDetector",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "OrchestratorTrace",
    "OrchestratorStep",
    "TaskProperties",
    # Schema -- output
    "ModeIndicators",
    "StepAudit",
    "OptimalityJustification",
    "OrchestratorIntervention",
    "OrchestratorModeDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "OrchestratorMode",
    "McGregorMode",
    "McGregorProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "MODES",
    "MCGREGOR_MODES",
    "MCGREGOR_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_mismatch",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "MCGREGOR_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "MCGREGOR_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_MODE_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_STEP_AUDIT_PROMPT",
    "FORENSIC_OPTIMALITY_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "MODE_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
