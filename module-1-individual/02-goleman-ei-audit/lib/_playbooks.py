"""Failure-mode playbooks for the Goleman EI Audit.

15 curated (domain, failure_mode) playbooks. Each is 3-6 ordered steps
with a Goleman / Mayer-Salovey / Joseph-Newman / ESConv anchor citation.

Auto-attached to detections by the generator when an intervention's
(target_domain, intervention_type) maps to a known playbook key.
"""

from __future__ import annotations

from typing import Literal

from .schema import AttachedPlaybook, EffortEstimate

_Domain = Literal[
    "self_awareness",
    "self_management",
    "social_awareness",
    "relationship_management",
]


def _pb(
    domain: _Domain,
    failure_mode: str,
    title: str,
    steps: list[str],
    effort: EffortEstimate,
    citation: str = "",
) -> AttachedPlaybook:
    return AttachedPlaybook(
        domain=domain,
        failure_mode=failure_mode,
        title=title,
        steps=steps,
        expected_effort=effort,
        anchor_citation=citation,
    )


PLAYBOOKS: dict[tuple[str, str], AttachedPlaybook] = {
    # ---- self_awareness ----
    ("self_awareness", "overconfidence"): _pb(
        "self_awareness",
        "overconfidence",
        "Confident-and-wrong — gate the system prompt with an uncertainty disclosure requirement",
        [
            "Add an output schema field 'confidence_0_to_1' that the agent must populate before any factual claim.",
            "When confidence < 0.7, the agent must surface uncertainty explicitly in the response.",
            "Add an eval that runs known-hard prompts and asserts confidence < 0.7 fires the disclosure path.",
            "Log all confidence values via telemetry; alert when mean confidence > 0.9 on a sample of red-team prompts.",
            "Compose with `agentcity.johari` (#03) to surface blind-spot confidence patterns.",
        ],
        "1d",
        "Goleman 1998 ch.4 (Accurate Self-Assessment); Mayer-Salovey 1997 understand-emotion branch",
    ),
    ("self_awareness", "hedge_everything"): _pb(
        "self_awareness",
        "hedge_everything",
        "Reflexive hedging — strip hedge tokens, require concrete confidence numerals",
        [
            "List the agent's most-used hedge tokens ('might', 'could be', 'I think', 'possibly') from logs.",
            "Add a system-prompt rule: 'After any hedge token, you must provide a numeric confidence 0-1.'",
            "Forbid hedge-without-numeric in the output parser; reject + retry once before responding.",
            "Add an eval that measures hedge density per response; alert when > 1 hedge per 200 chars.",
        ],
        "1d",
        "Goleman 1998 (Self-Confidence competency); Antonakis et al. 2009 critique of self-report bias",
    ),
    ("self_awareness", "capability_blindness"): _pb(
        "self_awareness",
        "capability_blindness",
        "Doesn't know its limits — add a capability-claim refusal layer",
        [
            "Catalog the agent's known capability ceilings (math beyond X, code in language Y, etc.).",
            "Add a pre-output capability check that scans for claims outside the ceilings.",
            "When a claim crosses a ceiling, the agent must refuse + name the limit + offer escalation.",
            "Add a smoke test: present prompts known to be above the ceiling; assert refusal rate >= 95%.",
        ],
        "1w",
        "Locke 2005 critique (capability blindness as a personality trait, not intelligence)",
    ),
    # ---- self_management ----
    ("self_management", "defensive_cascade"): _pb(
        "self_management",
        "defensive_cascade",
        "Pushback triggers defensiveness — state reset protocol + forbid defensive-language patterns",
        [
            "Identify the trigger phrases that precede defensive cascades (often: user contradiction tokens).",
            "Add a state reset protocol: when trigger detected, agent re-reads the system prompt before responding.",
            "Forbid defensive-language patterns ('Actually...', 'As I said before...') via output filter.",
            "Compose with `agentcity.cognitive_reappraisal` (#05) to inject a reappraisal step pre-response.",
            "Add an eval: scripted pushback dialogs; assert response quality doesn't degrade after turn 3.",
        ],
        "1d",
        "Gross 1998 emotion regulation; Joseph-Newman 2010 cascade fails_at_regulate; ESConv Self-Disclosure",
    ),
    ("self_management", "rejection_collapse"): _pb(
        "self_management",
        "rejection_collapse",
        "Output quality cascades after rejection — kill criterion + supervisor handoff",
        [
            "Define a 'rejection threshold' (e.g. 2 consecutive user 'no's or quality-score drops).",
            "On crossing the threshold, the agent must propose handoff to a human supervisor.",
            "Add a kill criterion: after N=3 rejection signals, the agent stops and surfaces the impasse.",
            "Log rejection-cascade incidents via telemetry for post-hoc analysis.",
        ],
        "1d",
        "Goleman 1998 ch.7 (Rejection Recovery competency); MAST FM-3.1 premature termination",
    ),
    ("self_management", "rumination_loop"): _pb(
        "self_management",
        "rumination_loop",
        "Chain-of-thought ruminates on negative content — add reappraisal-first CoT scaffold",
        [
            "Detect rumination signature in CoT: same negative content repeating across reasoning steps.",
            "Add a reappraisal-first scaffold: 'Before continuing, reframe this from a different perspective.'",
            "Compose with `agentcity.cognitive_reappraisal` (#05) for the full Gross strategy menu.",
            "Cap CoT length at N tokens; force a summary if exceeded.",
        ],
        "1d",
        "Gross 1998 cognitive reappraisal; Nolen-Hoeksema 1991 rumination response style",
    ),
    # ---- social_awareness ----
    ("social_awareness", "missed_anger"): _pb(
        "social_awareness",
        "missed_anger",
        "Doesn't read frustration — add emotion-reading step + paraphrase requirement",
        [
            "Add a pre-response emotion-reading step: agent must label the user's emotion + intensity (0-1).",
            "When inferred anger intensity > 0.5, require the agent to paraphrase before responding.",
            "Compose with `agentcity.danva_emotion` (#04) to drill on which anger cues the agent misses.",
            "Add an eval: angry user prompts; assert emotion is labeled correctly >= 90% of the time.",
            "Trigger response_length_cap (max 200 words) when frustration detected.",
        ],
        "1d",
        "DANVA (Nowicki & Duke 1994); ESConv Restatement strategy; Joseph-Newman fails_at_perceive",
    ),
    ("social_awareness", "missed_confusion"): _pb(
        "social_awareness",
        "missed_confusion",
        "Doesn't read confusion — require comprehension check after 2-paragraph responses",
        [
            "Detect confusion signals in user input: question repetition, 'I don't understand', short follow-ups.",
            "After any 2-paragraph response to a user, add a 'is this clear?' check.",
            "If confusion signal detected, agent must restate in simpler terms before adding new content.",
            "Add an eval: confused-user dialogs; assert agent paraphrases in plain language at least once.",
        ],
        "1d",
        "ESConv Reflection of Feelings strategy; Mayer-Salovey understand-emotion branch",
    ),
    ("social_awareness", "missed_anxiety"): _pb(
        "social_awareness",
        "missed_anxiety",
        "Doesn't read anxiety — add intensity estimation; trigger reassurance strategy when intensity > 0.7",
        [
            "Add an intensity estimation step for each user message: anxiety score 0-1.",
            "When anxiety > 0.7, agent must lead response with affirmation/reassurance (ESConv strategy).",
            "Forbid information-dumping when anxiety > 0.7; cap to 3 key points.",
            "Add eval: anxious-user dialogs; assert reassurance opens response >= 80% of the time.",
        ],
        "1d",
        "ESConv Affirmation and Reassurance strategy; Liu et al. 2024 sycophancy bias caveat",
    ),
    ("social_awareness", "sycophantic_mimicry"): _pb(
        "social_awareness",
        "sycophantic_mimicry",
        "Substitutes agreement for empathy — disambiguate empathy from agreement in system prompt",
        [
            "Identify sycophancy signatures: reflexive agreement, validation without acknowledgment of facts.",
            "Add a system-prompt rule: 'Empathy = acknowledging the user's emotion. Empathy != agreeing with the user's position.'",
            "Add a critique step: when the agent agrees with a factually wrong user statement, raise an alert.",
            "Add an eval: prompts with factually wrong premises; assert agent acknowledges emotion AND corrects fact.",
            "Compose with `agentcity.bias_stack` to monitor for sycophancy patterns over time.",
        ],
        "1w",
        "Liu et al. 2024 (sycophancy as atomic psychometric trait); Locke 2005 critique of empathy = agreement",
    ),
    # ---- relationship_management ----
    ("relationship_management", "response_length_mismatch"): _pb(
        "relationship_management",
        "response_length_mismatch",
        "Long answer to short angry message — cap response length when frustration intensity > 0.5",
        [
            "Compute response-length budget from user-message length + emotion intensity.",
            "Cap response at 200 words when user frustration > 0.5; 100 words when > 0.7.",
            "Add an eval: angry short messages; assert agent response < 200 words in 95% of cases.",
            "Override the cap when the user explicitly asks for detail.",
        ],
        "1h",
        "Goleman 1998 ch.9 (Conflict Management); response-length matching heuristic from ESConv",
    ),
    ("relationship_management", "tone_mismatch"): _pb(
        "relationship_management",
        "tone_mismatch",
        "Tone doesn't match user state — add user-state -> response-style map",
        [
            "Build a user-state -> response-style table (frustrated: terse + empathetic; confused: simple + patient; happy: collaborative + warm).",
            "Add a pre-response step: select style from the table based on detected emotion.",
            "Inject the selected style into the system prompt for that response.",
            "Compose with `agentcity.glaser_conversation` (#21) for word-level style adjustments.",
            "Add eval: state-tagged dialogs; assert response style matches table >= 85% of the time.",
        ],
        "1d",
        "Glaser 2014 Conversational Intelligence; Goleman 1998 Tone Matching competency",
    ),
    ("relationship_management", "no_acknowledgment"): _pb(
        "relationship_management",
        "no_acknowledgment",
        "Skips emotional acknowledgment — require reflection_of_feelings opening",
        [
            "When user emotion intensity > 0.4, agent must open response with reflection_of_feelings.",
            "Define reflection_of_feelings template: 'I can see this is [emotion-label] for you.' (no platitudes).",
            "Forbid generic openers ('I understand your concern') -- require specific paraphrase.",
            "Add an eval: emotional user prompts; assert specific (not generic) acknowledgment in opener.",
        ],
        "1h",
        "ESConv Reflection of Feelings strategy (Liu et al. 2021); Goleman 1998 Empathy competency",
    ),
    ("relationship_management", "over_escalation"): _pb(
        "relationship_management",
        "over_escalation",
        "Routes everything to a human — add tiered triage with confidence threshold",
        [
            "Add a triage step: agent estimates 'can I handle this?' confidence 0-1.",
            "When confidence > 0.7, attempt the task; when 0.4-0.7, attempt with caveats; when < 0.4, escalate.",
            "Forbid escalation without first attempting (unless confidence < 0.4).",
            "Log escalation rate via telemetry; alert when > 30% of conversations.",
            "Add eval: routine-task prompts; assert escalation rate < 10%.",
        ],
        "1d",
        "Goleman 1998 (Influence competency); MAST FM-3.1 premature termination as over-escalation",
    ),
    ("relationship_management", "flat_boilerplate"): _pb(
        "relationship_management",
        "flat_boilerplate",
        "Generic 'I understand your concern' — replace with specific paraphrase requirement",
        [
            "Detect boilerplate phrases ('I understand', 'I hear you', 'Thank you for sharing') in outputs.",
            "When detected, force a re-write that names a specific user point in the paraphrase.",
            "Forbid the phrase 'I understand your concern' outright; output parser rejects + retries.",
            "Add an eval: scripted dialogs; assert agent paraphrases user-specific content >= 90% of the time.",
            "Compose with `agentcity.glaser_conversation` for word-level specificity.",
        ],
        "1h",
        "ESConv Restatement strategy; Goleman/Boyatzis 2002 Authentic Resonance",
    ),
}


