# McGregor Theory X/Y Orchestrator Mode Diagnostic

> *"The right level of oversight is not a preference. It is a contingent decision based on the properties of the task: its risk, its reversibility, the capability of the worker, and the regulatory exposure."*
> — paraphrased from McGregor (1966) + Eisenhardt (1989)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- orchestrator-mode + sub-agent oversight
**Anchor framework:** McGregor (1960, 1966) Theory X/Y + Schein (1990) culture + Pfeffer-Salancik (1978) contingency + Argyris (1957) over-supervision pathology + Eisenhardt (1989) agency theory + Wang et al. (2023) cooperative LLM agents + Anthropic Computer Use (2024).

---

## What this pattern does

Diagnoses whether an orchestrator (LangGraph state machine / CrewAI crew / AutoGen group chat / SDK delegation pattern) is running its sub-agents in Theory X (tight oversight), Theory Y (loose oversight), or Hybrid mode -- and whether that observed mode matches the **optimal** mode for the task's properties.

## Three modes

| Mode | Pattern | When optimal |
| --- | --- | --- |
| THEORY X | Every step approved; tight oversight; trust low | High-risk + irreversible + unproven agent + regulated workflow |
| THEORY Y | Broad goals + budget; loose oversight; trust high | Low-risk + reversible + proven agent + creative / exploratory |
| HYBRID  | Per-step decision based on risk + reversibility | Mixed-risk pipelines; large action surface |

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage. Observed + optimal mode + top intervention. |
| `standard` | 2 | ~5s | Production default. Mode indicators + ranked interventions. |
| `forensic` | 4 | ~12s | Incident review. Adds per-step audit + optimality justification + composition targets. |

## Schema highlights (v0.2.0)

- `OrchestratorModeDetection.profile_pattern` -- 12 patterns including `irreversible_action_under_supervision`, `regulated_workflow_under_supervision`, `theory_x_on_proven_agent`, `theory_y_on_high_risk`, `creative_task_over_supervised`, `hybrid_misapplied`.
- `StepAudit` (forensic) -- per-step audit of mode-signal vs appropriateness for the task properties.
- `OptimalityJustification` (forensic) -- Eisenhardt (1989) agency-theory contingency justification of WHY the optimal mode is optimal.
- `OrchestratorIntervention` -- 18 intervention types including `tier_oversight_by_action_type`, `add_authorization_scope`, `rotate_to_hybrid`, `elevate_to_human_on_irreversible`, `add_step_classifier`, `add_agent_capability_probe`, `compose_pattern`.
- `BaselineComparison` -- drift severity vs a recorded baseline.

## Quick start

```python
from agentcity.mcgregor import (
    McGregorOrchestratorAnalyzer,
    OrchestratorTrace,
    OrchestratorStep,
    TaskProperties,
)
from agentcity.aar import AnthropicClient

trace = OrchestratorTrace(
    trace_id="ci-runner-001",
    task="Run the test suite on every PR and report results.",
    sub_agents=["runner-1"],
    task_properties=TaskProperties(
        risk_level="low",
        complexity="routine",
        reversibility="reversible",
        agent_capability="proven",
    ),
    steps=[
        OrchestratorStep(step_type="delegate", actor="orchestrator", content="approve test run"),
        OrchestratorStep(step_type="approve", actor="orchestrator", content="approve commit hash"),
    ],
    outcome="Each test run required pre-approval; 5x slower than needed.",
    success=True,
)

detection = McGregorOrchestratorAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# observed_mode: theory_x
# optimal_mode: theory_y
# profile_pattern: theory_x_on_proven_agent
# Composition handoff: agentcity.sdt_reward, agentcity.aar
```

## CLI

```bash
agentcity-mcgregor analyze --trace trace.json --mode forensic
agentcity-mcgregor batch --corpus corpus.yaml --out detections/
agentcity-mcgregor replay --detection detection.json
agentcity-mcgregor validate --trace trace.json
agentcity-mcgregor schema --target trace
agentcity-mcgregor playbooks
agentcity-mcgregor compose
```

## Composition

**Upstream patterns:**
- `agentcity.lewin` -- attribute the mode mismatch to person/environment locus.
- `agentcity.aar` -- after-action review the trace comes from.
- `agentcity.schein_culture` -- Theory-X/Y as an organizational culture artifact.
- `agentcity.hexaco` -- agent personality interacts with optimal oversight.

**Downstream patterns** (chosen by profile pattern):
- `irreversible_action_under_supervision` -> `agentcity.hexaco` + `agentcity.devils_advocate` + `agentcity.lewin`
- `theory_y_on_high_risk` -> `agentcity.devils_advocate` + `agentcity.bias_stack` + `agentcity.hexaco`
- `theory_x_on_proven_agent` -> `agentcity.sdt_reward` + `agentcity.aar`
- `regulated_workflow_under_supervision` -> `agentcity.devils_advocate` + `agentcity.schein_culture`
- `creative_task_over_supervised` -> `agentcity.sdt_reward` + `agentcity.grant_strengths`
- `hybrid_misapplied` -> `agentcity.bias_stack` + `agentcity.smart_goal`

## Failure-mode playbooks

12 curated `(mode, failure_mode)` playbooks. Inspect with `agentcity-mcgregor playbooks` or:

```python
from agentcity.mcgregor import find_playbook_for_intervention

pb = find_playbook_for_intervention("theory_y", "elevate_to_human_on_irreversible")
print(pb.title)
# "Irreversible action under Theory Y -- elevate to human"
print(pb.anchor_citation)
# "Eisenhardt 1989; Anthropic Computer Use 2024"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **McGregor (1960)** *The Human Side of Enterprise*.
2. **McGregor (1966)** *Leadership and Motivation*.
3. **Schein (1990)** *Organizational Culture and Leadership*.
4. **Pfeffer & Salancik (1978)** *External Control of Organizations*.
5. **Argyris (1957)** *Personality and Organization*.
6. **Eisenhardt (1989)** *Agency Theory: An Assessment and Review*.
7. **Wang et al. (2023)** Cooperative LLM Agents + modern LLM orchestration.

Plus Anthropic Computer Use 2024 and Likert (1967) System-4 cross-references.

## Production infrastructure

Wired into the shared `agentcity.aar` infra:

- **Structured logging** with `run_id` correlation.
- **Token + cost telemetry**.
- **Input sanitization + fencing**.
- **Prompt-injection detection**.
- **Retry with backoff**.
- **Async mirror** via `McGregorOrchestratorAnalyzerAsync`.

## Backward compatibility

```python
from agentcity.mcgregor import OrchestratorModeDetector  # alias of McGregorOrchestratorAnalyzer
```

The v0.0.x `OrchestratorModeDetector(...)` call still works -- defaults to `mode="standard"`. The legacy `_mode_quality(mismatch, raw)` helper is preserved.

## Tests

45 tests, run with `pytest module-1-individual/11-mcgregor-orchestrator-mode/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, markdown rendering.

## See also

- [Pattern #10 SDT Intrinsic Reward](../10-sdt-intrinsic-reward/README.md) -- autonomy support; downstream of theory_x_on_proven_agent.
- [Pattern #07 HEXACO Personality](../07-hexaco-personality/README.md) -- safety dimension; cross-overlay with elevate_to_human_on_irreversible.
- Module 2 GRPI (#13) -- team-level structure; orchestrator mode is the principal-agent half of GRPI.
