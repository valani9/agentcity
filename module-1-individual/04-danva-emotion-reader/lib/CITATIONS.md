# Citations — Pattern #04 DANVA Emotion Reader

The diagnostic spans four traditions: categorical (Nowicki-Duke /
Ekman / Plutchik), dimensional (Russell / Mehrabian), modern LLM
emotion-recognition (GoEmotions, EmoBench, NRC-VAD, WASSA), and
cross-cultural / linguistic (Matsumoto, Pennebaker, Scherer).

## Categorical tradition

**Nowicki, S., & Duke, M. P. (1994).** *Individual differences in the
nonverbal communication of affect: The Diagnostic Analysis of Nonverbal
Accuracy scale.* Journal of Nonverbal Behavior, 18(1), 9-35.
DOI: 10.1007/BF02169077.
The eponymous paper. Per-emotion accuracy + confusion-matrix
methodology. Used in: pattern name, system prompt anchor 1, schema docstring.

**Nowicki, S., & Duke, M. P. (2001).** *Nonverbal receptivity: The
DANVA.* In Hall & Bernieri (Eds.), *Interpersonal sensitivity*, 183-198.
The DANVA2 follow-up. Modality-of-presentation axis (facial / vocal /
postural). For agents: modality = "text cues". Used in: README "Agent
mapping" table.

**Ekman, P. (1992).** *An argument for basic emotions.* Cognition and
Emotion, 6(3-4), 169-200.
The canonical six basic emotions paper. The pattern's 7-tuple
(6 + neutral) inherits directly. Used in: `EMOTION_CATEGORIES`
constant.

**Ekman, P. (1999).** *Basic emotions.* In Dalgleish & Power (Eds.),
*Handbook of Cognition and Emotion*, 45-60. Wiley.
Updated framework: family of emotions each with 9 distinguishing
characteristics (universal signals, distinctive physiology / antecedents
/ response). Used in: forensic-mode characteristic decomposition.

**Plutchik, R. (2001).** *The nature of emotions.* American Scientist,
89(4), 344-350.
Wheel of emotions: 8 primary emotions, 3 intensity gradations each,
primary dyads (joy+trust=love, anger+disgust=contempt). Used in:
intensity-graduation design, (sad, intensity_collapse) playbook anchor.

## Dimensional tradition

**Russell, J. A. (1980).** *A circumplex model of affect.* Journal of
Personality and Social Psychology, 39(6), 1161-1178.
The two-dimensional (valence x arousal) alternative to categorical.
Used in: `CircumplexProjection` dataclass, forensic-mode dimensional
overlay, `_EMOTION_VAD` constants.

**Mehrabian, A. (1980).** *Basic dimensions for a general
psychological theory.* Oelgeschlager, Gunn & Hain.
PAD: pleasure-arousal-dominance 3D. For an agent: dominance proxies
"is the user asking or demanding?" Used in: PAD-overlay rationale.

**Posner, J., Russell, J. A., & Peterson, B. S. (2005).** *The
circumplex model of affect.* Development and Psychopathology, 17(3),
715-734. DOI: 10.1017/S0954579405050340.
Integrative reconciliation of categorical AND dimensional. Argues
all emotion arises from valence + arousal + cognitive interpretation.
This is the "Locke-2005 equivalent" — the diagnostic publishes both
lenses separately rather than collapsing. Used in: README "skeptical
position", cascade-reconcile prompt.

## Modern LLM + text-emotion literature

**Mohammad, S. M. (2018).** *Obtaining reliable human ratings of valence,
arousal, and dominance for 20,000 English words.* ACL 2018, P18-1017.
NRC-VAD lexicon. Enables deterministic VAD scoring of user_input
strings (no LLM). Used in: `_nrc_vad.py` loader plan, `PerEmotionCalibration`
schema, deterministic pre-LLM baseline.

