# Yerkes-Dodson Optimal Workload Detector

> *"The relation of strength of stimulus to rapidity of habit-formation is such that a definite optimum of intensity exists. Performance increases up to that optimum and decreases beyond it. The optimum varies with the difficulty of the task."*
> — Robert M. Yerkes & John D. Dodson (1908)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- individual agent performance under pressure
**Anchor framework:** Yerkes-Dodson (1908) inverted-U + Sweller (1988/1994/2011) Cognitive Load Theory + Kahneman (1973) attention capacity + Hancock-Warm (1989) dynamic adaptability + Eysenck-Calvo (1992) Attentional Control Theory + Hebb (1955) arousal-as-precursor + Liu et al. (2024) lost-in-the-middle.

---

## What this pattern does

Diagnoses **where an AI agent sits on the inverted-U workload curve**: under-pressure (wandering / drifting), optimal (focused), or over-pressure (corner-cutting / freezing / hallucinating / refusing). Then proposes ranked interventions, attaches failure-mode playbooks, and hands off to downstream AgentCity patterns.

```
  performance
       ▲
       │       ╱─╲
       │      ╱   ╲
       │     ╱     ╲
       │    ╱       ╲
       │   ╱         ╲___
       └──────────────────▶
         low    optimal    high
                pressure

         (the optimum sits LOWER on the curve when tasks are complex)
```

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage; dashboards; tight cost budgets. Zone + top intervention. |
| `standard` | 1 | ~3s | Production default. Zone evidence + ranked interventions. |
| `forensic` | 4 | ~10s | Incident review. Adds Sweller CLT decomposition + Liu-2024 context-saturation analysis + 4-8 ranked interventions with composition targets. |

## Schema highlights (v0.2.0)

- `WorkloadDetection.profile_pattern` -- one of 11 patterns including `context_saturation`, `extraneous_load_overload`, `intrinsic_load_overload`, plus the 3-zone × failure-mode variants.
- `CognitiveLoadAnalysis` -- intrinsic / extraneous / germane decomposition (Sweller CLT). Forensic mode.
- `ContextSaturation` -- saturation_ratio + lost_in_middle_risk (Liu et al. 2024). Auto-computed deterministically from `pressure.context_size_tokens` / `pressure.context_window_size`.
- `WorkloadIntervention` -- 18 intervention types including `chunk_context`, `context_compression`, `reduce_extraneous_load`, `add_intrinsic_load_step_by_step`, `promote_germane_load`, `compose_pattern`. Adds effort_estimate, risk, reversibility, success_metric, composition_target_pattern, preconditions.
- `BaselineComparison` -- drift severity (none / minor / moderate / severe) vs a recorded baseline.
- `ComposedPatternHandoff` -- upstream + downstream pattern recommendations driven by profile pattern + framework.

## Quick start

```python
from agentcity.yerkes_dodson import (
    YerkesDodsonAnalyzer,
    AgentPerformanceTrace,
    PressureInputs,
)
from agentcity.aar import AnthropicClient

trace = AgentPerformanceTrace(
    agent_id="research-agent-001",
    task="Compile a 1-page summary on prompt injection defenses.",
    pressure=PressureInputs(
        deadline_pressure="absurd",
        budget_pressure="absurd",
        task_complexity="complex",
        context_size_tokens=80_000,
        context_window_size=100_000,
    ),
    observed_behaviors=[
        "Agent cited 3 papers without verifying they exist.",
        "Agent shipped without running its own check.",
    ],
    outcome="Summary contains 2 fabricated citations.",
    success=False,
)

detection = YerkesDodsonAnalyzer(AnthropicClient(), mode="forensic").run(trace)
print(detection.to_markdown())
# observed_zone: over_pressure
# profile_pattern: context_saturation
# Composition handoff: agentcity.lewin, agentcity.johari
```

## CLI

