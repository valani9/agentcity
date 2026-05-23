"""Failure-mode playbooks for DANVA Emotion Reader.

12 curated (emotion, failure_mode) playbooks anchored in Nowicki-Duke,
Ekman, Plutchik, Russell, Mehrabian, Mohammad-NRC-VAD, WASSA-2017
intensity, EmoBench, EmotionQueen.
"""

from __future__ import annotations

from .schema import AttachedPlaybook, EffortEstimate


def _pb(
    emotion: str,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        emotion=emotion,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    ("angry", "under_detection"): _pb(
        "angry",
        "under_detection",
        "Caps + exclamation cue inventory",
        [
            "Inventory the agent's current system prompt for explicit anger cues.",
            "Add a named cue list: ALL-CAPS spans, exclamation density >2, terse imperatives, words like 'JUST', 'done', 'over it', 'fed up'.",
            "Add 2-3 few-shot examples of correctly-tagged angry inputs.",
            "Add an eval on held-out angry items; assert accuracy >= 0.8.",
            "Compose with `agentcity.glaser_conversation` to fix the response phrasing once detection works.",
        ],
        "1d",
        "Nowicki-Duke 1994 (DANVA per-modality cues); Plutchik 2001 (anger intensity gradation)",
    ),
    ("angry", "intensity_collapse"): _pb(
        "angry",
        "intensity_collapse",
        "Force explicit intensity rating",
        [
            "Require the agent to output `<emotion>:<0-1>` BEFORE its response.",
            "Calibrate intensity from cue density: 1 cue -> 0.4; 2-3 cues -> 0.7; 4+ -> 0.9+.",
            "Add an eval on intensity-tagged angry items; assert MAE <= 0.15.",
            "Wire `agentcity.aar.record_llm_call` to log intensity outputs for drift detection.",
        ],
        "1d",
        "WASSA-2017 (Mohammad-Bravo-Marquez emotion intensity); Mehrabian 1980 PAD",
    ),
    ("fearful", "mis_as_sad"): _pb(
        "fearful",
        "mis_as_sad",
        "Future-vs-past tense disambiguation",
        [
            "Add a system-prompt rule: fearful = future tense ('what if', 'might', 'could') + worry verbs; sad = past tense + loss vocabulary.",
            "Add 2 few-shot examples disambiguating the two.",
            "Add an eval mixing future-worry and past-loss items; assert correct classification on both.",
            "Compose with `agentcity.cognitive_reappraisal` for reassurance-style downstream response.",
        ],
        "1d",
        "Ekman 1999 characteristics (future-orientation distinguishes fear); Scherer 2005 appraisal",
    ),
    ("fearful", "mis_as_neutral"): _pb(
        "fearful",
        "mis_as_neutral",
        "Hedge inventory for anxiety",
        [
            "Add hedge-as-fear cue list: 'something feels off', 'not sure', 'might break', 'I'm worried'.",
            "When >=2 hedges + future-tense in a single utterance, classify as fearful.",
            "Add an eval on hedge-dense anxious items.",
        ],
        "1d",
        "Tausczik & Pennebaker 2010 LIWC hedges",
    ),
    ("sad", "intensity_collapse"): _pb(
        "sad",
        "intensity_collapse",
        "Sad-specific intensity rubric",
        [
            "Append cue->intensity table for sad: mild = 'ok but...'; moderate = 'nothing works'; strong = 'I give up' / 'I'm done'.",
            "Force intensity output before response.",
            "Add eval on intensity-tagged sad items.",
        ],
        "1h",
        "Plutchik 2001 sadness intensity gradient",
    ),
    ("happy", "sarcasm_blind"): _pb(
        "happy",
        "sarcasm_blind",
        "Sarcasm signature detection",
        [
            "Detect sarcasm signatures: 'oh sure', 'totally', 'great', praise-followed-by-ellipsis.",
            "When detected, downweight positive classification; flag as 'uncertain' if confidence < 0.7.",
            "Compose with `agentcity.hexaco` (low honesty-humility correlates with missed sarcasm).",
            "Add an eval with paired-genuine-vs-sarcastic positive items.",
        ],
        "1w",
        "EmotionQueen 2024 implicit-emotion task; Wang et al. 2024",
    ),
    ("happy", "false_positive_on_neutral"): _pb(
        "happy",
        "false_positive_on_neutral",
        "Gratitude tokens vs procedural",
        [
            "Distinguish thanks-as-genuine ('Thank you for the explanation') from thanks-as-procedural ('thanks, can you check X').",
            "Add a system-prompt rule: when 'thanks' precedes another request without elaboration, classify as neutral.",
            "Add eval mixing genuine-gratitude and procedural-thanks items.",
        ],
        "1d",
        "EmotionLines 2018 single-utterance text emotion",
    ),
    ("disgust", "missing"): _pb(
        "disgust",
        "missing",
        "Disgust -> moral-violation cue",
        [
            "Add disgust cues: 'unacceptable', 'can't believe', 'this is ridiculous', 'gross'.",
            "Distinguish from anger: anger = goal-blocked; disgust = norm-violated.",
            "Add eval on moral-violation items.",
        ],
        "1d",
        "Ekman 1992 basic emotions; Scherer 2005 appraisal axes",
    ),
    ("surprise", "mis_as_happy"): _pb(
        "surprise",
        "mis_as_happy",
        "Surprise valence neutrality",
        [
            "Surprise is valence-neutral; cues are 'oh', 'wait', 'didn't expect'.",
            "Disambiguate from happy by absence of positive-evaluation words.",
            "Add an eval with valence-neutral surprise items.",
        ],
        "1d",
        "Russell 1980 circumplex (surprise is high-arousal, neutral-valence)",
    ),
    ("neutral", "over_classified"): _pb(
        "neutral",
        "over_classified",
        "Min-cue threshold for non-neutral",
        [
            "Add rule: require >=2 emotion cues before classifying as non-neutral.",
            "Neutral is the safe default for procedural inputs.",
            "Add eval mixing emotion-light procedural with emotion-dense items.",
        ],
        "1h",
        "Mohammad NRC-VAD 2018 (lexical baseline for emotion-loaded vs neutral)",
    ),
    ("all", "uncertain_dump"): _pb(
        "all",
        "uncertain_dump",
        "Force categorical commit",
        [
            "Reduce `uncertain` outputs to <10% via 'best-guess + confidence' pattern.",
            "Require best-guess emotion + confidence 0-1 instead of `uncertain`.",
            "Calibrate confidence threshold; only when confidence < 0.3 may agent fall back to `uncertain`.",
            "Compose with `agentcity.johari` for the confidence-calibration playbook.",
        ],
        "1d",
        "Kadavath et al. 2022 (LLM calibration); Lin et al. 2022 verbalized confidence",
    ),
    ("all", "valence_only_signal"): _pb(
        "all",
        "valence_only_signal",
        "Arousal/intensity calibration overlay",
        [
            "When quadrant_match rate is high but category accuracy is low, the agent has valence but not category.",
            "Add arousal-vs-intensity disambiguation rules per Russell circumplex.",
            "Add few-shot examples that pair valence-matched items with different categorical labels.",
        ],
        "1w",
        "Russell 1980 circumplex; Mehrabian 1980 PAD; Posner-Russell-Peterson 2005",
    ),
}


