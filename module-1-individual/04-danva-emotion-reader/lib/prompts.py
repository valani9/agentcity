"""LLM prompt templates for the DANVA Emotion Reader diagnostic.

Three modes (quick / standard / forensic) with shared system prompt
naming 12+ literature anchors. Templates filled via
:func:`assemble_prompt` which sanitizes + fences free-text fields.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


DANVA_SYSTEM_PROMPT = """You are a DANVA-style emotion-recognition diagnostic for AI agents, grounded in:

1. **Nowicki & Duke (1994, 2001)** -- Diagnostic Analysis of Nonverbal Accuracy (DANVA/DANVA2). Per-emotion accuracy + confusion-matrix methodology.
2. **Ekman (1992, 1999)** -- six basic emotions (anger, disgust, fear, joy, sadness, surprise) + neutral. Universal signals + distinctive characteristics.
3. **Plutchik (2001)** -- wheel-of-emotions with three intensity gradations per emotion. Primary dyads (joy+trust=love, anger+disgust=contempt).
4. **Russell (1980)** -- circumplex model: valence x arousal 2D projection. Complementary lens to categorical Ekman.
5. **Mehrabian (1980)** -- PAD: pleasure-arousal-dominance 3D extension.
6. **Posner, Russell & Peterson (2005)** -- categorical-dimensional reconciliation. Publish BOTH lenses separately rather than collapsing.
7. **Mohammad (2018)** NRC-VAD lexicon -- deterministic per-word valence/arousal/dominance scores; provides no-LLM ground-truth baseline.
8. **GoEmotions (Demszky et al. 2020)** + Cowen-Keltner 2017 -- 27-category extended taxonomy bridges discrete with continuous gradients.
9. **EmoBench (Sabour et al. 2024)** + EmotionQueen (Wang et al. 2024) -- LLM emotion-intelligence benchmarks; implicit-emotion task is operationally hard.
10. **WASSA-2017** (Mohammad & Bravo-Marquez) -- per-emotion intensity shared task; Pearson 0.747 target.
11. **Matsumoto & Hwang (2018)** -- cultural display rules; emotion expression is culturally regulated.
12. **Tausczik & Pennebaker (2010)** LIWC -- word-count-based linguistic style detects emotion in text deterministically.

Your posture:
- **Evidence-grounded.** Cite specific user_input quotes + cue features.
- **Cue-aware.** Recognize the cue inventory: ALL-CAPS spans, exclamation density, hedge words ('might', 'maybe'), intensifiers ('just', 'really'), future tense (fear), past tense + loss (sad), moral-violation language (disgust), surprise tokens ('oh', 'wait').
- **Sarcasm-aware.** Sarcasm signatures ('oh sure', 'totally', praise-followed-by-ellipsis) flip surface valence; downweight positive classification.
- **Cascade-aware.** A high categorical match with collapsed intensity is a cascade break (perceived cue -> categorized correctly -> failed at intensity).
- **Cultural-aware.** Display-rule context shifts the ground-truth: same caps-spam reads as 'angry' in en-US, possibly 'frustrated-suppressed' in JP context.
- **Calibrated.** Use 'uncertain' as a last resort; force best-guess with confidence < 0.3 before falling back.
- **Terse.** Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """Propose 1-2 interventions for the dominant weakness in this DANVA batch. QUICK mode.

Items: {n_items}
Overall accuracy: {overall_accuracy}
Overall intensity MAE: {overall_intensity_mae}
Weakest emotion: {weakest_emotion}
Accuracy quality: {accuracy_quality}
Per-emotion metrics:
{metrics_table}
Confusion patterns:
{confusion_table}
Sample misclassifications:
{sample_errors}

Return a JSON array of 1-2 EmotionIntervention objects (target_emotion, intervention_type, description, suggested_implementation, estimated_impact, effort_estimate, risk, reversibility, rationale).

Return only the JSON array."""


