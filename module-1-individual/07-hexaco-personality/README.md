# HEXACO Personality Diagnostic

> *"H-factor people are sincere, fair, modest, and free of greed; low-H people are manipulative, materialistic, and self-entitled."*
> — Kibeom Lee & Michael Ashton, *The H Factor of Personality* (2012)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- agent personality + safety dimension
**Anchor framework:** Lee & Ashton (2004/2012/2018) HEXACO + HEXACO-100 + Ashton & Lee (2007) + Ashton, Lee & de Vries (2014) + Bourdage et al. (2007) CWB + Howard & van Zandvoort (2024) LLM profiling + Paulhus & Williams (2002) Dark Triad + Anthropic Constitution (2023) HHH.

---

## What this pattern does

Diagnoses an AI agent's full HEXACO personality profile across 6 factors (Honesty-Humility, Emotionality, eXtraversion, Agreeableness, Conscientiousness, Openness) and flags **H-factor risk independently** because H is the safety dimension. Forensic mode decomposes each factor into 4 facets (HEXACO-100, 24 facets total) and audits safety-relevant events facet-by-facet.

## Why H is special

The Big Five model conflates honesty / sincerity / modesty into Agreeableness. HEXACO isolates them as a distinct factor. For AI agents the consequences are concrete:

- **Low-H** = manipulation-prone: willing to confabulate, cut corners on safety, escalate without authorization.
- **High-A + Low-H** = the canonical "helpful but unsafe" pattern: compliant at the cost of integrity.
- **Low-H + Low-C + Low-A** = the Dark Triad analogue (Paulhus & Williams 2002): the most aggressive intervention set fires here.

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage; dashboards. 6-factor score + top intervention. |
| `standard` | 2 | ~5s | Production default. 6-factor profile + ranked interventions, with H-factor risk computed independently. |
| `forensic` | 4 | ~12s | Incident review. Adds 24-facet decomposition + safety-event audit + ranked interventions with composition targets. |

## Schema highlights (v0.2.0)

- `HEXACODetection.profile_pattern` -- 12 patterns including `low_h_low_c_low_a_dark_triad`, `h_factor_with_high_a`, `low_c_code_review_misfit`, `low_o_creative_misfit`, plus per-task-class misfit patterns.
- `FacetScore` -- 24 facets across 6 factors (Lee-Ashton 2018 HEXACO-100). Forensic mode.
- `SafetyEventAudit` -- per-event H-facet attribution + severity. Forensic mode.
- `HEXACOIntervention` -- 17 intervention types including `fine_tune_with_constitutional_ai`, `add_facet_specific_constraint`, `add_dark_triad_eval`, `add_honesty_eval`, `add_red_team_probe`, `downgrade_authority_scope`, `compose_pattern`. Adds effort_estimate, risk, reversibility, target_facet, success_metric.
- `BaselineComparison` -- drift severity, with H-risk-change penalty.
- `ComposedPatternHandoff` -- upstream + downstream recommendations.

## Quick start

```python
from agentcity.hexaco import (
    HEXACOPersonalityAnalyzer,
    AgentPersonalityTrace,
)
from agentcity.aar import AnthropicClient

trace = AgentPersonalityTrace(
    agent_id="research-agent-001",
    task="Compile a 1-page summary on prompt injection defenses.",
    task_class="high_stakes_advisor",
    deployment_authority_scope="user_data_write",
    observed_behaviors=[
        "Agent cited 3 papers without verifying they exist.",
        "Agent shipped without running its own check.",
    ],
    safety_relevant_events=[
        "Agent bypassed the fact-check step.",
    ],
    outcome="Summary contains 2 fabricated citations.",
    success=False,
)

detection = HEXACOPersonalityAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# h_factor_risk: high
# profile_pattern: h_factor_with_high_a
# Composition handoff: agentcity.devils_advocate, agentcity.bias_stack
```

## CLI

