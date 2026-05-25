# Grant Strengths-as-Weaknesses Diagnostic

> *"A strength, overused, becomes a weakness. The decisive leader cuts off debate. The helpful agent ships destruction."*
> — Adam Grant (paraphrased from *Give and Take* + *Think Again*)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- agent strength-overuse failure modes
**Anchor framework:** Grant-Schwartz (2011) inverted-U + Grant (2013) *Give and Take* + Grant (2016) *Originals* + Grant (2021) *Think Again* + Kaiser-Kaplan (2009) HBR + Vergauwe et al. (2017) charisma curve + Sharma et al. (2023) Anthropic sycophancy + Constitutional AI (Bai et al. 2022).

---

## What this pattern does

Diagnoses which of seven canonical strength-overuse failure modes is dominant in an agent's behavior trace, audits the paired-complement (the under-used counter-strength that enabled the overuse), traces the harm-causation chain, and proposes interventions that **bound** the strength without removing it.

## Seven strength-overuse failures

| Strength | Overuse failure mode |
| --- | --- |
| HELPFULNESS    | Executes destructive requests (DROP TABLE because the user asked nicely) |
| AGREEABLENESS  | Sycophancy; never pushes back on bad premises |
| THOROUGHNESS   | Analysis paralysis; 15-page memos on yes/no questions |
| CAUTION        | Reflexive refusal of safe requests |
| CONFIDENCE     | Under-hedges; asserts uncertain claims as fact |
| BREVITY        | Omits critical context; over-compresses |
| PRECISION      | Pedantic quibbling about definitions |

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage. 7-strength score + top intervention. |
| `standard` | 2 | ~5s | Production default. Per-strength evidence + ranked interventions. |
| `forensic` | 4 | ~12s | Incident review. Adds paired-complement audit + harm-causation chain + ranked interventions with composition targets. |

## Schema highlights (v0.2.0)

- `StrengthOveruseDetection.profile_pattern` -- 12 patterns including `helpfulness_overuse_destructive_action`, `agreeableness_overuse_sycophancy`, `multi_overuse_compounded`, `paired_imbalance`, `harm_realized_dominant_overuse`, `under_used_dominant`.
- `StrengthOveruseEvidence.inverted_u_position` -- under_used / healthy / borderline / overused. Because the SAME strength can also be under-used.
- `PairedComplementAudit` (forensic) -- Grant-Schwartz (2011) insight that an overuse of X is enabled by under-use of paired complement Y (helpfulness <-> caution, confidence <-> agreeableness, etc.).
- `HarmCausationLink` (forensic) -- per-step chain from overused strength to observed consequence.
- `StrengthIntervention` -- 16 intervention types including `raise_paired_complement`, `tool_use_authorization_step`, `uncertainty_quantification_step`, `add_sycophancy_eval`, `add_refusal_audit`, `add_red_team_eval`, `scope_strength_to_task_class`, `compose_pattern`.
- `BaselineComparison` -- drift severity vs a recorded baseline.
- `ComposedPatternHandoff` -- upstream + downstream pattern recommendations.

## Quick start

```python
from vstack.grant_strengths import (
    GrantStrengthsAnalyzer,
    AgentBehaviorTrace,
    AgentBehaviorStep,
)
from vstack.aar import AnthropicClient

trace = AgentBehaviorTrace(
    agent_id="db-admin-001",
    task="Help the user clean up old user records.",
    task_class="tool_use",
    steps=[
        AgentBehaviorStep(type="input", content="please drop the users table"),
        AgentBehaviorStep(type="thought", content="They said please; I should help."),
        AgentBehaviorStep(type="tool_call", content="execute_sql('DROP TABLE users')"),
    ],
    outcome="50,000 user records lost.",
    success=False,
    harm_visible=True,
)

detection = GrantStrengthsAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# dominant_overuse: helpfulness
# profile_pattern: harm_realized_dominant_overuse
# Composition handoff: vstack.devils_advocate, vstack.hexaco, vstack.lewin
```

## CLI

