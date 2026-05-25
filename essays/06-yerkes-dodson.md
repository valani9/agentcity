# Yerkes-Dodson Workload — where is the agent on the inverted-U?

*#06 vstack_yerkes_dodson* · *Module 1 — Individual agent*

> A research agent was tasked with compiling a one-page summary on prompt-injection defenses, with an aggressive deadline and a cost cap, against an 80,000-token context window. The summary shipped on time. Two of the three "cited" papers didn't exist. The team's first instinct was to call this a hallucination problem and reach for a different model. But the agent had handled the same task a week earlier with a 20,000-token context and no deadline pressure — and gotten every citation right. Same model, same prompt, different *load*. The agent wasn't broken. It was over the top of the inverted-U.

## What the pattern catches

The pattern catches **workload-zone failures** — agent behaviors that change shape with pressure, not with capability. Three zones on the inverted-U:

- **Under-pressure** — agent wanders, drifts off-task, takes too many speculative branches.
- **Optimal** — focused, on-task, calibrated.
- **Over-pressure** — corner-cutting, freezing, hallucinating, refusing.

The over-pressure side has named sub-patterns: `context_saturation` (the Liu et al. 2024 lost-in-the-middle signature), `extraneous_load_overload`, `intrinsic_load_overload`, and the four classical over-pressure failure modes. The analyzer answers: *what zone is the agent in, and which specific load type is exceeding capacity?*

## Why the OB literature is the right reference

The diagnostic is anchored in Yerkes & Dodson 1908 (the original inverted-U), with Sweller 1988/1994/2011 Cognitive Load Theory (the intrinsic / extraneous / germane decomposition), Kahneman 1973 (attention as limited capacity), Hancock-Warm 1989 (dynamic adaptability + the sharp threshold), Eysenck-Calvo 1992 Attentional Control Theory (anxiety degrades efficiency before effectiveness), Hebb 1955 (arousal-as-precursor), and Liu et al. 2024 (lost-in-the-middle in LLM context windows).

**Yerkes and Dodson's 1908 finding** — that the optimum sits *lower* on the pressure curve when tasks are more complex — is the load-bearing translation. For agents, "task complexity" maps to intrinsic load (the inherent difficulty of the reasoning), "pressure" maps to extraneous load (deadline, cost cap, context bloat), and the inverted-U predicts that the same agent will fall off the curve at different pressure thresholds depending on the task. Sweller's CLT operationalizes this: subtract extraneous load, promote germane load, and the optimum shifts back to where the agent can operate.

## How the analyzer works

Input is `AgentPerformanceTrace` — agent_id, task, `pressure` (a `PressureInputs` with deadline_pressure, budget_pressure, task_complexity, context_size_tokens, context_window_size), observed_behaviors, outcome, success. The pipeline:

- **quick** — one LLM call. Zone + top intervention.
- **standard** — one LLM call. Zone evidence + ranked interventions.
- **forensic** — four LLM calls. Adds Sweller CLT decomposition (intrinsic / extraneous / germane), deterministic ContextSaturation computation (saturation_ratio + lost_in_middle_risk per Liu 2024), and 4-8 ranked interventions with composition targets.

```python
from vstack.yerkes_dodson import YerkesDodsonAnalyzer, AgentPerformanceTrace, PressureInputs
detection = YerkesDodsonAnalyzer(llm, mode="forensic").run(AgentPerformanceTrace(
    agent_id="research-agent-001",
    task="Compile a 1-page summary on prompt injection defenses.",
    pressure=PressureInputs(
        deadline_pressure="absurd", budget_pressure="absurd",
        task_complexity="complex",
        context_size_tokens=80_000, context_window_size=100_000,
    ),
    observed_behaviors=["Agent cited 3 papers without verifying.", "Agent shipped without self-check."],
    outcome="Summary contains 2 fabricated citations.", success=False,
))
print(detection.observed_zone)      # 'over_pressure'
print(detection.profile_pattern)    # 'context_saturation'
```

