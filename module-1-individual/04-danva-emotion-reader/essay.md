# Your agent reads "I JUST WANT THIS FIXED!!!" as neutral. DANVA quantifies the gap.

*A thirtieth essay from vstack — organizational behavior, practiced on AI agents.*

---

A customer types: *"I JUST WANT THIS FIXED!!!"* — caps, exclamations, terse imperative, the word *"JUST"* doing a lot of work. Any human reads that as anger at intensity ~0.9. The agent reads it as neutral, intensity 0.3. The agent then produces a six-paragraph technical explanation. The customer disengages.

Pattern #02 (Goleman EI Audit) catches the failure at the competency level: social-awareness is low. Pattern #21 (Glaser Conversation Steering) catches it at the phrasing level: agent response triggered cortisol cascade. Both are correct. Both lack *numbers you can track per-deploy.*

The DANVA tradition fixes this. In 1994, Stephen Nowicki and Marshall Duke published *"A Measure of Nonverbal Social Processing Ability in Children Between the Ages of 6 and 10 Years"* — a standardized battery measuring emotion-recognition accuracy from facial expressions, vocal tones, and body postures. Subjects looked at images / heard clips and named the emotion. Researchers computed per-emotion accuracy and confusion matrices. The findings — that humans differ measurably and reliably in nonverbal accuracy, and that the differences predict downstream social outcomes — anchored two decades of emotion-recognition research, including Paul Ekman's basic-emotions framework.

For AI agents, the modality is text, but the operational test is the same: given a user utterance with a known emotion, can the agent identify it correctly? And when wrong, *which other emotion does it pick?* The confusion matrix is the diagnostic value, because each confusion pattern points at a specific cue the agent is missing.

The seven canonical categories are Ekman's basic emotions plus neutral: **happy, sad, angry, fearful, disgust, surprise, neutral.** For each category, the diagnostic computes:

- **Accuracy** — fraction correctly identified.
- **Intensity MAE** — mean absolute error between inferred and ground-truth intensity (0..1).
- **Confusion partners** — when the agent got this emotion wrong, which alternative did it pick?

All three are deterministic. The library doesn't ask an LLM to *score* the metrics — it computes them in Python from the trace items. The LLM is involved only in *intervention generation* on top of the locked numbers.

In the opening example, the agent is exhibiting two textbook DANVA failure modes:

1. **Anger under-detection.** Anger has the lowest accuracy in the batch (0%). Two ground-truth-angry items both got classified as neutral. The agent is missing the anger cues: ALL-CAPS spans, exclamation density, terse imperative, intensifier word ("JUST").

2. **Intensity collapse.** Even when the agent classified emotions correctly, its intensity estimates undershoot. Ground-truth intensity 0.9 was inferred as 0.3. This is a real failure mode separate from accuracy — the agent might know the user is upset but rate the upset as mild, leading to under-calibrated responses.

The interventions map cleanly to the diagnostic:

- For under-detection of one specific emotion: `add_cue_inventory` — explicitly list the text cues for that emotion in the system prompt.
- For confusion between two emotions (e.g., fearful → sad): `add_confusion_clarification` — distinguish the two with concrete rules.
- For intensity collapse across the board: `add_intensity_calibration_step` — force explicit intensity rating before response.
- For batch-wide weakness: `few_shot_examples` of the underperforming category.

Each intervention is a system-prompt addition. None require model retraining or new infrastructure.

## Why this matters operationally

The single highest-leverage use is **regression testing emotion-recognition accuracy across deploys.** Most teams running customer-facing agents have no objective metric for *"is the agent reading emotion correctly?"* They have anecdotes ("user complained about the response") and aggregate sentiment metrics ("CSAT dropped"), neither of which tells them whether the failure was emotion-recognition or response-style or content. DANVA gives them a per-emotion accuracy number on a fixed batch — when the number moves, they know which deploy introduced the regression and which emotion drove it.

The second-highest-leverage use is **diagnosing *which* emotion is the problem.** Generic "improve EQ" interventions are unactionable. "Anger accuracy is 30%; here's the confusion matrix: 70% of misclassifications go to neutral" is actionable — the fix is a specific cue-inventory intervention on the system prompt.

The third use is **comparative analysis across models / agents.** Because the math is deterministic, you can run the same eval batch across Claude / GPT / Llama / your fine-tune and get directly comparable accuracy numbers per emotion. This is the kind of comparison that's impossible with LLM-judged diagnostics because the judge's scoring is non-deterministic.

## How this fits with the rest of vstack

This is pattern #04 — the thirty-first pattern shipped. It composes with several other Module 1 / Module 2 patterns:

- **#02 Goleman 4-Domain EI Audit** — measures the *competency* of emotion reading at a high level (social-awareness); #04 measures the *per-emotion accuracy* with a specific batch.
- **#21 Glaser Conversation Steering** — measures whether the agent's *response phrasing* triggers cortisol; #04 measures whether the agent *reads* the user's emotion correctly in the first place.
- **#05 Cognitive Reappraisal** — measures the agent's *response to* emotional content (suppress vs reframe); #04 measures the upstream *recognition*.

The four together cover the full emotional-intelligence stack: #02 at the competency level, #04 at the recognition-accuracy level, #05 at the response-strategy level, #21 at the phrasing level. A team running all four can pinpoint exactly where in the EQ pipeline an agent is failing — recognition vs strategy vs phrasing vs overall competency.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-1-individual/04-danva-emotion-reader
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
