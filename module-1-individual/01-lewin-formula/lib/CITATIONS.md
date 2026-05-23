# Citations — Pattern #01 Lewin Formula

A per-pattern bibliography for `agentcity.lewin`. Each citation lists
the work, why it appears in the diagnostic, and which schema field or
prompt section uses it.

## Primary source — Kurt Lewin

**Lewin, K. (1936). *Principles of Topological Psychology* (F. Heider & G. M. Heider, Trans.). New York: McGraw-Hill.**
The behavior formula `B = f(P, E)` (originally written `B = f(L)` where
`L` is the life space `L = P ∪ E`) is introduced at p. 12: "every
psychological event depends upon the state of the person and at the same
time on the environment, although their relative importance is different
in different cases." pp. 23–25 distinguish the *psychological*
environment from the physical environment; p. 34 catalogues the
components of "the person."

Used in: system prompt, top-level package docstring, schema docstring,
README, essay.

**Lewin, K., Lippitt, R., & White, R. K. (1939). Patterns of aggressive
behavior in experimentally created social climates. *Journal of Social
Psychology*, 10, 271–301.**
Empirical work establishing that *behavior is set by the climate*.
Autocratic / democratic / laissez-faire groups produced different
behaviors from the same children depending on the climate. For agents:
the system prompt + orchestration topology *is* the climate. Anchors
the system-prompt and orchestration playbooks.

Used in: playbook anchor for `(environmental, system_prompt)`.

**Lewin, K. (1947). Frontiers in group dynamics. *Human Relations*, 1, 5–41.**
Introduces the unfreeze-change-refreeze model. Internal-locus
interventions (fine-tuning, model swap) are forced refreezes;
environmental-locus interventions are not. Anchors the model_version
playbook.

Used in: playbook anchor for `(internal, model_version)`.

**Lewin, K. (1951). *Field Theory in Social Science: Selected Theoretical Papers* (D. Cartwright, Ed.). Harper & Row.**
Posthumous. Introduces force-field analysis — behavior as the
equilibrium of driving forces and restraining forces in the life space.
Anchors the task-framing playbook (ambiguity is a restraining force).

Used in: playbook anchor for `(environmental, task_framing)`.

## Person-situation debate

**Mischel, W. (1968). *Personality and Assessment.* New York: Wiley.**
Argued cross-situational consistency of behavior is low (the
"personality coefficient" of .30). Read by some as "person doesn't
matter; only situation." Triggered the debate the formula implicitly
resolves.

Used in: README framing section.

**Bem, D. J., & Allen, A. (1974). On predicting some of the people some of the time. *Psychological Review*, 81, 506–520.**
Proposed person-as-moderator: some people consistent on some traits in
some situations. Step toward the interactionist resolution.

Used in: README framing section.

**Funder, D. C., & Ozer, D. J. (1983). Behavior as a function of the situation. *Journal of Personality and Social Psychology*, 44, 107–112.**
Showed *situations* also produce r ≈ .30–.40. The empirical symmetry
that resolves the Mischel critique — both sides of `B = f(P, E)` are ~
equally predictive.

Used in: README framing, playbook anchor for `(internal, sampling_config)`.

**Epstein, S. (1979). The stability of behavior: I. On predicting most of the people much of the time. *J. Personality and Social Psychology*, 37, 1097–1126.**
Aggregation across occasions raises consistency to r ≈ .70.

Used in: README footnote.

**Mischel, W., & Shoda, Y. (1995). A cognitive-affective system theory of personality. *Psychological Review*, 102(2), 246–268.**
The CAPS framework: personality is a stable network of cognitive-affective
units producing "if-situation-A-then-behavior-X" signatures. Maps
directly onto LLM behavior policies (prompt-conditioned).

Used in: README framing, playbook anchor for `(internal, reasoning_capability)`.

**Funder, D. C. (2006). Towards a resolution of the personality triad: Persons, situations, and behaviors. *Journal of Research in Personality*, 40(1), 21–34.**
Finalizes the interactionist position. The "personality triad" — persons,
situations, behaviors — is the unit. Used to frame the interactional
locus.

Used in: playbook anchor for `(interactional, system_prompt)`.

## Attribution theory

**Heider, F. (1958). *The Psychology of Interpersonal Relations.* Wiley.**
Original attribution theory. The internal/external distinction is
Heider's personal/impersonal causality, transposed.

Used in: README framing.

**Jones, E. E., & Davis, K. E. (1965). From acts to dispositions: The attribution process in person perception. *Advances in Experimental Social Psychology*, 2, 219–266.**
Correspondent inference theory. Names "correspondence bias."

Used in: forensic prompt for bias-mechanism diagnosis.

**Jones, E. E., & Harris, V. A. (1967). The attribution of attitudes. *Journal of Experimental Social Psychology*, 3(1), 1–24.**
Forced-essay paradigm: observers attribute attitude to writer even when
told position was assigned. Empirical demonstration of dispositional
over-attribution.

Used in: README framing.

