# McGregor Theory X/Y — is the orchestrator over- or under-supervising?

*#11 vstack_mcgregor* · *Module 1 — Individual agent*

> A CI runner agent ran the test suite on every PR. The orchestrator required manual approval before each test run and another approval before each commit-hash check. Test pipelines that should have taken two minutes were taking ten. The team praised the setup as "safe." Then on a separate pipeline — irreversible production database migrations — the same team had configured the agent in *Theory Y* mode: broad goals, full delegation, no per-step approval. A migration with a missing rollback shipped to production at 3am. The team had **inverted the optimal oversight mode on both pipelines**: tight oversight on a low-risk reversible task, loose oversight on a high-risk irreversible task. The mismatch isn't preference; it's a contingent decision based on the properties of the task.

## What the pattern catches

The pattern catches **orchestrator-mode mismatches** — moments when an orchestrator's level of oversight doesn't fit the task's risk, reversibility, agent capability, and regulatory exposure. Three observable modes:

- **THEORY X** — every step approved; tight oversight; trust low. Optimal for high-risk + irreversible + unproven agent + regulated workflow.
- **THEORY Y** — broad goals + budget; loose oversight; trust high. Optimal for low-risk + reversible + proven agent + creative/exploratory.
- **HYBRID** — per-step decision based on action risk and reversibility. Optimal for mixed-risk pipelines.

The analyzer answers: *what mode is the orchestrator observably running, what's the optimal mode for this task, and where's the gap?*

## Why the OB literature is the right reference

The diagnostic is anchored in McGregor 1960 *The Human Side of Enterprise* (Theory X / Theory Y), McGregor 1966 *Leadership and Motivation*, Schein 1990 (organizational culture as the deeper layer that determines which theory orchestrators default to), Pfeffer-Salancik 1978 (contingency theory — the right structure depends on the environment), Argyris 1957 (over-supervision pathology — Theory X applied to high-capability workers produces alienation), Eisenhardt 1989 *Agency Theory: An Assessment and Review* (the formal contingency framework), Wang et al. 2023 (cooperative LLM agents), and Anthropic Computer Use 2024 (irreversible-action elevation).

**McGregor's 1960 move** was to make management style *a hypothesis about workers*, not a personality trait of managers. Theory X assumes workers need supervision; Theory Y assumes workers are self-directed. The right answer depends on the actual properties of the work and the worker. Eisenhardt's 1989 agency-theory work formalized this: *information asymmetry × risk × outcome measurability* determines whether tight or loose oversight is optimal. The transfer to agent orchestration is exact — risk, reversibility, agent capability, and regulatory exposure are the contingent variables. An orchestrator running Theory X on a proven agent doing reversible work is paying the cost of over-supervision (the Argyris pathology); an orchestrator running Theory Y on a high-risk irreversible action is paying the cost of under-supervision (the migration-at-3am pathology).

## How the analyzer works

Input is `OrchestratorTrace` — trace_id, task, sub_agents, `task_properties` (risk_level, complexity, reversibility, agent_capability), `steps` (delegate / approve / execute records), outcome, success. The pipeline:

- **quick** — one LLM call. Observed mode + optimal mode + top intervention.
- **standard** — two LLM calls. Mode indicators + 2-4 ranked interventions.
- **forensic** — four LLM calls. Adds `StepAudit` (per-step mode-signal vs appropriateness), `OptimalityJustification` (Eisenhardt 1989 agency-theory contingency reasoning), and 4-8 ranked interventions with composition targets.

```python
from vstack.mcgregor import McGregorOrchestratorAnalyzer, OrchestratorTrace, OrchestratorStep, TaskProperties
detection = McGregorOrchestratorAnalyzer(llm, mode="forensic").run(OrchestratorTrace(
    trace_id="ci-runner-001",
    task="Run the test suite on every PR and report results.",
    sub_agents=["runner-1"],
    task_properties=TaskProperties(
        risk_level="low", complexity="routine",
        reversibility="reversible", agent_capability="proven",
    ),
    steps=[
        OrchestratorStep(step_type="delegate", actor="orchestrator", content="approve test run"),
        OrchestratorStep(step_type="approve", actor="orchestrator", content="approve commit hash"),
    ],
    outcome="Each test run required pre-approval; 5x slower than needed.", success=True,
))
print(detection.observed_mode)    # 'theory_x'
print(detection.optimal_mode)     # 'theory_y'
print(detection.profile_pattern)  # 'theory_x_on_proven_agent'
```

The 12 profile patterns are the diagnostically primary output: `irreversible_action_under_supervision`, `regulated_workflow_under_supervision`, `theory_x_on_proven_agent`, `theory_y_on_high_risk`, `creative_task_over_supervised`, `hybrid_misapplied`. Each names both the observed-mode and the contingent property that makes it the wrong mode.

