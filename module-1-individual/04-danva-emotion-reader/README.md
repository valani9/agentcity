# Pattern #04 — DANVA-Style Emotion Reader

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.danva_emotion`

Stephen Nowicki & Marshall Duke's DANVA (Diagnostic Analysis of
Nonverbal Accuracy) applied to AI agent text emotion recognition.
Per-emotion accuracy, intensity calibration, and confusion patterns —
all computed deterministically.

## The framework

Seven canonical emotion labels (Ekman basic emotions + neutral):

- **happy** / **sad** / **angry** / **fearful** / **disgust** / **surprise** / **neutral**
- (Plus `uncertain` for agent fallback)

For each batch of recognition trials, the diagnostic computes:

- **Per-emotion accuracy** — fraction correctly identified
- **Intensity MAE** — mean absolute error between inferred and true intensity
- **Confusion patterns** — which emotion does the agent pick when it gets one wrong?
- **Overall accuracy** + **weakest emotion** + **quality bucket**

Math is locked in Python; LLM only generates qualitative
interventions on top of the computed numbers.

## Agent mapping

| Emotion cue | Text signal |
| --- | --- |
| Angry | ALL-CAPS, exclamation density, terse imperatives, "JUST", "done", "fed up" |
| Sad | Past-tense loss vocabulary, "nothing works", flat affect |
| Fearful | Future tense ("what if", "might"), hedging, worry verbs |
| Happy | Exclamation positive, gratitude tokens, ":)", "amazing" |
| Surprise | "oh", "didn't expect", "wait what" |
| Disgust | Strong negative valence, dismissal vocabulary |
| Neutral | Procedural, transactional, low intensifier density |

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `EmotionRecognitionAnalyzer` (deterministic metrics + LLM interventions)
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Anger under-detection demo
- [`eval/synthetic_emotion_batches.yaml`](eval/synthetic_emotion_batches.yaml) — 4 batch scenarios
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_danva_emotion.py`](tests/test_danva_emotion.py) — pytest suite (metric correctness + pipeline)

## Quick start

```python
from agentcity.danva_emotion import (
    AgentEmotionTrace, EmotionItem, EmotionRecognitionAnalyzer,
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
    ],
)
analysis = EmotionRecognitionAnalyzer(AnthropicClient()).run(trace)
print(analysis.to_markdown())
```
