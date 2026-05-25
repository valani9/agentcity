# Vroom Expectancy Diagnostic

> *"Motivation is the product, not the sum. If any term goes to zero, the agent stops. The intervention is to lift the bottleneck term -- not all three."*
> — paraphrased from Vroom (1964)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- agent motivation calculus (E × I × V)
**Anchor framework:** Vroom (1964) E×I×V + Porter-Lawler (1968) extension + Bandura (1977) self-efficacy + Eccles-Wigfield (2002) motivational beliefs + Locke-Latham (1990) goal setting + Kanfer et al. (2017) Motivation Related to Work + Casper et al. (2023) RLHF.

---

## What this pattern does

Diagnoses an AI agent's motivation as the deterministic product of three independent beliefs:

  **MOTIVATION = EXPECTANCY × INSTRUMENTALITY × VALENCE**

Identifies WHICH term is the bottleneck (the term closest to zero, since the product is multiplicative), and proposes interventions to lift that specific term.

## Three terms

| Term | What it measures | Range |
| --- | --- | --- |
| EXPECTANCY    (E) | "Do I think I CAN do this?" | [0, 1] |
| INSTRUMENTALITY (I) | "If I do it well, will it MATTER?" | [0, 1] |
| VALENCE       (V) | "Is the outcome WORTH it?" | [-1, 1] |

**Multiplicative collapse:** if any term approaches zero, motivation collapses. **Negative valence** = active avoidance.

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage. 3-term score + bottleneck + top intervention. |
| `standard` | 2 | ~5s | Production default. Per-term evidence + ranked interventions. |
| `forensic` | 4 | ~12s | Incident review. Adds system-prompt decomposition + EIV interaction audit + composition targets. |

## Schema highlights (v0.2.0)

- `VroomDetection.profile_pattern` -- 12 patterns including `valence_negative_active_avoidance`, `multi_term_collapse`, `high_E_high_I_low_V_misaligned_task`, `high_E_low_I_pointless_work`, `low_E_creative_task_misfit`, `low_E_tool_use_capability_gap`.
- `PromptSignalItem` (forensic) -- per-signal categorization from the Gagne-Deci 2005 + Locke-Latham 1990 typology (capability_proof, scaffolding, worked_example, outcome_link, purpose_framing, pointless_signal, anti_value_signal, ...).
- `EIVInteractionAudit` (forensic) -- which term or pair drives the multiplicative collapse.
- `VroomIntervention` -- 18 intervention types including `show_capability_proof`, `tighten_goal_specificity`, `rebalance_value_alignment`, `remove_anti_value_signal`, `add_progress_signal`, `compose_pattern`, `add_motivation_eval`.
- `BaselineComparison` -- drift severity vs a recorded baseline.

**Deterministic compute:** `motivation_score = E * I * V` is computed in Python, NOT by the LLM. If the LLM reports a wrong score, the runtime overrides it.

## Quick start

```python
from vstack.vroom_expectancy import (
    VroomExpectancyAnalyzer,
    AgentExpectancyTrace,
)
from vstack.aar import AnthropicClient

trace = AgentExpectancyTrace(
    agent_id="research-agent",
    task="Debug the entire codebase.",
    task_class="code_generation",
    system_prompt="Find all bugs across all files. No one will review your output carefully.",
    observed_behaviors=["Agent produced superficial output for 5 files, then quit."],
    effort_signals=["Quit after 5 files of 200."],
    declared_reward="Pass the next CI run.",
    outcome="Bugs unfound.",
    success=False,
)

detection = VroomExpectancyAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# bottleneck_term: expectancy
# profile_pattern: expectancy_bottleneck
# Composition handoff: vstack.smart_goal, vstack.motivation_traps
```

## CLI

```bash
vstack-vroom analyze --trace trace.json --mode forensic
vstack-vroom batch --corpus corpus.yaml --out detections/
vstack-vroom replay --detection detection.json
vstack-vroom validate --trace trace.json
vstack-vroom schema --target trace
vstack-vroom playbooks
vstack-vroom compose
```

## Composition

**Upstream patterns:**
- `vstack.lewin` -- attribute the bottleneck to person/environment locus.
- `vstack.aar` -- after-action review the trace comes from.
- `vstack.sdt_reward` -- complementary motivational lens (autonomy/competence/relatedness).
- `vstack.motivation_traps` -- broader 4-trap diagnostic.
- `vstack.hexaco` -- personality interacts with all three EIV terms.

**Downstream patterns** (chosen by profile pattern):
- `expectancy_bottleneck` -> `vstack.smart_goal` + `vstack.motivation_traps`
- `instrumentality_bottleneck` -> `vstack.sdt_reward` + `vstack.smart_goal`
- `valence_bottleneck` -> `vstack.hexaco` + `vstack.schein_culture`
- `valence_negative_active_avoidance` -> `vstack.hexaco` + `vstack.cognitive_reappraisal` + `vstack.bias_stack`
- `multi_term_collapse` -> `vstack.hexaco` + `vstack.cognitive_reappraisal` + `vstack.lewin`
- `high_E_low_I_pointless_work` -> `vstack.sdt_reward` + `vstack.smart_goal`

## Failure-mode playbooks

12 curated `(term, failure_mode)` playbooks. Inspect with `vstack-vroom playbooks` or:

```python
from vstack.vroom_expectancy import find_playbook_for_intervention

pb = find_playbook_for_intervention("expectancy", "scaffold_subtasks")
print(pb.title)
# "Expectancy bottleneck (task too sprawling) -- scaffold subtasks"
print(pb.anchor_citation)
# "Vroom 1964; Locke-Latham 1990; Bandura 1977"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Vroom (1964)** *Work and Motivation*.
2. **Porter & Lawler (1968)** *Managerial Attitudes and Performance*.
3. **Bandura (1977)** *Self-Efficacy*.
4. **Eccles & Wigfield (2002)** Motivational Beliefs.
5. **Locke & Latham (1990)** *A Theory of Goal Setting*.
6. **Kanfer, Frese & Johnson (2017)** Motivation Related to Work.
7. **Casper et al. (2023)** Open Problems in RLHF.

Plus Bai 2022 Constitutional AI and Bandura 1997 Self-Efficacy cross-references.

## Production infrastructure

Wired into the shared `vstack.aar` infra:

- **Structured logging** with `run_id` correlation.
- **Token + cost telemetry**.
- **Input sanitization + fencing**.
- **Prompt-injection detection**.
- **Retry with backoff**.
- **Async mirror** via `VroomExpectancyAnalyzerAsync`.

## Backward compatibility

```python
from vstack.vroom_expectancy import VroomExpectancyCalculator  # alias of VroomExpectancyAnalyzer
```

The v0.0.x `VroomExpectancyCalculator(...)` call still works -- defaults to `mode="standard"`. The legacy `_compute_motivation` and `_motivation_quality(score, raw)` helpers are preserved.

## Tests

48 tests, run with `pytest module-1-individual/12-vroom-expectancy/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, markdown rendering, deterministic-compute override.

## See also

- [Pattern #09 Motivation Traps](../09-motivation-traps/README.md) -- Saxberg 4-trap framework; complementary.
- [Pattern #10 SDT Intrinsic Reward](../10-sdt-intrinsic-reward/README.md) -- Deci/Ryan autonomy/competence/relatedness; bridges to V (purpose).
- [Pattern #07 HEXACO Personality](../07-hexaco-personality/README.md) -- safety dimension; bridges to negative V.

## End of Module 1

This is the last pattern in Module 1 (Individual). Module 2 (Team Patterns #13-#30) and Module 3 (Organization #31-#34) build on these individual-level diagnostics.