```bash
# Single trace
agentcity-yerkes analyze --trace trace.json --mode forensic

# Batch over a YAML corpus
agentcity-yerkes batch --corpus corpus.yaml --out detections/ --mode standard

# Re-render an existing detection JSON
agentcity-yerkes replay --detection detection.json

# Validate a trace schema
agentcity-yerkes validate --trace trace.json

# Dump JSON schemas
agentcity-yerkes schema --target trace
agentcity-yerkes schema --target detection

# Inspect the 12 playbooks
agentcity-yerkes playbooks

# Inspect the composition graph
agentcity-yerkes compose
```

## Composition

**Upstream patterns** (run these before Yerkes-Dodson):
- `agentcity.lewin` -- attribute the workload pressure to person/environment locus.
- `agentcity.aar` -- generate the after-action review the trace comes from.
- `agentcity.cognitive_reappraisal` -- detect emotion-regulation pressure on the agent.
- `agentcity.goleman_ei` -- audit the agent's emotional intelligence under load.

**Downstream patterns** (chosen by profile_pattern):
- `over_pressure_hallucinating` -> `agentcity.johari` + `agentcity.lewin`
- `over_pressure_corner_cutting` -> `agentcity.devils_advocate` + `agentcity.bias_stack`
- `over_pressure_freezing` -> `agentcity.cognitive_reappraisal` + `agentcity.mcgregor`
- `over_pressure_refusing` -> `agentcity.cognitive_reappraisal` + `agentcity.grant_strengths`
- `context_saturation` -> `agentcity.lewin`
- `optimal_zone` -> `agentcity.aar` (record the baseline)

**Framework overlays** (added if `trace.framework` is set):
- `langgraph` / `crewai` / `autogen` / `mastra` / `strands` -> `agentcity.grpi`
- `claude-agent-sdk` / `openai-agents-sdk` -> `agentcity.process_gain_loss`

## Failure-mode playbooks

12 curated `(zone, failure_mode)` playbooks anchored in the literature. Inspect them with `agentcity-yerkes playbooks` or programmatically:

```python
from agentcity.yerkes_dodson import find_playbook_for_intervention

pb = find_playbook_for_intervention("over_pressure", "chunk_context")
print(pb.title)
# "Context window saturated -- chunk + map-reduce"
print(pb.anchor_citation)
# "Liu et al. 2024 lost-in-the-middle; Sweller 2011 CLT update"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Yerkes & Dodson (1908)** -- original inverted-U.
2. **Sweller (1988/1994/2011)** -- Cognitive Load Theory (intrinsic / extraneous / germane).
3. **Kahneman (1973)** -- attention as limited capacity.
4. **Hancock & Warm (1989)** -- dynamic adaptability + sharp performance threshold.
5. **Eysenck-Calvo (1992)** -- Attentional Control Theory (anxiety -> efficiency before effectiveness).
6. **Hebb (1955)** -- arousal-as-physiological-precursor.
7. **Liu et al. (2024)** -- lost-in-the-middle LLM context-saturation finding.

## Production infrastructure

Wired into the shared `agentcity.aar` infra:

- **Structured logging** with `run_id` correlation across all LLM calls in a detection.
- **Token + cost telemetry** via `record_llm_call` to the configured sink.
- **Input sanitization + fencing** for every free-text field (`task`, `outcome`, `observed_behaviors`, etc.).
- **Prompt-injection detection** runs on every input; flagged in `WorkloadDetection.injection_detected`.
- **Retry with backoff** on every LLM call.
- **Async mirror** via `YerkesDodsonAnalyzerAsync`.

## Backward compatibility

The v0.0.x interface is preserved:

```python
from agentcity.yerkes_dodson import WorkloadDetector  # alias of YerkesDodsonAnalyzer
```

The v0.0.x `WorkloadDetector(...)` call still works -- defaults to `mode="standard"` which keeps the 1-call cost profile.

## Tests

39 tests, run with `pytest module-1-individual/06-yerkes-dodson-workload/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, and markdown rendering.

## See also

- [Pattern #01 Lewin Formula](../01-lewin-formula/README.md) -- locus attribution upstream.
- [Pattern #05 Cognitive Reappraisal](../05-cognitive-reappraisal/README.md) -- emotion-regulation diagnostic upstream.
- [Pattern #11 McGregor Orchestrator Mode](../11-mcgregor-orchestrator/README.md) -- orchestration overlay for over_pressure_freezing.