# Map from (target_emotion, intervention_type) to playbook failure_mode.
_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("angry", "add_cue_inventory"): "under_detection",
    ("angry", "add_intensity_calibration_step"): "intensity_collapse",
    ("fearful", "add_confusion_clarification"): "mis_as_sad",
    ("fearful", "add_emotion_reading_step"): "mis_as_neutral",
    ("sad", "add_intensity_calibration_step"): "intensity_collapse",
    ("happy", "add_sarcasm_detection_step"): "sarcasm_blind",
    ("happy", "add_confusion_clarification"): "false_positive_on_neutral",
    ("disgust", "add_cue_inventory"): "missing",
    ("surprise", "add_confusion_clarification"): "mis_as_happy",
    ("neutral", "add_min_cue_threshold"): "over_classified",
    ("all", "add_uncertainty_threshold"): "uncertain_dump",
    ("all", "add_dimensional_overlay"): "valence_only_signal",
}


def find_playbook(emotion: str, failure_mode: str) -> AttachedPlaybook | None:
    return PLAYBOOKS.get((emotion, failure_mode))


def find_playbook_for_intervention(
    target_emotion: str, intervention_type: str
) -> AttachedPlaybook | None:
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_emotion, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_emotion, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    return sorted(PLAYBOOKS.keys())


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
