"""agentcity.johari -- Luft & Ingham's Johari Window applied to AI agent
self-awareness.

Four quadrants: OPEN / BLIND / HIDDEN / UNKNOWN. The diagnostic reads
an agent's trace + self-report and classifies content into quadrants,
identifies dominant blind spots, and proposes interventions to grow
the OPEN arena (via Luft's two mechanisms: disclosure for HIDDEN ->
OPEN; feedback for BLIND -> OPEN).

Three pipeline modes:

  - ``quick`` -- one LLM call, scoring + top intervention; CI / live ops.
  - ``standard`` -- two LLM calls, full scoring + ranked interventions.
  - ``forensic`` -- 5 LLM calls: forensic-quadrants + feedback opportunities
    + disclosure opportunities + Stone-Heen mechanism diagnosis + ranked
    interventions with composition targets.

Production wiring (v0.1.0 infra):

  - Structured logging with run-id correlation (every log line carries
    ``run_id`` + ``pattern="johari"``).
  - Token / cost telemetry via :func:`agentcity.aar.record_llm_call`.
  - Prompt-injection input guards on every free-text field.
  - Async mirror :class:`JohariSelfAuditorAsync`.
  - Tool-receipt deterministic cross-reference (Basu et al. 2026).
  - Kadavath introspection ceiling check.

Composition:

  - Auto-attaches a :class:`ComposedPatternHandoff` based on
    dominant_quadrant + profile_pattern + framework + intervention shape.
  - Playbooks for 12 (quadrant, failure_mode) combinations are
    auto-attached.

Quick start
-----------

    from agentcity.johari import (
        JohariSelfAuditor,
        AgentSelfReportTrace,
        InteractionTurn,
        ToolReceipt,
    )
    from agentcity.aar import AnthropicClient

    trace = AgentSelfReportTrace(
        agent_id="research-agent-007",
        model_name="claude-opus-4-7",
        task="Research the latest cancer immunotherapy clinical trials.",
        turns=[
            InteractionTurn(role="user", content="Find recent trials."),
            InteractionTurn(role="thought", content="I'll search PubMed."),
            InteractionTurn(role="tool", content="pubmed.search('immunotherapy')"),
            InteractionTurn(role="agent", content="I searched 3 databases and found 4 candidates."),
        ],
        self_report="I searched 3 databases comprehensively and found 4 high-quality candidates.",
        outcome="User found discrepancy: agent only actually searched 1 database.",
        success=False,
        tool_receipts=[ToolReceipt(tool_name="pubmed.search")],
    )
    audit = JohariSelfAuditor(AnthropicClient(), mode="forensic").run(trace)
    print(audit.to_markdown())

CLI
---

    agentcity-johari analyze --trace trace.json --mode forensic
    agentcity-johari playbooks
    agentcity-johari compose
    agentcity-johari schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    JOHARI_COMPOSITION,
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
    JohariSelfAuditor,
    JohariSelfAuditorAsync,
    LLMClient,
)
from .prompts import (
    CAPABILITY_PROBE_PROMPT,
    FORENSIC_BLIND_MECHANISM_PROMPT,
    FORENSIC_DISCLOSURE_OPPORTUNITY_PROMPT,
    FORENSIC_FEEDBACK_OPPORTUNITY_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_QUADRANT_ANALYSIS_PROMPT,
    INTERVENTIONS_PROMPT,
    JOHARI_SYSTEM_PROMPT,
    QUADRANT_ANALYSIS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_QUADRANT_ANALYSIS_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    JOHARI_MODES,
    JOHARI_PROFILE_PATTERNS,
    QUADRANTS,
    QUADRANTS_WITH_INDETERMINATE,
    SEVERITY_ORDER,
    AgentSelfReportTrace,
    AttachedPlaybook,
    BaselineComparison,
    BlindSpotMechanism,
    CapabilityProbe,
    ComposedPatternHandoff,
    DisclosureOpportunity,
    EffortEstimate,
    FeedbackOpportunity,
    HiddenContentMode,
    InteractionTurn,
    InterventionType,
    JohariIntervention,
    JohariMode,
    JohariProfilePattern,
    JohariSelfAudit,
    Quadrant,
    QuadrantContent,
    QuadrantSizeMetrics,
    Severity,
    ToolReceipt,
    severity_from_self_awareness,
)

__all__ = [
    # Detector entry points
    "JohariSelfAuditor",
    "JohariSelfAuditorAsync",
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentSelfReportTrace",
    "InteractionTurn",
    "ToolReceipt",
    # Schema -- output
    "QuadrantContent",
    "QuadrantSizeMetrics",
    "FeedbackOpportunity",
    "DisclosureOpportunity",
    "CapabilityProbe",
    "JohariIntervention",
    "JohariSelfAudit",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Schema -- Literal enums + constants
    "Quadrant",
    "JohariMode",
    "JohariProfilePattern",
    "Severity",
    "BlindSpotMechanism",
    "HiddenContentMode",
    "InterventionType",
    "EffortEstimate",
    "QUADRANTS",
    "QUADRANTS_WITH_INDETERMINATE",
    "JOHARI_MODES",
    "JOHARI_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_self_awareness",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "JOHARI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "JOHARI_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_QUADRANT_ANALYSIS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_QUADRANT_ANALYSIS_PROMPT",
    "FORENSIC_FEEDBACK_OPPORTUNITY_PROMPT",
    "FORENSIC_DISCLOSURE_OPPORTUNITY_PROMPT",
    "FORENSIC_BLIND_MECHANISM_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "CAPABILITY_PROBE_PROMPT",
    "QUADRANT_ANALYSIS_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
