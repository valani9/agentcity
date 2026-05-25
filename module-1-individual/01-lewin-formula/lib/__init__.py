"""vstack.lewin — Kurt Lewin's behavior formula B = f(P, E) applied
to AI agent failure attribution.

When an agent fails, the cause is either INTERNAL (P) (model: training,
capability, RLHF, sampling, version), ENVIRONMENTAL (E) (scaffolding:
prompt, tools, context, orchestration, verification), or
INTERACTIONAL (both swapped — neither alone fixes it). Most teams
default to "fix the model"; Lewin's diagnostic redirects effort to the
right locus, drawing on the full attribution-theory literature thread
(Heider 1958, Kelley 1967, Ross 1977, Gilbert & Malone 1995) and the
person-situation debate's modern resolution (Mischel & Shoda 1995
CAPS; Funder & Ozer 1983 symmetry; Bandura 1986 reciprocal
determinism).

The diagnostic ships three pipeline modes:

  - ``quick`` — one LLM call, scoring + top intervention; CI / live ops.
  - ``standard`` — two LLM calls, full scoring + ranked interventions.
  - ``forensic`` — four LLM calls, Kelley covariance reasoning +
    counterfactual swap analysis + Gilbert-Malone bias-mechanism
    diagnosis + 4-8 ranked interventions with composition targets.

Production wiring (v0.1.0 infra):

  - Structured logging with run-id correlation (every log line carries
    ``run_id`` + ``pattern="lewin"``).
  - Token / cost telemetry via :func:`vstack.aar.record_llm_call`.
  - Prompt-injection input guards on every free-text field.
  - Async mirror :class:`LewinAttributionDetectorAsync` for parallel
    pattern fan-out under server traffic.

Composition:

  - The pattern auto-attaches a :class:`ComposedPatternHandoff` to
    every detection naming the next vstack pattern(s) to run.
  - Playbooks for common (locus, factor) failure modes are auto-attached.

Quick start
-----------

    from vstack.lewin import (
        LewinAttributionDetector,
        AgentFailureTrace,
        FailureStep,
        CovarianceSignal,
    )
    from vstack.aar import AnthropicClient

    trace = AgentFailureTrace(
        agent_id="qa-bot-001",
        model_name="claude-opus-4-7",
        task="Answer 'When was Pluto reclassified?'",
        steps=[
            FailureStep(type="input", content="When was Pluto reclassified?"),
            FailureStep(type="tool_call", content="rag.search(query=...)"),
            FailureStep(type="observation", content="returned a 2003 Wikipedia revision"),
            FailureStep(type="output", content="Pluto was reclassified in 2003."),
        ],
        outcome="Confidently wrong year.",
        success=False,
        initial_attribution="model is bad at facts",
        covariance_signal=CovarianceSignal(
            consensus="high",
            distinctiveness="high",
            consistency="high",
        ),
    )
    detection = LewinAttributionDetector(AnthropicClient(), mode="forensic").run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-lewin analyze --trace trace.json --mode forensic
    vstack-lewin playbooks
    vstack-lewin compose
    vstack-lewin schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    LEWIN_COMPOSITION,
    recommended_downstream,
    recommended_upstream,
)
from ._playbooks import PLAYBOOKS, all_playbook_keys, find_playbook
from .generator import (
    AsyncLLMClient,
    LewinAttributionDetector,
    LewinAttributionDetectorAsync,
    LLMClient,
)
from .prompts import (
    BIAS_MECHANISM_PROMPT,
    COUNTERFACTUAL_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_LOCUS_SCORING_PROMPT,
    INTERVENTIONS_PROMPT,
    LEWIN_SYSTEM_PROMPT,
    LOCUS_SCORING_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_LOCUS_SCORING_PROMPT,
    assemble_prompt,
)
from .schema import (
    ENVIRONMENTAL_FACTOR_NAMES,
    INDIVIDUAL_FACTOR_NAMES,
    INTERVENTION_TYPES,
    LEWIN_MODES,
    LOCI,
    LOCI_WITH_INDETERMINATE,
    SEVERITY_ORDER,
    AgentFailureTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CovarianceSignal,
    EffortEstimate,
    EnvironmentalFactor,
    EnvironmentalFactorName,
    FailureStep,
    GilbertMaloneMechanism,
    IndividualFactor,
    IndividualFactorName,
    InterventionType,
    LewinDetection,
    LewinIntervention,
    LewinMode,
    LocusEvidence,
    Severity,
    severity_from_score,
)

__all__ = [
    # Detector entry points
    "LewinAttributionDetector",
    "LewinAttributionDetectorAsync",
    "LLMClient",
    "AsyncLLMClient",
    # Schema — input
    "AgentFailureTrace",
    "FailureStep",
    "IndividualFactor",
    "EnvironmentalFactor",
    "CovarianceSignal",
    # Schema — output
    "LocusEvidence",
    "LewinIntervention",
    "LewinDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Schema — Literal enums + constants
    "LewinMode",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "IndividualFactorName",
    "EnvironmentalFactorName",
    "GilbertMaloneMechanism",
    "LOCI",
    "LOCI_WITH_INDETERMINATE",
    "LEWIN_MODES",
    "SEVERITY_ORDER",
    "INDIVIDUAL_FACTOR_NAMES",
    "ENVIRONMENTAL_FACTOR_NAMES",
    "INTERVENTION_TYPES",
    "severity_from_score",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "LEWIN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    # Prompts (re-exported for prompt-engineering work)
    "LEWIN_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_LOCUS_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_LOCUS_SCORING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "COUNTERFACTUAL_PROMPT",
    "BIAS_MECHANISM_PROMPT",
    "LOCUS_SCORING_PROMPT",  # legacy alias
    "INTERVENTIONS_PROMPT",  # legacy alias
    "assemble_prompt",
]

__version__ = "0.2.0"