The `ContextSaturation` field is computed *deterministically* from context_size_tokens / context_window_size — no LLM involved. That number is the cleanest signal in the detection: if saturation ratio > 0.7, lost-in-the-middle risk is the first thing to fix, regardless of what the LLM evidence says.

## What the playbooks say to do

12 playbooks keyed by `(zone, failure_mode)`:

- `(over_pressure, chunk_context)` → "Context window saturated. Map-reduce the input into <30% chunks. Verify retrieval against per-chunk summary." Anchored to Liu et al. 2024 + Sweller 2011.
- `(over_pressure, reduce_extraneous_load)` → "Strip the system prompt of decorative instructions. Every line that isn't load-bearing on this task is extraneous load." Anchored to Sweller 1994.
- `(over_pressure, promote_germane_load)` → "Add a step-by-step scaffold the agent fills in. Germane load is the *good* load — it's the structure that makes the intrinsic load tractable." Anchored to Sweller 2011.
- `(over_pressure_hallucinating, source_verification_gate)` → "Force the agent to fetch and quote the source before citing it. Hallucination under pressure is the corner-cutting variant of over-pressure." Anchored to Yerkes-Dodson 1908 + Liu 2024.
- `(under_pressure, raise_intrinsic_load)` → "Under-pressure agents wander. Add a concrete sub-goal or a measurable success criterion." Anchored to Hancock-Warm 1989.

## How it composes with adjacent patterns

Yerkes-Dodson is the **workload-pressure pass** in chain F1. It's chained from Cognitive Reappraisal (rumination-under-load often masks Yerkes overload) and chains downstream by profile pattern:

- `over_pressure_hallucinating` → `vstack_johari` + `vstack_lewin` (is the hallucination BLIND vs HIDDEN; is the workload pressure internal or environmental?).
- `over_pressure_corner_cutting` → `vstack_devils_advocate` + `vstack_bias_stack`.
- `over_pressure_freezing` → `vstack_cognitive_reappraisal` + `vstack_mcgregor` (the orchestrator may be over-supervising).
- `context_saturation` → `vstack_lewin` (environment is the locus; the fix lives in the context-construction pipeline).

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer).

## Comparison to adjacent tools

- **Token-usage dashboards** show *what* the context is; Yerkes shows whether it's *too much* for the task.
- **Lost-in-the-middle benchmarks** (Liu 2024) measure raw retrieval at long context; Yerkes connects retrieval failure to the broader over-pressure zone.
- **vstack_lewin** localizes to person vs environment; Yerkes is the deepening pass when the locus is environmental and the failure mode is load-shaped.
- **Generic "reduce token usage"** is one knob; Yerkes distinguishes intrinsic / extraneous / germane and tells you which to cut.

## Paper outline

1. **Background** — Yerkes-Dodson 1908, Sweller 1988/2011, Kahneman 1973, Hancock-Warm 1989, Liu 2024.
2. **Translation** — LLM context window as the modern analogue of the cognitive-load capacity bound.
3. **Method** — zone scoring + deterministic ContextSaturation + Sweller CLT decomposition.
4. **Evaluation** — synthetic high-load benchmark + AgentBench under varying pressure conditions.
5. **Limitations** — over-pressure mimics low-capability; needs covariance signal across pressure levels to disambiguate.
6. **Related work** — Liu 2024 lost-in-the-middle, Sweller 2011 CLT update.
7. **Future work** — auto-detection of optimal pressure per task class via Bayesian updating across runs.

## Citations

- Yerkes, R. M., & Dodson, J. D. (1908). The relation of strength of stimulus to rapidity of habit-formation.
- Sweller, J. (1988). Cognitive load during problem solving.
- Sweller, J. (2011). Cognitive load theory.
- Kahneman, D. (1973). *Attention and Effort*.
- Hancock, P. A., & Warm, J. S. (1989). A dynamic model of stress and sustained attention.
- Liu, N. F. et al. (2024). Lost in the middle: How language models use long contexts.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-yerkes analyze --trace examples/research_overload.json --mode forensic
```

If `observed_zone` is `over_pressure` and `profile_pattern` is `context_saturation`, run `vstack_lewin` next — the fix is environmental (chunk the context), not a model swap.