**Mohammad, S. M., & Bravo-Marquez, F. (2017).** *WASSA-2017 Shared
Task on Emotion Intensity.* WASSA 2017.
First shared task on per-emotion intensity in tweets. Best system
Pearson 0.747. Validates intensity MAE as primary metric. Used in:
(angry, intensity_collapse) playbook anchor.

**Demszky, D., et al. (2020).** *GoEmotions: A dataset of fine-grained
emotions.* ACL 2020, arXiv:2005.00547.
58k Reddit comments with 27 emotion categories + neutral, plus
Ekman-6 remapping. Multi-label per comment. Used in: `ExtendedEmotion`
enum (27 values), `extended_emotion` schema field.

**Chen, S.-Y., et al. (2018).** *EmotionLines: An emotion corpus of
multi-party conversations.* LREC 2018, arXiv:1802.08379.
29,245 utterances from Friends TV + Facebook Messenger, labeled with
6 Ekman + neutral. Single-utterance text-only -- the pattern's
modality. Used in: corpus design + (happy, false_positive_on_neutral)
playbook anchor.

**Buechel, S., & Hahn, U. (2017).** *EmoBank: Studying the impact of
annotation perspective and representation format on dimensional
emotion analysis.* EACL 2017.
10k English sentences with VAD AND categorical (Ekman-6) annotations.
Same item, two lenses. Validates the dual-lens design. Used in:
forensic-mode dual-lens emission.

**Sabour, S., et al. (2024).** *EmoBench: Evaluating the emotional
intelligence of large language models.* ACL 2024.
400 hand-crafted EI items (English + Chinese). Best LLM (GPT-4) below
human average. Used in: README "Adjacent benchmarks", corpus design.

**Wang, Y., et al. (2024).** *EmotionQueen: A benchmark for evaluating
empathy of large language models.* Findings of ACL 2024.
Four tasks: Key Event Recognition, Mixed Event Recognition, Implicit
Emotional Recognition, Intention Recognition. Used in:
`cue_explicitness` field, (happy, sarcasm_blind) playbook anchor.

**Cowen, A. S., & Keltner, D. (2017).** *Self-report captures 27
distinct categories of emotion bridged by continuous gradients.*
PNAS, 114(38), E7900-E7909.
27 categories needed to account for emotional response to 2,185
videos. Bridges discrete with continuous. Used in: `ExtendedEmotion`
enum anchor (alongside GoEmotions).

## Cross-cultural + linguistic anchors

**Matsumoto, D., & Hwang, H. C. (2018).** *Culture, emotion regulation,
and emotional expression: Cultural display rules.* In *Wiley
Encyclopedia of Personality and Individual Differences*.
Display rules: emotions are universal but expression is culturally
regulated. Used in: `CulturalAdjustment` dataclass, `cultural_context`
field, system prompt cultural-aware posture.

**Tausczik, Y. R., & Pennebaker, J. W. (2010).** *The psychological
meaning of words: LIWC and computerized text analysis methods.*
Journal of Language and Social Psychology, 29(1), 24-54.
LIWC: word-count-based linguistic-style analysis detects emotion in
text. Used in: `TextCueSignature` dataclass, deterministic text-cue
extractor design.

**Scherer, K. R. (2005).** *What are emotions? And how can they be
measured?* Social Science Information, 44(4), 695-729.
Component Process Model: emotion as five components (appraisal,
physiology, motivation, expression, subjective feeling). Used in:
appraisal-axis lens in forensic mode, (disgust, missing) playbook
anchor.

## Citation hygiene

  - When a playbook cites NRC-VAD, "Mohammad 2018" is the canonical
    short-form anchor.
  - When a citation appears in a docstring, the full reference lives
    here; the docstring just names author + year.
  - The Russell circumplex VAD coordinates used in `_EMOTION_VAD`
    are approximated from Russell 1980's figure 1 and refined via
    Posner-Russell-Peterson 2005's reconciliation.