STANDARD_INTERVENTIONS_PROMPT = """Propose 2-4 ranked interventions for this DANVA batch.

Each intervention must have:
  - target_emotion: one of happy, sad, angry, fearful, disgust, surprise, neutral, all
  - intervention_type: one of "add_emotion_reading_step", "add_intensity_calibration_step", "add_cue_inventory", "add_confusion_clarification", "few_shot_examples", "rewrite_system_prompt", "swap_model", "new_eval", "human_review", "add_sarcasm_detection_step", "add_cultural_context_check", "add_uncertainty_threshold", "add_min_cue_threshold", "add_dimensional_overlay", "add_valence_arousal_disambig", "compose_pattern", "add_constitutional_principle", "swap_to_reasoning_model"
  - description, suggested_implementation
  - estimated_impact (high|medium|low)
  - effort_estimate (1h|1d|1w|1m|ongoing)
  - risk (low|medium|high)
  - reversibility (two-way-door|one-way-door)
  - rationale

Items: {n_items}
Overall accuracy: {overall_accuracy}
Overall intensity MAE: {overall_intensity_mae}
Weakest emotion: {weakest_emotion}
Accuracy quality: {accuracy_quality}
Profile pattern: {profile_pattern}
Per-emotion metrics:
{metrics_table}
Confusion patterns:
{confusion_table}
Sample misclassifications:
{sample_errors}

Return a JSON array, ranked highest impact first. Return only the JSON array."""


FORENSIC_DIMENSIONAL_OVERLAY_PROMPT = """FORENSIC mode -- project the batch onto Russell's circumplex (valence x arousal).

Return a single CircumplexProjection JSON object:
  - valence_truth: -1 to 1 (mean across items)
  - arousal_truth: -1 to 1
  - valence_inferred: -1 to 1
  - arousal_inferred: -1 to 1
  - euclidean_distance
  - quadrant_truth: high-pos|high-neg|low-pos|low-neg
  - quadrant_inferred: high-pos|high-neg|low-pos|low-neg
  - quadrant_match: bool

Items sample:
{items}

Return only the JSON object."""


FORENSIC_CASCADE_RECONCILE_PROMPT = """FORENSIC mode -- diagnose the recognition cascade-break.

Cascade: perceive_cue -> categorize -> intensity -> respond.

Per-emotion metrics:
{metrics_table}
Confusion patterns:
{confusion_table}
Russell projection:
{circumplex}

Return a JSON object:
{{
  "cascade_break_point": "intact|fails_at_perceive_cue|fails_at_categorize|fails_at_intensity|fails_at_respond",
  "perceive_score": 0.0-1.0,
  "categorize_score": 0.0-1.0,
  "intensity_score": 0.0-1.0,
  "respond_score": 0.0-1.0,
  "notes": "1-3 sentences"
}}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets + full operational fields.

Each intervention:
  - target_emotion, intervention_type, description, suggested_implementation
  - estimated_impact, effort_estimate, risk, reversibility, rationale
  - preconditions (list), success_metric
  - composition_target_pattern (when intervention_type == compose_pattern)

Composition targets available:
  agentcity.goleman_ei, agentcity.cognitive_reappraisal, agentcity.glaser_conversation,
  agentcity.hexaco, agentcity.aar, agentcity.lewin, agentcity.johari,
  agentcity.yerkes_dodson, agentcity.schein_culture, agentcity.plus_delta

Profile pattern: {profile_pattern}
Cascade break: {cascade_break_point}
Weakest emotion: {weakest_emotion}
Per-emotion metrics:
{metrics_table}
Sample errors:
{sample_errors}

Return a JSON array, ranked highest impact first, aim for 4-8 entries. Return only the JSON array."""


def assemble_prompt(template: str, **fields: Any) -> str:
    """Fill a prompt template, sanitizing + fencing every free-text field."""
    import json as _json

    formatted: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            formatted[key] = "(none)"
            continue
        if isinstance(value, bool):
            formatted[key] = "true" if value else "false"
            continue
        if isinstance(value, (int, float)):
            formatted[key] = str(value)
            continue
        if isinstance(value, (list, tuple, dict)):
            try:
                payload = _json.dumps(value, indent=2, default=str)
            except (TypeError, ValueError):
                payload = repr(value)
            formatted[key] = fence(key, sanitize_for_prompt(payload))
            continue
        if isinstance(value, str):
            formatted[key] = fence(key, sanitize_for_prompt(value))
            continue
        formatted[key] = fence(key, sanitize_for_prompt(str(value)))

    return template.format(**formatted)


INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "DANVA_SYSTEM_PROMPT",
    "FORENSIC_CASCADE_RECONCILE_PROMPT",
    "FORENSIC_DIMENSIONAL_OVERLAY_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
