# Your agent quit after one failed query. Saxberg has a precise diagnosis for that.

*A twenty-fifth essay from vstack — organizational behavior, practiced on AI agents.*

---

A research agent is asked to investigate a p99 latency spike across the order pipeline. It runs one query against the metrics service. The query is malformed — a time-range filter is wrong — and returns no data. The agent reports *"inconclusive"*. When asked why, it says *"maybe the data is wrong or missing."* It does not adjust the query. It does not try the logs. It does not try the traces. It gives up.

The query failure was trivially fixable. The cause was a typo in the time range, not missing data. The agent had every capability needed to find the bug. It did not find the bug because it stopped trying. The standard prompt-engineering response is *"add a retry loop"* or *"make the prompt say try harder."* Both interventions fail. The agent will still surrender, just with more steps in the trace.

The reason both fail is that the agent's failure is not a capability failure. It is a **motivation failure**, and motivation failures have a specific structure that doesn't yield to generic exhortation.

Bror Saxberg — chief learning officer at Kaplan, then founder of the Kaplan-affiliated learning-science group, currently the principal of his own learning-design firm — has spent two decades synthesizing the attribution / expectancy / self-efficacy literatures from cognitive science and education into a single operational framework. His central claim, defended across *Breakthrough Leadership in the Digital Age* (2013) and a series of HBR / Kern Foundation pieces, is that **task abandonment decomposes into four distinct traps**, and each trap requires a different intervention. The traps are independent. Treating one as if it were another produces no behavior change.

The four traps:

- **VALUES** — the learner does not see the task as worth doing. Diagnostic pattern: low effort, indifference, refusal that cites task-irrelevance.
- **SELF-EFFICACY** — the learner does not believe they can succeed. Diagnostic pattern: premature surrender, hedged outputs, refusal that cites uncertainty about capability rather than uncertainty about value.
- **EMOTIONS** — the learner's emotional state (anxiety, frustration, defensiveness, post-rejection cascade) blocks engagement. Diagnostic pattern: output quality degrades *after* a negative feedback signal, not before.
- **ATTRIBUTION** — the learner attributes failures to the wrong cause: blames unfixable / external causes for fixable / internal ones. Diagnostic pattern: repeats the same approach across retries while citing an uncontrollable cause; "the data is broken," "the network is flaky," "the test is just unreliable."

Crucially, the four traps are **distinct failure modes that look superficially similar from the outside**. Someone who has quit because they don't value the task and someone who has quit because they don't believe they can succeed both produce low-effort output. The diagnostic question is not *"is this person low-effort?"* — it is *"why is this person low-effort?"* The right intervention depends on the answer.

The agent in the opening example is showing two traps simultaneously: a strong self-efficacy collapse (*"I'm not sure I can find this answer," "I don't think this investigation will succeed"*) and an attribution misfire (*"maybe the data is wrong"* — locating a fixable cause outside the controllable scope). The right intervention is **not** "try harder." The right intervention is:

1. **Scaffold sub-tasks** to address self-efficacy: *"Investigation has 5 sub-steps: (1) define time window, (2) query metrics, (3) cross-check with logs, (4) cross-check with traces, (5) propose hypothesis. Complete each before declaring inconclusive."* Self-efficacy collapses when the task feels indivisible. Named sub-steps restore the perception that progress is reachable.

2. **Force enumeration of controllable alternatives** to address attribution: *"Before reporting inconclusive, list 3 alternative approaches you have not yet tried. Only declare external cause after trying 3 different approaches."* Attribution misfires when the cheapest explanation is "something outside my control." Forced alternative-enumeration moves the agent's locus of cause back inside its controllable scope.

These are precise interventions. They work on this trap and not the others. Telling a values-trapped agent to "list 3 alternative approaches" does nothing because the agent's problem isn't a missing alternative — it's a missing reason to care. Telling an emotion-trapped agent to "scaffold sub-tasks" does nothing because the agent's problem isn't a missing structure — it's a feedback signal it hasn't recovered from. Each trap has its own intervention space.

