# DANVA Emotion Reader — per-emotion accuracy with confusion matrices

*#04 vstack_danva_emotion* · *Module 1 — Individual agent*

> A customer-facing agent shipped a new system prompt on Monday. CSAT dropped four points by Friday. The team had aggregate sentiment metrics, scattered user complaints, and no objective measure of whether the regression was an emotion-recognition issue, a response-style issue, or a content issue. The CSAT decline was real but blind. By the time someone pulled the eval traces by hand, they noticed the new prompt had made the agent read all-caps utterances as "neutral" — the anger detector had quietly degraded. There was no per-emotion accuracy number per deploy; nobody had thought to track one.

## What the pattern catches

The pattern catches **per-emotion recognition failures** in user-facing agents — the upstream half of emotional intelligence, before any response is composed. The most common production failure isn't that the agent can't generate empathy; it's that the agent never registered the emotion in the first place.

vstack_danva_emotion computes, per emotion:

- **Accuracy** — fraction correctly identified vs ground truth.
- **Intensity MAE** — mean absolute error between inferred and ground-truth intensity (0..1).
- **Confusion partners** — when wrong, which alternative did the agent pick?
- **Profile pattern** — one of 14, including `anger_blind`, `sadness_collapse`, `positive_bias`, `sarcasm_blind`, `fear_sadness_confusion`, `valence_only_signal`.

All three core metrics are deterministic. The library doesn't ask an LLM to score the numbers — it computes them in Python from the labeled batch. The LLM is involved only in intervention generation on top of locked numbers.

## Why the OB literature is the right reference

The diagnostic is anchored in Nowicki & Duke 1994/2001 (the DANVA/DANVA2 standardized batteries for nonverbal emotion-recognition accuracy), with Ekman 1992/1999 (basic emotions), Plutchik 2001 (wheel), Russell 1980 (circumplex), Posner-Russell-Peterson 2005 (reconciliation), Mehrabian 1980 PAD, Scherer 2005, Matsumoto-Hwang 2018, Mohammad 2018 NRC-VAD, GoEmotions (Demszky 2020), EmoBench (Sabour 2024), EmotionQueen (Wang 2024), and WASSA-2017 (intensity calibration).

**Nowicki and Duke's 1994 insight** was operational: pick a fixed canon of categories, build a labeled stimulus battery, compute per-emotion accuracy and confusion matrices — and the per-emotion numbers predict downstream social outcomes better than any aggregate "social intelligence" score. The same operationalization works for agents because text-emotion is just another modality. Per-emotion accuracy is a number you can track per-deploy; aggregate "EQ" is not.

## How the analyzer works

Input is `AgentEmotionTrace` — agent_id, framework, `items` (each with `user_input`, `ground_truth_emotion`, `ground_truth_intensity`, `agent_inferred_emotion`, `agent_inferred_intensity`). The pipeline:

- **quick** — one LLM call. Per-emotion summary + top intervention.
- **standard** — one LLM call (skipped on already-high accuracy). Per-emotion evidence + ranked interventions.
- **forensic** — three LLM calls. Adds Russell circumplex projection (valence × arousal quadrant), Joseph-Newman-style cascade (perceive_cue → categorize → intensity → respond), and Plutchik-wheel confusion-partner analysis.

```python
from vstack.danva_emotion import EmotionRecognitionAnalyzer, AgentEmotionTrace, EmotionItem
analysis = EmotionRecognitionAnalyzer(llm, mode="forensic").run(AgentEmotionTrace(
    agent_id="support-agent", framework="custom",
    items=[EmotionItem(
        item_id="i1",
        user_input="I JUST WANT THIS FIXED!!!",
        ground_truth_emotion="angry",
        ground_truth_intensity=0.9,
        agent_inferred_emotion="neutral",
        agent_inferred_intensity=0.3,
    )],
))
print(analysis.profile_pattern)             # 'anger_blind'
print(analysis.per_emotion["angry"].accuracy)  # deterministic; locked
```