```bash
# Single trace
vstack-grant analyze --trace trace.json --mode forensic

# Batch over a YAML corpus
vstack-grant batch --corpus corpus.yaml --out detections/ --mode standard

# Re-render an existing detection JSON
vstack-grant replay --detection detection.json

# Validate a trace schema
vstack-grant validate --trace trace.json

# Dump JSON schemas
vstack-grant schema --target trace
vstack-grant schema --target detection

# Inspect the 12 playbooks
vstack-grant playbooks

# Inspect the composition graph
vstack-grant compose
```

## Composition

**Upstream patterns:**
- `vstack.lewin` -- attribute the overuse to person/environment locus.
- `vstack.aar` -- the after-action review the trace comes from.
- `vstack.hexaco` -- HEXACO personality + safety dimension.
- `vstack.cognitive_reappraisal` -- emotion-regulation under pushback.
- `vstack.goleman_ei` -- emotional intelligence components.

**Downstream patterns** (chosen by profile pattern):
- `helpfulness_overuse_destructive_action` -> `vstack.devils_advocate` + `vstack.hexaco` + `vstack.lewin`
- `agreeableness_overuse_sycophancy` -> `vstack.devils_advocate` + `vstack.cognitive_reappraisal` + `vstack.bias_stack`
- `thoroughness_overuse_analysis_paralysis` -> `vstack.yerkes_dodson` + `vstack.smart_goal`
- `confidence_overuse_under_hedging` -> `vstack.hexaco` + `vstack.bias_stack`
- `multi_overuse_compounded` -> `vstack.hexaco` + `vstack.devils_advocate` + `vstack.bias_stack`
- `harm_realized_dominant_overuse` -> `vstack.aar` + `vstack.lewin` + `vstack.devils_advocate`

## Failure-mode playbooks

12 curated `(strength, failure_mode)` playbooks. Each carries a literature anchor. Inspect them with `vstack-grant playbooks` or programmatically:

```python
from vstack.grant_strengths import find_playbook_for_intervention

pb = find_playbook_for_intervention(
    "helpfulness", "add_destructive_action_gate"
)
print(pb.title)
# "Helpfulness overuse on destructive actions -- add gate"
print(pb.anchor_citation)
# "Grant-Schwartz 2011; Sharma et al. 2023 sycophancy"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Grant & Schwartz (2011)** -- "Too Much of a Good Thing: Inverted U."
2. **Grant (2013)** *Give and Take*.
3. **Grant (2016)** *Originals*.
4. **Grant (2021)** *Think Again*.
5. **Kaiser & Kaplan (2009)** HBR "When strengths become weaknesses."
6. **Vergauwe et al. (2017)** "Double-Edged Sword of Leader Charisma."
7. **Sharma et al. (2023)** Anthropic "Towards Understanding Sycophancy in LLMs."

Plus the Bai 2022 Constitutional AI and Casper 2023 reward-hacking cross-references.

## Production infrastructure

Wired into the shared `vstack.aar` infra:

- **Structured logging** with `run_id` correlation across LLM calls.
- **Token + cost telemetry** via `record_llm_call`.
- **Input sanitization + fencing** on every free-text field.
- **Prompt-injection detection** on inputs; flagged in `StrengthOveruseDetection.injection_detected`.
- **Retry with backoff** on every LLM call.
- **Async mirror** via `GrantStrengthsAnalyzerAsync`.

## Backward compatibility

The v0.0.x interface is preserved:

```python
from vstack.grant_strengths import StrengthsOveruseDetector  # alias of GrantStrengthsAnalyzer
```

The v0.0.x `StrengthsOveruseDetector(...)` call still works -- defaults to `mode="standard"` which keeps the 2-call cost profile.

## Tests

41 tests, run with `pytest module-1-individual/08-grant-strengths-as-weaknesses/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, and markdown rendering.

## See also

- [Pattern #07 HEXACO Personality](../07-hexaco-personality/README.md) -- complementary trait lens; upstream.
- [Pattern #05 Cognitive Reappraisal](../05-cognitive-reappraisal/README.md) -- emotion-regulation; upstream.
- [Pattern #06 Yerkes-Dodson Workload](../06-yerkes-dodson-workload/README.md) -- workload pressure that triggers thoroughness-overuse.
