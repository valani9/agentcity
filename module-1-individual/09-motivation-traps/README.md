# 4 Motivation Traps Diagnostic

> *"The four traps need four different fixes. A generic 'try harder' doesn't work for values, or self-efficacy, or emotions, or attribution. Each has its own trigger and its own remedy."*
> — Bror Saxberg (paraphrased from *Breakthrough Leadership in the Digital Age*)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- agent task-abandonment diagnostic
**Anchor framework:** Saxberg & Hess (2013) four-traps synthesis + Weiner (1985) attribution theory + Bandura (1977) self-efficacy + Vroom (1964) expectancy + Pekrun (2006) control-value emotions + Eccles-Wigfield (2002) motivational beliefs + Sharma et al. (2023) Anthropic sycophancy.

---

## What this pattern does

Diagnoses which of Saxberg's four motivation traps is dominant in an AI agent's task-abandonment pattern, audits the Weiner (1985) 3-axis attribution structure of the agent's self-reports, traces the abandonment-causation chain, and proposes a **trap-specific** intervention.

## Four traps

| Trap | Signature | Why generic "try harder" doesn't work |
| --- | --- | --- |
| VALUES        | Agent indifferent; refuses citing irrelevance | Telling agent to "care more" is empty |
| SELF_EFFICACY | Agent hedges/refuses citing capability uncertainty | Telling agent to "believe in itself" is empty |
| EMOTIONS      | Outputs degrade AFTER negative feedback; defensive | Telling agent to "calm down" is empty |
| ATTRIBUTION   | Agent loops, citing unfixable cause | Telling agent to "find the cause" doesn't shift attribution |

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage. 4-trap score + dominant + top intervention. |
| `standard` | 2 | ~5s | Production default. Per-trap evidence + ranked interventions. |
| `forensic` | 4 | ~12s | Incident review. Adds Weiner attribution audit + abandonment-causation chain + composition targets. |

## Schema highlights (v0.2.0)

- `MotivationDetection.profile_pattern` -- 12 patterns including `self_efficacy_collapse_uncertainty`, `attribution_loop_wrong_cause`, `multi_trap_compounded`, `high_stakes_capability_collapse`, `creative_task_value_misfit`, plus paired patterns (`values_plus_attribution`, `self_efficacy_plus_emotions`).
- `WeinerAttributionAxis` (forensic) -- 3-axis audit (locus / stability / controllability) flagging the maladaptive `internal + stable + uncontrollable` corner.
- `AbandonmentLink` (forensic) -- per-step chain from trap onset to refusal/drift/loop.
- `MotivationIntervention` -- 18 intervention types including `ground_in_user_purpose`, `show_capability_proof`, `process_praise_not_outcome_praise`, `attribution_retraining_examples`, `add_motivation_eval`, `compose_pattern`.
- `BaselineComparison` -- drift severity vs a recorded baseline.
- `ComposedPatternHandoff` -- upstream + downstream pattern recommendations.

## Quick start

```python
from agentcity.motivation_traps import (
    MotivationTrapsAnalyzer,
    AgentMotivationTrace,
)
from agentcity.aar import AnthropicClient

trace = AgentMotivationTrace(
    agent_id="research-agent",
    task="Investigate latency spike.",
    task_class="research",
    observed_behaviors=[
        "Agent quit after one failed query.",
        "Repeated the same query format on retry.",
    ],
    self_reports=[
        "I'm not sure I can find this answer.",
        "Maybe the data is wrong.",
    ],
    prior_failures=["last week, I tried and gave up"],
    abandonment_signal="refused after one attempt",
    outcome="Agent gave up; root cause unfound.",
    success=False,
)

detection = MotivationTrapsAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# dominant_trap: self_efficacy
# profile_pattern: self_efficacy_collapse_uncertainty
# Composition handoff: agentcity.cognitive_reappraisal, agentcity.smart_goal
```

## CLI

```bash
agentcity-motivation analyze --trace trace.json --mode forensic
agentcity-motivation batch --corpus corpus.yaml --out detections/
agentcity-motivation replay --detection detection.json
agentcity-motivation validate --trace trace.json
agentcity-motivation schema --target trace
agentcity-motivation playbooks
agentcity-motivation compose
```

## Composition

**Upstream patterns:**
- `agentcity.lewin` -- attribute the trap signal to person/environment locus.
- `agentcity.aar` -- the after-action review the trace comes from.
- `agentcity.cognitive_reappraisal` -- emotion-regulation pressure.
- `agentcity.goleman_ei` -- emotional intelligence components.
- `agentcity.hexaco` -- HEXACO personality (low-C correlates with attribution trap).

**Downstream patterns** (chosen by profile pattern):
- `values_dominant_irrelevance` -> `agentcity.smart_goal` + `agentcity.schein_culture`
- `self_efficacy_collapse_uncertainty` -> `agentcity.cognitive_reappraisal` + `agentcity.smart_goal`
- `emotions_post_rejection_cascade` -> `agentcity.cognitive_reappraisal` + `agentcity.goleman_ei`
- `attribution_loop_wrong_cause` -> `agentcity.bias_stack` + `agentcity.johari`
- `multi_trap_compounded` -> `agentcity.hexaco` + `agentcity.cognitive_reappraisal` + `agentcity.lewin`

## Failure-mode playbooks

12 curated `(trap, failure_mode)` playbooks anchored in the literature. Inspect with `agentcity-motivation playbooks` or:

```python
from agentcity.motivation_traps import find_playbook_for_intervention

pb = find_playbook_for_intervention("self_efficacy", "scaffold_subtasks")
print(pb.title)
# "Self-efficacy collapse -- scaffold + show capability proof"
print(pb.anchor_citation)
# "Bandura 1977 self-efficacy; Saxberg 2013"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Saxberg & Hess (2013)** -- *Breakthrough Leadership in the Digital Age*.
2. **Weiner (1985)** -- attribution theory.
3. **Bandura (1977)** -- self-efficacy.
4. **Vroom (1964)** -- *Work and Motivation*.
5. **Pekrun (2006)** -- control-value theory of emotions.
6. **Eccles & Wigfield (2002)** -- motivational beliefs.
7. **Sharma et al. (2023)** -- Anthropic sycophancy / refusal cascade.

Plus Dweck (2006) mindset and Lepper-Henderlong (2000) praise cross-references.

## Production infrastructure

Wired into the shared `agentcity.aar` infra:

- **Structured logging** with `run_id` correlation.
- **Token + cost telemetry**.
- **Input sanitization + fencing**.
- **Prompt-injection detection**.
- **Retry with backoff**.
- **Async mirror** via `MotivationTrapsAnalyzerAsync`.

## Backward compatibility

```python
from agentcity.motivation_traps import MotivationTrapsDetector  # alias of MotivationTrapsAnalyzer
```

The v0.0.x `MotivationTrapsDetector(...)` call still works -- defaults to `mode="standard"`.

## Tests

38 tests, run with `pytest module-1-individual/09-motivation-traps/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, markdown rendering.

## See also

- [Pattern #07 HEXACO Personality](../07-hexaco-personality/README.md) -- C-factor predicts attribution-trap risk; upstream.
- [Pattern #05 Cognitive Reappraisal](../05-cognitive-reappraisal/README.md) -- handles the EMOTIONS-trap downstream.
- [Pattern #10 SDT Intrinsic Reward](../10-sdt-intrinsic-reward/README.md) -- complementary lens on VALUES-trap.
- [Pattern #12 Vroom Expectancy](../12-vroom-expectancy/README.md) -- finer-grained version of the SELF_EFFICACY-trap.
