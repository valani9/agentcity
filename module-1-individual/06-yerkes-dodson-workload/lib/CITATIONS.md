# Yerkes-Dodson Workload Diagnostic -- Literature Anchors

The Yerkes-Dodson Optimal Workload diagnostic is grounded in classical
arousal-performance psychology, three generations of Cognitive Load
Theory, and modern LLM-specific findings on context-window saturation.

## Primary anchors

### 1. Yerkes, R. M., & Dodson, J. D. (1908)

> *The relation of strength of stimulus to rapidity of habit-formation.*
> Journal of Comparative Neurology and Psychology, 18, 459-482.

The original inverted-U. Two principal findings:

1. Performance increases with arousal up to an optimal point and then
   decreases.
2. The location of the optimum depends on task complexity --
   **harder tasks peak at lower arousal**.

For agentic systems we model "arousal" as **pressure inputs**:
deadline_pressure, budget_pressure, retry_cap, error_visibility,
task_complexity. Complex tasks should be paired with lower
deadline/budget pressure; simple tasks tolerate (and may benefit from)
higher pressure.

### 2. Sweller, J. (1988, 1994, 2011) Cognitive Load Theory

> Sweller, J. (1988). *Cognitive load during problem solving: Effects
> on learning.* Cognitive Science, 12(2), 257-285.
>
> Sweller, J. (1994). *Cognitive load theory, learning difficulty, and
> instructional design.* Learning and Instruction, 4(4), 295-312.
>
> Sweller, J., Ayres, P., & Kalyuga, S. (2011).
> *Cognitive Load Theory.* Explorations in the Learning Sciences,
> Instructional Systems and Performance Technologies (Vol. 1).
> Springer.

CLT decomposes load into three components:

- **Intrinsic load** -- inherent to the task itself.
- **Extraneous load** -- imposed by how the task is presented; the
  *only* component that can be reduced through prompt/scaffolding
  design without reducing what is being learned.
- **Germane load** -- the productive load that builds schemas
  (useful learning).

The forensic mode of this diagnostic explicitly estimates all three
components and identifies the dominant component. Interventions like
`reduce_extraneous_load`, `remove_irrelevant_context`,
`promote_germane_load`, and `add_intrinsic_load_step_by_step` map
directly to CLT.

### 3. Kahneman, D. (1973)

> *Attention and Effort.* Prentice-Hall.

The capacity model: attention is a limited resource that depletes
under load. Modern LLMs show analogous behavior -- attention "spends"
on each token in the context, so context that exceeds useful capacity
degrades performance even when nominally below the window limit.
Kahneman's framing also justifies the
`interrupt_thrashing` playbook -- mid-task interrupts force
capacity reallocation and erode task performance.

### 4. Hancock, P. A., & Warm, J. S. (1989)

> *A dynamic model of stress and sustained attention.*
> Human Factors, 31(5), 519-537.

Dynamic adaptability framework. Two thresholds: comfort and
performance. Beyond the performance threshold, output collapses
sharply. Hancock-Warm gives us the language for **graceful zone
transitions** -- a system at the edge of optimal can absorb small
perturbations, but pushed past its threshold it falls catastrophically
into corner_cutting / freezing / refusing.

### 5. Eysenck, M. W., & Calvo, M. G. (1992) Attentional Control Theory

> *Anxiety and performance: The processing efficiency theory.*
> Cognition & Emotion, 6(6), 409-434.
>
> Eysenck, M. W., Derakshan, N., Santos, R., & Calvo, M. G. (2007).
> *Anxiety and cognitive performance: Attentional control theory.*
> Emotion, 7(2), 336-353.

Anxiety reduces processing **efficiency** before it reduces
**effectiveness**. The mapping for AI agents: stylistic pressure
(absurd deadlines, low retry caps, hostile reviewers) drives
"efficiency-first" failures -- corner-cutting, premature commitment,
narrow search -- well before global accuracy collapses. This is the
basis for the `freezing` and `corner_cutting` playbooks.

### 6. Hebb, D. O. (1955)

> *Drives and the C.N.S. (conceptual nervous system).*
> Psychological Review, 62(4), 243-254.

Arousal as a physiological precursor of performance. Provides the
classical neuroscience foundation for the inverted-U and clarifies why
the curve is **continuous** -- intermediate arousal states exist and
matter.

### 7. Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M.,
     Petroni, F., & Liang, P. (2024)

> *Lost in the Middle: How Language Models Use Long Contexts.*
> Transactions of the Association for Computational Linguistics, 12,
> 157-173. arXiv:2307.03172.

The key modern LLM finding: model performance on a question-answering
task degrades sharply when the relevant information is located in the
**middle** of a long context, even when the context is well below the
model's nominal window size. This is the modern analog of Kahneman's
capacity model and grounds the `context_saturation` profile pattern,
the `chunk_context` / `context_compression` interventions, and the
deterministic `saturation_ratio > 0.7` heuristic in
`_calibration.py`.

## Supporting anchors (modern AI-specific)

### Anthropic context-window research

> Anthropic. (2025).
> *Long-context performance degradation with prompt complexity.*
> Anthropic Technical Note.

Empirical reports that prompt structure has measurable cost above
~30-50% of nominal window utilization. We expose this through
the `context_size_tokens` / `context_window_size` pressure inputs and
the deterministic `_compute_context_saturation_from_pressure`
augmentation.

### LangGraph / CrewAI / AutoGen orchestration patterns

The `framework_overlays` in `_composition.py` link Yerkes-Dodson zone
diagnostics to per-framework recommendations (e.g. `vstack.grpi`
for CrewAI / AutoGen; `vstack.process_gain_loss` for SDK-style
single-agent runs). Framework choice substantially changes the
shape of the workload curve.

## How the diagnostic uses these anchors

| Anchor              | Where it appears                                                          |
| ------------------- | ------------------------------------------------------------------------- |
| Yerkes-Dodson 1908  | Three zones; distance_from_optimal; complexity-sensitive optimum.         |
| Sweller CLT         | `CognitiveLoadAnalysis`; forensic mode; CLT-component interventions.      |
| Kahneman 1973       | Interrupt-thrashing playbook; capacity rationale for context guards.      |
| Hancock-Warm 1989   | Severity bands; sharp drop past the performance threshold.                |
| Eysenck-Calvo 1992  | Freezing + corner-cutting playbooks; efficiency-vs-effectiveness framing. |
| Hebb 1955           | Continuity of the inverted-U; arousal-as-precursor framing.               |
| Liu et al. 2024     | `ContextSaturation`; lost-in-middle risk; chunk-context interventions.    |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
