"""agentcity.thomas_kilmann — Thomas-Kilmann's five conflict styles
applied to AI agent interactions."""

from .generator import ConflictStyleSelector, LLMClient
from .schema import (
    STYLES,
    AgentInteractionTrace,
    ConflictStyleSelection,
    InteractionTurn,
    StyleRecommendation,
    StyleScore,
)

__all__ = [
    "ConflictStyleSelector",
    "LLMClient",
    "AgentInteractionTrace",
    "InteractionTurn",
    "StyleScore",
    "StyleRecommendation",
    "ConflictStyleSelection",
    "STYLES",
]

__version__ = "0.0.5"