The diagnostic earns its keep on **intensity collapse** — agents that get the category right but systematically under-read intensity. WASSA-2017 anchored this pattern in the human-recognition literature; the DANVA analyzer surfaces it with a per-emotion intensity MAE.

## What the playbooks say to do

12 playbooks keyed by `(emotion, failure_mode)`:

- `(angry, under_detection)` → "Add a cue inventory in the system prompt: ALL-CAPS spans, exclamation density, terse imperatives, intensifier words. Force agent to enumerate cues before classifying." Anchored to Ekman 1992 cue taxonomy.
- `(angry, intensity_collapse)` → "Force explicit intensity rating on a 1-5 anchored scale before generating response." Anchored to WASSA-2017.
- `(fearful, mis_as_sad)` → "Future-vs-past tense disambiguation rule. Fear is anticipatory; sadness is retrospective." Anchored to Plutchik 2001.
- `(happy, sarcasm_blind)` → "Sarcasm signature detection: positive lexical content + negative punctuation pattern or exaggeration." Anchored to EmotionQueen (Wang 2024).
- `(all, uncertain_dump)` → "Force categorical commit. The agent must pick one primary emotion before adding qualifiers." Anchored to Russell 1980.

Each intervention is a system-prompt addition. None require retraining.

## How it composes with adjacent patterns

DANVA is the **per-emotion drill-down** when Goleman EI surfaces `social_awareness` as the weakest domain. It also runs upstream as a regression gate — sit it in CI, catch emotion-recognition drift before any user-facing deploy.

Per-profile downstream:
- `anger_blind` → `vstack_glaser_conversation` (the phrasing pass that turns recognition into response).
- `sadness_collapse` → `vstack_cognitive_reappraisal`, `vstack_yerkes_dodson`.
- `positive_bias` → `vstack_glaser_conversation`, `vstack_johari` (sycophancy proxy — agent reads everything as happy because it's been tuned to agree).
- `sarcasm_blind` → `vstack_glaser_conversation`, `vstack_hexaco`.

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer) for the wider stack.

## Comparison to adjacent tools

- **EmoBench / EQ-Bench** measure aggregate emotional understanding; DANVA gives you per-emotion accuracy + confusion matrix.
- **vstack_goleman_ei** scores the 2x2 quadrants at the competency level; DANVA scores the recognition accuracy *inside* the social-awareness quadrant.
- **vstack_glaser_conversation** scores phrasing patterns at the word level; DANVA scores upstream recognition before any phrasing.
- **Generic LLM judges** ("did the agent get the emotion right?") give a non-deterministic score. DANVA gives a deterministic accuracy number you can compare across models.

## Paper outline

1. **Background** — Nowicki-Duke 1994, Ekman 1992, Plutchik 2001, Russell 1980, WASSA-2017.
2. **Translation** — text as another DANVA modality; per-emotion accuracy as the diagnostically primary metric.
3. **Method** — deterministic per-emotion accuracy + intensity MAE + confusion matrix + Russell circumplex projection.
4. **Evaluation** — GoEmotions-derived eval batches + EmotionQueen + WASSA intensity benchmark.
5. **Limitations** — needs labeled ground truth; cross-cultural emotion expression isn't fully captured.
6. **Related work** — EmoBench (Sabour 2024), EQ-Bench (Paech 2023), GoEmotions (Demszky 2020).
7. **Future work** — automated ground-truth generation; cross-model regression dashboards.

## Citations

- Nowicki, S., & Duke, M. P. (1994). Individual differences in the nonverbal communication of affect: The DANVA.
- Ekman, P. (1992). An argument for basic emotions.
- Plutchik, R. (2001). The nature of emotions.
- Russell, J. A. (1980). A circumplex model of affect.
- Mohammad, S. M. (2018). Obtaining reliable human ratings of valence, arousal, and dominance (NRC-VAD).
- Sabour, S. et al. (2024). EmoBench: Evaluating the emotional intelligence of large language models.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-danva analyze --trace examples/caps_anger_batch.json --mode forensic
```

If `profile_pattern` is `anger_blind`, run `vstack_glaser_conversation` next — the cue inventory you add upstream needs a downstream response-phrasing audit to land.
