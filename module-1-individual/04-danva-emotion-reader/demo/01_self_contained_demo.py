"""Self-contained demo of the DANVA-style Emotion Reader Diagnostic.

Synthetic scenario: a support agent processes 10 user messages with
known ground-truth emotions. The agent under-detects 'angry' and
'fearful' (reading them as 'neutral'), but reads 'happy' and 'sad'
correctly. Classic intensity-collapse + anger-under-detection pattern.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.danva_emotion import (
        AgentEmotionTrace,
        EmotionItem,
        EmotionRecognitionAnalyzer,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentEmotionTrace:
    items = [
        EmotionItem(
            item_id="i01",
            user_input="I JUST WANT THIS FIXED!!!",
            ground_truth_emotion="angry",
            ground_truth_intensity=0.9,
            agent_inferred_emotion="neutral",
            agent_inferred_intensity=0.3,
        ),
        EmotionItem(
            item_id="i02",
            user_input="why is this so hard. i'm done.",
            ground_truth_emotion="angry",
            ground_truth_intensity=0.7,
            agent_inferred_emotion="neutral",
            agent_inferred_intensity=0.4,
        ),
        EmotionItem(
            item_id="i03",
            user_input="Thanks so much, this is amazing!",
            ground_truth_emotion="happy",
            ground_truth_intensity=0.85,
            agent_inferred_emotion="happy",
            agent_inferred_intensity=0.8,
        ),
        EmotionItem(
            item_id="i04",
            user_input="great, perfect, you've made my day :)",
            ground_truth_emotion="happy",
            ground_truth_intensity=0.8,
            agent_inferred_emotion="happy",
            agent_inferred_intensity=0.75,
        ),
        EmotionItem(
            item_id="i05",
            user_input="i don't know what to do anymore. i give up.",
            ground_truth_emotion="sad",
            ground_truth_intensity=0.85,
            agent_inferred_emotion="sad",
            agent_inferred_intensity=0.7,
        ),
        EmotionItem(
            item_id="i06",
            user_input="this is the third time today. nothing works.",
            ground_truth_emotion="sad",
            ground_truth_intensity=0.7,
            agent_inferred_emotion="sad",
            agent_inferred_intensity=0.6,
        ),
        EmotionItem(
            item_id="i07",
            user_input="what if this breaks production? i'm worried.",
            ground_truth_emotion="fearful",
            ground_truth_intensity=0.75,
            agent_inferred_emotion="neutral",
            agent_inferred_intensity=0.4,
        ),
        EmotionItem(
            item_id="i08",
            user_input="i don't want to deploy this, something feels off",
            ground_truth_emotion="fearful",
            ground_truth_intensity=0.65,
            agent_inferred_emotion="sad",
            agent_inferred_intensity=0.5,
        ),
        EmotionItem(
            item_id="i09",
            user_input="oh nice, didn't expect that to work!",
            ground_truth_emotion="surprise",
            ground_truth_intensity=0.6,
            agent_inferred_emotion="happy",
            agent_inferred_intensity=0.7,
        ),
        EmotionItem(
            item_id="i10",
            user_input="please check the status of order 12345.",
            ground_truth_emotion="neutral",
            ground_truth_intensity=0.1,
            agent_inferred_emotion="neutral",
            agent_inferred_intensity=0.1,
        ),
    ]
    return AgentEmotionTrace(
        agent_id="demo-support-agent",
        model_name="demo-stub",
        items=items,
    )


def stub_responses() -> list[str]:
    interventions = json.dumps(
        [
            {
                "target_emotion": "angry",
                "intervention_type": "add_cue_inventory",
                "description": (
                    "Add a system-prompt section that names specific anger cues "
                    "in text: ALL-CAPS spans, exclamation density, terse imperative "
                    "verbs, 'JUST', 'done', 'over it'."
                ),
                "suggested_implementation": (
                    "Append to system prompt: 'Anger cues in text: ALL-CAPS, "
                    "exclamation density >2, terse sentences, words like JUST / "
                    "done / over it / fed up. When you see >=2 of these, infer "
                    "anger with intensity 0.7+.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Anger is the weakest emotion (0% accuracy in the batch). "
                    "Cue-inventory closes the gap by making implicit signals explicit."
                ),
            },
            {
                "target_emotion": "fearful",
                "intervention_type": "add_confusion_clarification",
                "description": (
                    "Distinguish fearful from sad and neutral. Fearful = "
                    "future-oriented worry; sad = past-oriented loss."
                ),
                "suggested_implementation": (
                    "Append: 'Fear cues: future tense (what if, might, could), "
                    "hedging (something feels off, not sure), worry verbs. "
                    "Distinguish from sad (loss-focused, past tense).'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Fear is misread as neutral and sad. The confusion is "
                    "diagnosable and the clarification is one prompt addition."
                ),
            },
            {
                "target_emotion": "all",
                "intervention_type": "add_intensity_calibration_step",
                "description": ("Force explicit intensity rating before responding."),
                "suggested_implementation": (
                    "Append: 'Before responding, output: <emotion> at intensity "
                    "<0.0-1.0>. Calibrate intensity from cue density.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Intensity MAE is non-trivial. Forcing explicit rating "
                    "reduces intensity-collapse failures."
                ),
            },
        ]
    )
    return [interventions]


def pick_client() -> object:
    choice = os.environ.get("AGENTCITY_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_responses())


def main() -> None:
    trace = build_trace()
    client = pick_client()
    analyzer = EmotionRecognitionAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    analysis = analyzer.run(trace)
    print(analysis.to_markdown())


if __name__ == "__main__":
    main()