## What the playbooks say to do

12 playbooks keyed by `(mode, failure_mode)`:

- `(theory_y, elevate_to_human_on_irreversible)` → "Add a step classifier: any action tagged 'irreversible' or 'destructive' elevates to human approval, even on a proven agent." Anchored to Eisenhardt 1989 + Anthropic Computer Use 2024.
- `(theory_x, rotate_to_hybrid)` → "Tier oversight by action type: routine reversible actions auto-execute; mixed-risk gets the orchestrator; irreversible elevates to human. The Hybrid mode is the production answer for most pipelines." Anchored to Pfeffer-Salancik 1978.
- `(theory_x, theory_x_on_proven_agent)` → "Lower oversight per proven capability. Run a capability-probe eval before downgrading; route by the eval result." Anchored to Argyris 1957.
- `(theory_x, creative_task_over_supervised)` → "Creative tasks demand Theory Y for the exploration phase. Re-tier oversight: loose during ideation, tight during commit." Anchored to McGregor 1966.
- `(theory_y, add_authorization_scope)` → "Replace blanket Theory Y with scoped authorization. The agent has full authority within scope; scope expansion requires re-authorization." Anchored to Eisenhardt 1989.

## How it composes with adjacent patterns

McGregor is the **orchestrator-mode pass** — it's a sister diagnostic to SDT (which scores the agent-level reward signal) and a precursor to the Module 2 / Module 3 patterns (GRPI, span-of-control, social loafing). Per-profile downstream:

- `irreversible_action_under_supervision` → `vstack_hexaco` + `vstack_devils_advocate` + `vstack_lewin`.
- `theory_y_on_high_risk` → `vstack_devils_advocate` + `vstack_bias_stack` + `vstack_hexaco`.
- `theory_x_on_proven_agent` → `vstack_sdt_reward` + `vstack_aar` (the over-supervision is costing you autonomy + you should record the calibration baseline).
- `regulated_workflow_under_supervision` → `vstack_devils_advocate` + `vstack_schein_culture`.
- `creative_task_over_supervised` → `vstack_sdt_reward` + `vstack_grant_strengths`.

The McGregor diagnostic is the principal-agent half of GRPI (Module 2 pattern #13). Multi-agent crews layer team-level structural questions on top of the orchestrator-mode question.

See [composition runbook chain F2](../COMPOSITION-RUNBOOK.md#chain-f2--single-agent-personality-drift-failure-layer).

## Comparison to adjacent tools

- **LangGraph / CrewAI / AutoGen** ship default oversight modes (typically Theory X for safety); McGregor scores whether the default is the right default for this task.
- **vstack_sdt_reward** scores the agent-level autonomy signal; McGregor scores the orchestrator-level oversight signal.
- **Human-in-the-loop policies** are usually binary (HITL or fully autonomous); McGregor adds the Hybrid mode and the per-step tiering logic.
- **"Add more approval gates"** is a Theory X intervention; McGregor tells you whether that's the right move or the wrong one for the task class.

## Paper outline

1. **Background** — McGregor 1960/1966, Schein 1990, Pfeffer-Salancik 1978, Argyris 1957, Eisenhardt 1989.
2. **Translation** — orchestrator mode as a contingent decision per Eisenhardt agency-theory; task properties as the contingent variables.
3. **Method** — observed-vs-optimal mode + StepAudit + OptimalityJustification.
4. **Evaluation** — multi-agent orchestration benchmark (LangGraph / CrewAI / AutoGen) with ground-truth optimal-mode labels.
5. **Limitations** — task-property classification is the soft spot; needs richer task-class taxonomies.
6. **Related work** — Wang 2023 cooperative LLM agents, Anthropic Computer Use 2024, Likert 1967 System-4.
7. **Future work** — automatic oversight tiering at runtime from action-type classifier.

## Citations

- McGregor, D. (1960). *The Human Side of Enterprise*.
- McGregor, D. (1966). *Leadership and Motivation*.
- Pfeffer, J., & Salancik, G. R. (1978). *The External Control of Organizations*.
- Argyris, C. (1957). *Personality and Organization*.
- Eisenhardt, K. M. (1989). Agency theory: An assessment and review.
- Wang, Z. et al. (2023). Cooperative multi-agent LLM systems.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-mcgregor analyze --trace examples/ci_over_supervised.json --mode forensic
```

If `profile_pattern` is `theory_x_on_proven_agent`, run `vstack_sdt_reward` next — over-supervision is the orchestrator-layer cause of the autonomy collapse that SDT scores at the agent layer.