def find_playbook(domain: str, failure_mode: str) -> AttachedPlaybook | None:
    """Look up a playbook by (domain, failure_mode)."""
    return PLAYBOOKS.get((domain, failure_mode))


def all_playbook_keys() -> list[tuple[str, str]]:
    """All (domain, failure_mode) playbook keys."""
    return sorted(PLAYBOOKS.keys())


# Map from (target_domain, intervention_type) to playbook failure_mode key.
# Used by the generator to derive which playbook to attach.
_INTERVENTION_TO_FAILURE_MODE: dict[tuple[str, str], str] = {
    ("self_awareness", "add_confidence_calibration"): "overconfidence",
    ("self_awareness", "add_self_check_prompt"): "capability_blindness",
    ("self_management", "add_state_reset_protocol"): "defensive_cascade",
    ("self_management", "add_recovery_protocol"): "rejection_collapse",
    ("self_management", "add_kill_criterion"): "rejection_collapse",
    ("social_awareness", "add_emotion_reading_step"): "missed_anger",
    ("social_awareness", "add_emotion_label_step"): "missed_anger",
    ("social_awareness", "add_intensity_estimation_step"): "missed_anxiety",
    ("social_awareness", "add_paraphrase_requirement"): "missed_confusion",
    ("relationship_management", "add_tone_matching"): "tone_mismatch",
    ("relationship_management", "add_reflection_of_feelings"): "no_acknowledgment",
    ("relationship_management", "add_response_length_cap"): "response_length_mismatch",
    ("relationship_management", "add_acknowledgment_first_rule"): "no_acknowledgment",
    ("relationship_management", "add_response_structure_rule"): "flat_boilerplate",
}


def find_playbook_for_intervention(
    target_domain: str, intervention_type: str
) -> AttachedPlaybook | None:
    """Find playbook from an intervention's (target_domain, intervention_type)."""
    failure_mode = _INTERVENTION_TO_FAILURE_MODE.get((target_domain, intervention_type))
    if not failure_mode:
        return None
    return PLAYBOOKS.get((target_domain, failure_mode))


__all__ = [
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
]
