"""agentcity.danva_emotion — DANVA-style emotion-recognition accuracy
diagnostic for AI agents (Nowicki & Duke, 1994).

Seven canonical emotion categories: happy, sad, angry, fearful, disgust,
surprise, neutral. The diagnostic measures per-emotion accuracy,
intensity calibration, and confusion patterns on a batch of recognition
trials.

Metrics computed DETERMINISTICALLY in Python; LLM contributes only
qualitative intervention recommendations.

Quick start:

    from agentcity.danva_emotion import (
        EmotionRecognitionAnalyzer,
        AgentEmotionTrace,
        EmotionItem,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentEmotionTrace(
        agent_id="support-agent",
        items=[
            EmotionItem(
                item_id="i1",
                user_input="I JUST WANT THIS FIXED!!!",
                ground_truth_emotion="angry",
                ground_truth_intensity=0.9,
                agent_inferred_emotion="neutral",
                agent_inferred_intensity=0.3,
            ),
            EmotionItem(
                item_id="i2",
                user_input="Thanks so much, this is amazing!",
                ground_truth_emotion="happy",
                ground_truth_intensity=0.85,
                agent_inferred_emotion="happy",
                agent_inferred_intensity=0.8,
            ),
        ],
    )
    analysis = EmotionRecognitionAnalyzer(AnthropicClient()).run(trace)
    print(analysis.to_markdown())
"""

from .generator import EmotionRecognitionAnalyzer, LLMClient
from .schema import (
    EMOTION_CATEGORIES,
    AgentEmotionTrace,
    EmotionIntervention,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
)

__all__ = [
    "EmotionRecognitionAnalyzer",
    "LLMClient",
    "AgentEmotionTrace",
    "EmotionItem",
    "EmotionMetric",
    "EmotionIntervention",
    "EmotionRecognitionAnalysis",
    "EMOTION_CATEGORIES",
]

__version__ = "0.0.14"