**Kelley, H. H. (1967). Attribution theory in social psychology. *Nebraska Symposium on Motivation*, 15, 192–238.**
The covariation principle — causes are inferred from consensus,
distinctiveness, and consistency. **Direct mapping to the
:class:`CovarianceSignal` schema input.** Forensic mode prompts use
this explicitly.

Used in: `CovarianceSignal` schema, forensic locus-scoring prompt.

**Ross, L. (1977). The intuitive psychologist and his shortcomings. *Advances in Experimental Social Psychology*, 10, 173–220.**
Names the "fundamental attribution error" — the bias the entire
diagnostic exists to correct. Ross argued FAE is the "conceptual
bedrock" of social psychology.

Used in: system prompt's tie-break rationale, README's "why this
diagnostic" section.

**Gilbert, D. T., & Malone, P. S. (1995). The correspondence bias. *Psychological Bulletin*, 117(1), 21–38.**
Reviews mechanisms by which observers over-attribute: unaware of
constraints, unrealistic expectations, inflated categorization,
incomplete correction. **Direct mapping to the
:class:`GilbertMaloneMechanism` schema field.** Forensic mode prompts
the LLM to name which mechanism explains the team's misattribution.

Used in: `GilbertMaloneMechanism` enum, forensic bias-mechanism prompt.

**Storms, M. D. (1973). Videotape and the attribution process. *J. Personality and Social Psychology*, 27(2), 165–175.**
Actor-observer asymmetry. The diagnostic is a "videotape reversal"
that helps observers (engineers) see the situation.

Used in: README framing.

## Modern reformulation — Bandura

**Bandura, A. (1977). Self-efficacy: Toward a unifying theory of behavioral change. *Psychological Review*, 84, 191–215.**
First clear statement of P/E/B reciprocity.

Used in: playbook anchor for `(internal, rlhf)`.

**Bandura, A. (1978). The self system in reciprocal determinism. *American Psychologist*, 33(4), 344–358.**
Names reciprocal determinism.

Used in: README framing.

**Bandura, A. (1986). *Social Foundations of Thought and Action: A Social Cognitive Theory.* Prentice-Hall.**
Triadic reciprocal causation: P ↔ B ↔ E, each leg influencing the
other two. The Lewin diagnostic gives the instantaneous reading;
reciprocity is the temporal extension over multi-turn agent loops.

Used in: README framing, playbook anchor for `(interactional, rag_context)`.

## AI agent failure taxonomy

**Cemri, M., Pan, M. Z., Yang, S., et al. (2025). Why do multi-agent LLM systems fail? *NeurIPS Datasets & Benchmarks* / arXiv:2503.13657.**
The MAST taxonomy — 14 failure modes in 3 categories (specification &
system design; inter-agent misalignment; task verification & termination).
**Key finding: most multi-agent LLM failures arise from inter-agent
interactions and system design, not model limitations.** Direct empirical
support for the diagnostic's environmental tie-break.

Specific failure-mode anchors used in playbooks:
  - FM-1.3 step repetition → `(environmental, orchestration)`
  - FM-1.4 loss of conversation history → `(environmental, rag_context)`,
    `(internal, context_window_size)`
  - FM-1.5 unaware of termination conditions → `(environmental, orchestration)`
  - FM-2.1 conversation reset
  - FM-2.2 fail to ask for clarification → schema's `clarification_request` step type
  - FM-2.3 task derailment
  - FM-2.6 reasoning-action mismatch
  - FM-3.1 premature termination → `(environmental, orchestration)`
  - FM-3.2 no / incomplete verification → `(environmental, verification_step)`
  - FM-3.3 incorrect verification → `(environmental, downstream_consumers)`

Used in: system prompt's MAST mention, playbook anchors, schema's new
`FailureStep` types.

## Adjacent tooling for the comparison table

  - **Who&When benchmark (ICML 2025 Spotlight)** — 127 manually annotated
    multi-agent failure trajectories with ground-truth "who failed when."
  - **AgenTracer (arXiv 2509.03312)** — trajectory diagnosis tool.
  - **AgentRx (arXiv 2602.02475)** — automated agent-failure diagnosis.
  - **OWASP LLM Top 10 (2025)** — LLM07 System Prompt Leakage; LLM08
    Vector/Embedding Weaknesses (anchors the RAG-poisoning playbook).
  - **TruthfulQA / HaluEval** — output-quality evals, complementary to
    Lewin's attribution layer (not competitive).

## Citation hygiene

  - When a playbook cites a Lewin work, the year is given (`1936`, `1947`,
    `1951`) and the page is given when it's a directly-quotable passage
    (`Lewin 1936 p.12`).
  - When a playbook cites a MAST failure mode, the FM number is given
    (`FM-1.4`, `FM-3.2`) so readers can look up the full description in
    Cemri et al. 2025.
  - When a citation appears in a docstring, the full citation lives
    here in CITATIONS; the docstring just names author + year.

## How to add a citation

When adding a new playbook or schema dimension that draws on the
literature, append the citation to the appropriate section above, then
reference it from the new code site as `Author Year` (matching the
existing convention). Prefer primary sources; secondary reviews are
acceptable when the primary source is paywalled and not easily linkable.