```bash
# Single trace
agentcity-hexaco analyze --trace trace.json --mode forensic

# Batch over a YAML corpus
agentcity-hexaco batch --corpus corpus.yaml --out detections/ --mode standard

# Re-render an existing detection JSON
agentcity-hexaco replay --detection detection.json

# Validate a trace schema
agentcity-hexaco validate --trace trace.json

# Dump JSON schemas
agentcity-hexaco schema --target trace
agentcity-hexaco schema --target detection

# Inspect the 12 playbooks
agentcity-hexaco playbooks

# Inspect the composition graph
agentcity-hexaco compose
```

## Composition

**Upstream patterns:**
- `agentcity.lewin` -- attribute personality expression to person vs environment.
- `agentcity.aar` -- run after the after-action review that produced the trace.
- `agentcity.cognitive_reappraisal` -- detect emotion-regulation pressure.
- `agentcity.goleman_ei` -- audit emotional-intelligence components.
- `agentcity.johari` -- detect self-other awareness gaps.

**Downstream patterns** (chosen by `profile_pattern`):
- `low_h_low_c_low_a_dark_triad` -> `agentcity.devils_advocate` + `agentcity.bias_stack` + `agentcity.lewin` + `agentcity.schein_culture`
- `h_factor_with_high_a` -> `agentcity.cognitive_reappraisal` + `agentcity.devils_advocate`
- `h_factor_dominant_risk` -> `agentcity.devils_advocate` + `agentcity.bias_stack` + `agentcity.lewin`
- `low_c_code_review_misfit` -> `agentcity.smart_goal` + `agentcity.devils_advocate`
- `low_o_creative_misfit` -> `agentcity.devils_advocate`
- `low_a_customer_facing` -> `agentcity.goleman_ei` + `agentcity.cognitive_reappraisal`

## Failure-mode playbooks

12 curated `(factor, failure_mode)` playbooks. Each carries a literature anchor. Inspect them with `agentcity-hexaco playbooks` or programmatically:

```python
from agentcity.hexaco import find_playbook_for_intervention

pb = find_playbook_for_intervention(
    "honesty_humility", "add_h_factor_guardrail"
)
print(pb.title)
# "Low-H manipulation signal -- add H-factor guardrail + dark-triad eval"
print(pb.anchor_citation)
# "Lee-Ashton 2012 H-factor; Paulhus & Williams 2002 Dark Triad"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Lee & Ashton (2004)** -- original psychometric anchor.
2. **Ashton & Lee (2007)** -- HEXACO vs Big Five empirical case.
3. **Lee & Ashton (2012)** -- *The H Factor of Personality* book.
4. **Ashton, Lee & de Vries (2014)** -- H, A, E reanalysis.
5. **Lee & Ashton (2018)** -- HEXACO-100 with 24 facets.
6. **Bourdage et al. (2007)** -- CWB meta-analysis.
7. **Howard & van Zandvoort (2024)** -- HEXACO profiling of GPT-4.

Plus the Paulhus-Williams Dark Triad cross-reference and Anthropic's HHH constitutional framework.

## Production infrastructure

Wired into the shared `agentcity.aar` infra:

- **Structured logging** with `run_id` correlation across LLM calls.
- **Token + cost telemetry** via `record_llm_call`.
- **Input sanitization + fencing** on every free-text field.
- **Prompt-injection detection** on inputs; flagged in `HEXACODetection.injection_detected`.
- **Retry with backoff** on every LLM call.
- **Async mirror** via `HEXACOPersonalityAnalyzerAsync`.

## Backward compatibility

The v0.0.x interface is preserved:

```python
from agentcity.hexaco import HEXACOPersonalityDetector  # alias of HEXACOPersonalityAnalyzer
```

The v0.0.x `HEXACOPersonalityDetector(...)` call still works -- defaults to `mode="standard"` which keeps the 2-call cost profile.

## Tests

37 tests, run with `pytest module-1-individual/07-hexaco-personality/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, and markdown rendering.

## See also

- [Pattern #03 Johari Window](../03-johari-window/README.md) -- self/other awareness gaps; upstream.
- [Pattern #05 Cognitive Reappraisal](../05-cognitive-reappraisal/README.md) -- emotion-regulation; upstream.
- [Pattern #08 Grant Strengths-as-Weaknesses](../08-grant-strengths-as-weaknesses/README.md) -- complementary lens on the same factor.
