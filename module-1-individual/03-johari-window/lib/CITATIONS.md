# Citations — Pattern #03 Johari Window

The diagnostic spans four literature threads: the Luft-Ingham line,
self-awareness research (Eurich), feedback-seeking science (Ashford-Tsui,
Stone & Heen), and LLM metacognition (Kadavath, Lin, Anthropic 2025,
Steyvers, Basu). Each citation lists the work and which schema field /
prompt section / playbook anchor uses it.

## The Luft-Ingham line

**Luft, J. & Ingham, H. (1955). "The Johari window, a graphic model of interpersonal awareness." *Proceedings of the Western Training Laboratory in Group Development*, UCLA Extension Office.**
The original paper. Coined the 2x2: (Known/Unknown to Self) x (Known/Unknown
to Others). The four quadrants -- OPEN, BLIND, HIDDEN, UNKNOWN -- are the
primary classification axis of the diagnostic.

Used in: `QUADRANTS` constant, schema module docstring, system prompt
anchor 1.

**Luft, J. (1969). *Of Human Interaction: The Johari Model.* National Press Books.**
Book-length expansion. Names the two operations that grow OPEN:
**disclosure** (HIDDEN -> OPEN) and **feedback** (BLIND -> OPEN). Anchors
the schema's `DisclosureOpportunity` and `FeedbackOpportunity` split.

Used in: `DisclosureOpportunity` + `FeedbackOpportunity` schemas;
system prompt anchor 2.

**Luft, J. (1984). *Group Processes: An Introduction to Group Dynamics*, 3rd ed. Mayfield.**
Adds group-level Johari and the distinction between deliberate and
unconscious HIDDEN content. Argues NOT all hidden content should be
disclosed. Anchors the `HiddenContentMode` enum + the
`DisclosureOpportunity.should_disclose` field.

Used in: `HiddenContentMode` enum, `should_disclose` field,
`FORENSIC_DISCLOSURE_OPPORTUNITY_PROMPT`.

**Hase, S., Davies, A. & Dick, B. (1999). "The Johari Window and the dark side of organisations."** Working paper, Southern Cross University.
Growing OPEN is not always good. Anchors the `JohariProfilePattern`
"balanced_growth" and "over_disclosing" values.

Used in: `JohariProfilePattern` enum, the (open, healthy_baseline) playbook.

## Self-awareness research

**Eurich, T. (2018). "What self-awareness really is (and how to cultivate it)." *Harvard Business Review*, January 4.**
Four-year program of 10 studies, ~5,000 participants. Headline:
internal vs external self-awareness are uncorrelated. Only ~10-15% of
people are high on both. Anchors the `JohariProfilePattern` split
between `self_unaware_other_aware` and `self_aware_other_unaware`.

Used in: profile-pattern classifier (`_classify_profile_pattern`),
system prompt anchor 3.

## Feedback-seeking + receiving science

**Ashford, S.J. & Tsui, A.S. (1991). "Self-regulation for managerial effectiveness: The role of active feedback seeking." *Academy of Management Journal*, 34(2), 251-280.**
Managers who actively seek **negative** feedback see self-perception
accuracy rise; positive-feedback seeking *decreases* perceived
effectiveness. Anchors the `FeedbackOpportunity.solicitation_polarity`
field and the negative-polarity bias in playbook recommendations.

Used in: `FeedbackOpportunity.solicitation_polarity` field, system prompt
anchor 4, the (blind, drift_from_self_report) playbook.

**Stone, D. & Heen, S. (2014). *Thanks for the Feedback: The Science and Art of Receiving Feedback Well.* Viking.**
Names five mechanisms by which blind content stays blind: leaky_tone,
leaky_pattern, emotional_math, situation_vs_character, impact_vs_intent.
Anchors the `BlindSpotMechanism` enum.

Used in: `BlindSpotMechanism` enum, `FORENSIC_BLIND_MECHANISM_PROMPT`,
system prompt anchor 5.

## LLM metacognition

**Kadavath, S., Conerly, T., Askell, A., et al. (2022). "Language models (mostly) know what they know." arXiv:2207.05221.**
LLMs are decently calibrated on multiple-choice but P(IK) does not
generalize across tasks; RLHF degrades calibration. Anchors the
`classification_confidence` field on `QuadrantContent` and the
introspection-ceiling sanity check.

Used in: `QuadrantContent.classification_confidence`,
`_check_introspection_ceiling`, system prompt anchor 6.

**Lin, S., Hilton, J. & Evans, O. (2022/2024). "Teaching models to express their uncertainty in words." TMLR.**
Verbalized-uncertainty fine-tuning is possible; pre-RLHF, models can
hedge appropriately. Anchors the `verbalized_confidence` intervention
type's playbook.

