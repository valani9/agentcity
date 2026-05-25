# Pattern #04 — DANVA-Style Emotion Reader

**Status:** shipped — v0.2.0 (gstack-grade upgrade).
**Module:** 1 (Individual) — emotion-recognition accuracy for AI agents.
**Anchor framework:** Nowicki & Duke 1994, 2001 (DANVA/DANVA2) per-emotion accuracy + confusion-matrix methodology, with Ekman 1992/1999 basic emotions, Plutchik 2001 wheel, Russell 1980 circumplex, Mehrabian 1980 PAD, Posner-Russell-Peterson 2005 reconciliation, Mohammad 2018 NRC-VAD, GoEmotions Demszky 2020, EmoBench Sabour 2024, EmotionQueen Wang 2024, WASSA-2017, Matsumoto-Hwang 2018, Tausczik-Pennebaker 2010, Scherer 2005.

> Full literature thread (14+ sources) with per-citation usage notes:
> [`lib/CITATIONS.md`](lib/CITATIONS.md).

---

## TL;DR -- what this pattern does

For each emotion the user expressed in a batch of agent interactions,
this diagnostic computes: per-emotion accuracy + intensity calibration
+ confusion patterns + (forensic mode) Russell-circumplex valence/arousal
projection + cascade-break diagnosis (perceive_cue -> categorize ->
intensity -> respond).

Outputs:

  - Per-emotion accuracy + intensity MAE + intensity bias + confusion
    matrix.
  - **Profile pattern** -- one of 14: `balanced_high/developing/low`,
    `anger_blind`, `sadness_collapse`, `positive_bias`, `negative_bias`,
    `valence_only_signal`, `categorical_signal_only`,
    `fear_sadness_confusion`, `neutral_collapse`, `uncertain_dump`,
    `sarcasm_blind`, `indeterminate`.
  - Russell circumplex projection (valence x arousal quadrant).
  - **Cascade analysis** (forensic) -- earliest stage where competence
    drops.
  - Ranked interventions with effort/risk/reversibility/composition target.
  - Composition handoffs to #02 Goleman EI, #05 Cognitive Reappraisal,
    #21 Glaser, #07 HEXACO.
  - 12 (emotion, failure_mode) playbooks auto-attached.
  - Baseline drift detection.

> The single thing this diagnostic earns its keep on: catching
> **intensity collapse** -- agents that get the category right but
> systematically under-read the intensity (sadness_collapse pattern;
> WASSA-2017 anchor).

---

## Install

```bash
pip install vstack
pip install "vstack[anthropic]"
pip install "vstack[openai]"
pip install "vstack[ollama]"
```

---

## Three pipeline modes

| Mode | LLM calls | Latency | Cost | When to use |
|---|---|---|---|---|
| `quick` | 1 | < 2s | < $0.005 | CI gates |
| `standard` | 1 (skipped if high-accuracy) | < 5s | < $0.015 | Default postmortems |
| `forensic` | 3 | < 15s | < $0.05 | Deep dives with circumplex + cascade |

---

## Python quick start

```python
from vstack.danva_emotion import (
    EmotionRecognitionAnalyzer,
    AgentEmotionTrace,
    EmotionItem,
)
from vstack.aar import AnthropicClient

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
```

---

## CLI

```bash
vstack-danva analyze --trace trace.json --client stub --stub-responses stub.json
vstack-danva analyze --trace fail.json --client anthropic --mode forensic
vstack-danva batch --corpus eval/synthetic_emotion_batches.yaml --out analyses/
vstack-danva replay --analysis analyses/scenario-1.json
vstack-danva playbooks
vstack-danva compose
vstack-danva schema --target trace
```

---

## Composition

**Upstream:** goleman_ei (social_awareness weakest -> DANVA), aar, yerkes_dodson, lewin.

**Per-profile-pattern downstream:**
  - `anger_blind` -> glaser_conversation, cognitive_reappraisal.
  - `sadness_collapse` -> cognitive_reappraisal, yerkes_dodson.
  - `positive_bias` -> glaser_conversation, johari (sycophancy proxy).
  - `sarcasm_blind` -> glaser_conversation, hexaco.
  - `balanced_low` -> lewin, aar.

**Per-weakest-emotion downstream:**
  - angry -> glaser_conversation.
  - fearful / sad -> cognitive_reappraisal.
  - neutral -> goleman_ei.

---

## 12 failure-mode playbooks

  - (angry, under_detection) — caps + exclamation cue inventory.
  - (angry, intensity_collapse) — force explicit intensity rating.
  - (fearful, mis_as_sad) — future-vs-past tense disambiguation.
  - (fearful, mis_as_neutral) — hedge inventory for anxiety.
  - (sad, intensity_collapse) — sad-specific intensity rubric.
  - (happy, sarcasm_blind) — sarcasm signature detection.
  - (happy, false_positive_on_neutral) — gratitude tokens vs procedural.
  - (disgust, missing) — moral-violation cue.
  - (surprise, mis_as_happy) — surprise valence neutrality.
  - (neutral, over_classified) — min-cue threshold.
  - (all, uncertain_dump) — force categorical commit.
  - (all, valence_only_signal) — arousal/intensity calibration overlay.

Each playbook is 3-6 ordered steps with a Nowicki-Duke / Ekman /
Plutchik / Russell / WASSA / EmotionQueen anchor.

---

## When to use vs not-use

**Use:** you have an agent batch with ground-truth emotions and want
to know which emotions it's missing + how. Backwards from a user
escalation. Or as a CI gate on agent emotion accuracy.

**Don't use:** to evaluate agent output quality (use HaluEval); to
attribute internal vs environmental locus (use Lewin); to score 4
EI domains (use Goleman); to detect prompt injection (use aar guards).

---

## Calibration

```python
from vstack.danva_emotion import record_baseline, load_baseline, compare_to_baseline

record_baseline(analysis, "baselines/support-agent.json")
fresh = EmotionRecognitionAnalyzer(client).run(trace)
cmp = compare_to_baseline(fresh, load_baseline("baselines/support-agent.json"))
print(cmp.drift_severity)  # none | minor | moderate | severe
```

---

## Versioning

  - `0.0.8` -- initial categorical implementation.
  - `0.1.0` -- production-readiness infrastructure at library level.
  - **`0.2.0`** -- comprehensive upgrade. Multi-mode pipeline. Richer
    schema (14 profile patterns, EmotionConfusionMatrix, IntensityCurve,
    CircumplexProjection, CulturalAdjustment, CascadeAnalysis,
    TextCueSignature, PerEmotionCalibration, ExtendedEmotion). Composition
    manifest, calibration, 12 playbooks, CLI with 7 subcommands, async
    mirror, intensity bias + correlation, Russell circumplex projection.
    14+ academic sources.

Backward compatibility preserved: existing 18 tests pass unmodified.

---

## License

MIT.