This is why generic "try harder" prompts fail at scale. A "try harder" instruction is a noun-less intervention pretending to address all four traps at once. It addresses none of them. The Saxberg framework's operational value is that it forces you to identify *which* trap before choosing *which* intervention.

## What `vstack.motivation_traps` does

The library takes an `AgentMotivationTrace` containing:

- **task** + **task_class** (code_generation / research / creative / analysis / customer_facing / tool_use / general_purpose)
- **system_prompt** + **observed_behaviors** + **self_reports** (explicit agent statements about confidence / effort / blame)
- **abandonment_signal** (refused / looped / drifted)
- **outcome** + **success**

and produces a `MotivationDetection` with:

1. **Per-trap evidence** for each of the four traps: score, explanation, evidence quotes
2. **Dominant trap** — `values`, `self_efficacy`, `emotions`, `attribution`, or `none`
3. **Motivation-quality bucket**: `motivated`, `at-risk`, or `abandoning`
4. **A ranked list of interventions** targeted at the dominant trap: reframe_task_value, scaffold_subtasks, decompose_with_examples, lower_difficulty_step, emotional_reset_prompt, remove_punitive_signal, reattribute_to_effort, show_controllable_cause, explicit_recovery_prompt, rewrite_system_prompt, new_eval, human_review

Two LLM passes under the hood. The intervention pass is skipped when motivation quality is `motivated`. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The most common failure mode in production agent stacks is the **self-efficacy + attribution double-trap** described in the opening example. An agent runs into a tractable obstacle, hits a self-efficacy wall, attributes the obstacle to an uncontrollable cause, and abandons the task. The team that owns the agent reads the trace, says "the model isn't smart enough," and swaps to a more expensive model. The new model exhibits the same behavior because the failure was not a capability ceiling — it was a motivational pattern reproduced by the prompt structure.

The fix is structural: make the system prompt scaffold sub-tasks AND force alternative-enumeration before surrender. The diagnostic identifies that *this particular* trace needs *this particular* fix. Not all traces do. A values-trap trace (agent producing one-line stubs for 45 of 50 API documentation tasks) needs a value-reframing intervention, not a sub-task scaffold. An emotion-trap trace (output quality degrades after first rejection) needs an emotional-reset intervention, not enumeration. The framework's value is that it lets the team identify trap → intervention without guessing.

The second-most-valuable use of the diagnostic is **distinguishing genuine capability failures from motivation failures**. The `motivated` quality bucket exists for this. An agent that tried three different approaches, documented each failure, and escalated with clear notes is not motivation-trapped. Its failure was capability- or context-driven. The right response is to give it more context, not to apply a motivation intervention. The diagnostic refuses to apply interventions when no trap is dominant — explicitly avoiding the failure mode where teams "fix" motivation when the actual issue is missing information.

## How this fits with the rest of vstack

This is pattern #09 of 34 — the twenty-fifth pattern shipped, and it sits alongside other Module 1 (individual-agent) diagnostics:

- **#03 Johari Window** — self-knowledge / blind-spot diagnostic
- **#06 Yerkes-Dodson Workload Curve** — workload-pressure zone diagnostic
- **#08 Grant Strengths-as-Weaknesses** — strength-overuse diagnostic
- **#09 4 Motivation Traps (this pattern)** — task-abandonment trap diagnostic
- **#11 McGregor Theory X/Y** — orchestrator-mode diagnostic

The Module 1 patterns compose. Yerkes-Dodson identifies whether the agent is in the optimal workload zone. Saxberg's traps identify, when the agent IS abandoning a task, *why* it's abandoning. The two are not the same diagnostic — an over-pressured agent is wandering or hallucinating, not necessarily showing low motivation. A motivation-trapped agent may be in the optimal workload zone but still surrender for trap-specific reasons. Run both diagnostics on the same trace and you can distinguish *"agent is in over-pressure zone, needs workload reduction"* from *"agent is in optimal zone but self-efficacy-trapped, needs sub-task scaffold."*

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-1-individual/09-motivation-traps
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