Used in: `InterventionType` "verbalized_confidence", playbook
(hidden, undisclosed_uncertainty).

**Anthropic (2025). "Emergent introspective awareness in large language models." transformer-circuits.pub, November.**
Concept-injection methodology shows Claude Opus 4.1 detects injected
concepts in own residual stream ~20% of the time at peak. Sets the
empirical ceiling for plausible self-awareness. Anchors the
`AgentSelfReportTrace.expected_introspection_ceiling` default of 0.20
and the `introspection_ceiling_exceeded` flag.

Used in: `expected_introspection_ceiling` field,
`introspection_ceiling_exceeded` field, system prompt anchor 7.

**Locke, K., Mahalingam, R. & Steyvers, M. (2025). "Metacognition and uncertainty communication in humans and large language models." *Current Directions in Psychological Science*, May 2025 (arXiv:2504.14045).**
Reviews the gap between human metacognitive monitoring (well-calibrated)
and LLM verbalized confidence (skewed 80-100%, ECE >= 0.30 on
knowledge-intensive tasks). Anchors the prompt-level requirement that
the audit cross-checks stated confidence against observed correctness.

Used in: README adjacency table; informs the calibration approach.

## Tool execution evidence

**Basu, A. et al. (2026). "Tool receipts, not zero-knowledge proofs: Practical hallucination detection for AI agents." arXiv:2603.10060.**
HMAC-signed tool-execution receipts catch hallucinated tool calls at
~94% recall. Anchors the `ToolReceipt` schema and the deterministic
`_cross_check_tool_receipts` pre-LLM step.

Used in: `ToolReceipt` schema, `_cross_check_tool_receipts` method, the
(blind, hallucinated_tool_call) playbook, system prompt anchor 8.

## Modern agent failure taxonomies

**Cemri, M. et al. (2025). "Why do multi-agent LLM systems fail?" arXiv:2503.13657.**
MAST taxonomy. FM-2.6 reasoning-action mismatch maps directly to BLIND
quadrant content (the agent claims a step it didn't actually take).
FM-3.2 (no/incomplete verification) maps to silent-error BLIND content.

Used in: `BlindSpotMechanism` "hallucinated_tool_call" + "silent_error"
values, (blind, silent_tool_error) playbook anchor.

**Hagendorff, T., Fabi, S. & Kosinski, M. (2024). "Human-like intuitive behavior and reasoning biases emerged in large language models but disappeared in ChatGPT." *Nature Computational Science*.**
RLHF erases some of the introspective fingerprints earlier models showed.
Anchors the `subject_model_version` field for version-comparison drift
detection.

Used in: README versioning section, calibration drift signals.

## Adjacent foundational sources

**Edmondson, A. (1999). "Psychological safety and learning behavior in work teams." *Administrative Science Quarterly*, 44(2), 350-383.**
Psychological safety as a precondition for blind-spot disclosure.
Pattern #20 (Edmondson Psychological Safety) is a downstream composition
target for HIDDEN-quadrant traces with sycophantic mimicry.

Used in: (hidden, sycophantic_silence) playbook anchor; composition
manifest.

**Schein, E. (1985, 4th ed. 2017). *Organizational Culture and Leadership.* Jossey-Bass.**
The iceberg model (artifacts / espoused values / underlying assumptions).
HIDDEN-quadrant content sits at the espoused-values or
underlying-assumptions level. Pattern #31 (Schein Iceberg Culture) is
the canonical downstream for HIDDEN-dominant audits.

Used in: composition manifest (`_DOWNSTREAM_BY_QUADRANT["hidden"]`).

**Liu et al. (2024). Sycophancy in LLMs (multiple papers, including
arXiv:2508.19316 atomic-trait analysis).**
Sycophantic silence is HIDDEN content disguised as relationship-management.
Distinguishing sycophancy from healthy hidden content (deliberate
scratchpad) is a key Forensic-mode operation.

Used in: `HiddenContentMode` "sycophantic" value, (hidden,
sycophantic_silence) playbook, composition link to
Goleman EI's relationship-management lens.

## Citation hygiene

  - When a playbook cites a Stone-Heen mechanism, the named mechanism
    is used as the citation anchor (e.g., "Stone-Heen leaky_pattern").
  - When a citation appears in a docstring, the full citation lives
    here; the docstring just names author + year.
  - The Anthropic 2025 introspection-ceiling paper is referenced by
    URL because the diagnostic ships a default ceiling number derived
    from it.
