"""agentcity.danva_emotion -- DANVA-style emotion-recognition accuracy
diagnostic for AI agents.

Seven canonical Ekman emotion categories: happy, sad, angry, fearful,
disgust, surprise, neutral. Plus "uncertain" inferred-fallback. The
diagnostic measures per-emotion accuracy, intensity calibration,
confusion patterns, and (forensic mode) Russell-circumplex
projection + cascade-break diagnosis.

Anchored in 12+ academic sources spanning four traditions:
categorical (Nowicki-Duke 1994, 2001; Ekman 1992, 1999; Plutchik 2001),
dimensional (Russell 1980; Mehrabian 1980; Posner-Russell-Peterson 2005),
modern LLM (GoEmotions 2020, EmotionLines 2018, EmoBank 2017, EmoBench
2024, EmotionQueen 2024, NRC-VAD 2018, WASSA-2017, Cowen-Keltner 2017),
and cross-cultural / linguistic (Matsumoto-Hwang 2018, Tausczik-Pennebaker
2010, Scherer 2005).

Three pipeline modes (mirrors patterns #01-#03):

  - ``quick`` -- one LLM call, top intervention. ~$0.005.
  - ``standard`` -- one LLM call, 2-4 ranked interventions. ~$0.015.
  - ``forensic`` -- three+ LLM calls: Russell dimensional overlay +
    cascade-break reconcile + ranked interventions with composition
    targets. ~$0.05.

Production wiring (v0.1.0 infra): structured logging with run-id
correlation, token/cost telemetry, prompt-injection input guards,
async mirror.

Composition: auto-attaches ComposedPatternHandoff based on
weakest_emotion + profile_pattern + framework + intervention shape.
12 (emotion, failure_mode) playbooks auto-attached.

Quick start
-----------

    from agentcity.danva_emotion import (
        EmotionRecognitionAnalyzer,
        AgentEmotionTrace,
        EmotionItem,
    )
    from agentcity.aar import AnthropicClient

    trace = AgentEmotionTrace(
        agent_id="support-agent",
        framework="custom",
        items=[
            EmotionItem(
                item_id="i1",
                user_input="I JUST WANT THIS FIXED!!!",
                ground_truth_emotion="angry",
                ground_truth_intensity=0.9,
                agent_inferred_emotion="neutral",
                agent_inferred_intensity=0.3,
            ),
        ],
    )
    analysis = EmotionRecognitionAnalyzer(AnthropicClient(), mode="forensic").run(trace)
    print(analysis.to_markdown())

CLI
---

    agentcity-danva analyze --trace trace.json --mode forensic
    agentcity-danva playbooks
    agentcity-danva compose
    agentcity-danva schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    DANVA_COMPOSITION,
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
    EmotionRecognitionAnalyzer,
    EmotionRecognitionAnalyzerAsync,
    LLMClient,
)
from .prompts import (
    DANVA_SYSTEM_PROMPT,
    FORENSIC_CASCADE_RECONCILE_PROMPT,
    FORENSIC_DIMENSIONAL_OVERLAY_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    DANVA_MODES,
    DANVA_PROFILE_PATTERNS,
    EMOTION_CATEGORIES,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    AgentEmotionTrace,
    AttachedPlaybook,
    BaselineComparison,
    CascadeAnalysis,
    CircumplexProjection,
    ComposedPatternHandoff,
    CueExplicitness,
    CulturalAdjustment,
    CulturalContext,
    DANVAMode,
    DANVAProfilePattern,
    EffortEstimate,
    EmotionCategory,
    EmotionConfusionMatrix,
    EmotionIntervention,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
    ExtendedEmotion,
    InferredEmotion,
    IntensityCurve,
    InterventionType,
    PerEmotionCalibration,
    Severity,
    TextCueSignature,
    severity_from_accuracy,
)

__all__ = [
    # Analyzer entry points
    "EmotionRecognitionAnalyzer",
    "EmotionRecognitionAnalyzerAsync",
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentEmotionTrace",
    "EmotionItem",
    "TextCueSignature",
    "PerEmotionCalibration",
    # Schema -- output
    "EmotionMetric",
    "EmotionConfusionMatrix",
    "IntensityCurve",
    "CircumplexProjection",
    "CulturalAdjustment",
    "CascadeAnalysis",
    "EmotionIntervention",
    "EmotionRecognitionAnalysis",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Schema -- Literal enums + constants
    "EmotionCategory",
    "InferredEmotion",
    "DANVAMode",
    "DANVAProfilePattern",
    "Severity",
    "CueExplicitness",
    "CulturalContext",
    "ExtendedEmotion",
    "InterventionType",
    "EffortEstimate",
    "EMOTION_CATEGORIES",
    "DANVA_MODES",
    "DANVA_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_accuracy",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "DANVA_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "DANVA_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_DIMENSIONAL_OVERLAY_PROMPT",
    "FORENSIC_CASCADE_RECONCILE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
