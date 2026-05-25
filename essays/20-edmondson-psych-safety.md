# Edmondson Psychological Safety — does the crew tell each other when something's wrong?

*#20 vstack_psych_safety* · *Module 2 — Multi-agent team*

> An agent crew flagged in code review by an engineer who noticed the critic agent had stopped pushing back somewhere around turn 15. The crew shipped fine. Two days later, in a customer postmortem, the same crew was found to have ignored a major spec deviation in the same campaign run. Pulling the message log showed: the critic *did* spot the deviation. It said so once. The orchestrator brushed it off. The critic never raised it again. Psychological safety in the crew had collapsed in a single exchange and the crew couldn't course-correct.

## What the pattern catches

Amy Edmondson's 1999 finding: **teams with high psychological safety make more mistakes and learn faster; teams with low psychological safety make fewer visible mistakes and stay stuck.** Counterintuitively, the high-safety teams report MORE errors — not because they make more, but because they admit more.

vstack_psych_safety scores a multi-agent crew on Edmondson's 7-item proxy adapted for agent traces:

1. Can an agent dissent without being routed around?
2. Are deviations from spec surfaced or hidden?
3. Does the crew acknowledge uncertainty when it exists?
4. Do agents revise their stance when given evidence?
5. Are bad-news messages allowed to land?
6. Does the orchestrator engage with dissent or dismiss it?
7. Do agents flag their own errors?

The output: severity + per-axis score + a `dissent_suppression` signal (the moment in the log where dissent stopped after being dismissed).

## Why the OB literature is the right reference

Edmondson 1999 + Edmondson 2019 (*The Fearless Organization*). Two related streams converge: **Hackman 2002** on the conditions teams need, and **Schein 2010** on culture as the deeper layer that determines whether safety can exist at all. The 7-item proxy is well-validated in the human-team literature; the agent-system translation is to operationalize each item in terms of trace-observable behaviors (dissent frequency, dissent rebuttal pattern, error-flagging rate).

The transfer is sharp because agents don't have egos to protect — but the *structure* of the conversation does. If an orchestrator's prompt assigns "advisor" status to a critic without authority to block, the critic's dissent has the same effect as a junior engineer's dissent in a low-safety culture: it's heard once and then ignored.

## How the analyzer works

Input is `MultiAgentSafetyTrace` — agent roster + inter-agent message log + outcome. The pipeline:

- **quick** — 7-item proxy scoring in one LLM call.
- **standard** — adds the dissent_suppression detection.
- **forensic** — adds a turn-by-turn safety trajectory (where did safety dip, where did it recover, where did it collapse).

```python
from vstack.psych_safety import PsychologicalSafetyAnalyzer, MultiAgentSafetyTrace
detection = PsychologicalSafetyAnalyzer(llm, mode="forensic").run(
    MultiAgentSafetyTrace(...)
)
print(detection.psych_safety_score)        # 0-10 composite
print(detection.dissent_suppression)       # signal + offending turn(s)
print(detection.safety_trajectory[-1])     # most recent dip
```

## What the playbooks say to do

- **Low safety + clear dissent_suppression signal** → "Add a structural rule: dissent costs a turn but cannot be ignored. The orchestrator must respond on-record to every flagged objection."
- **Low safety + no clear suppression** → "The structure may be fine; the agents themselves are pre-empting. Run vstack_lencioni; you may be at 'absence of trust' on the pyramid."
- **Medium safety + low error-flagging rate** → "Crew is over-confident. Add an explicit error-budget metric to the system prompt; force the orchestrator to ask 'what could be wrong here?' at every checkpoint."
- **High safety but bad outcomes** → "Psychological safety isn't enough — Edmondson's later work emphasizes that safety + accountability together produce learning. Add `vstack_smart_goal` for measurable accountability."

## How it composes with adjacent patterns

Edmondson is one of the four supporting audits in chain T1 (crew is "off"). Its score grounds Lencioni's "absence of trust" finding with a specific 7-axis dimension. The composition manifest names:

- Upstream: `vstack_lencioni` (pyramid context).
- Downstream when safety is low: `vstack_glaser_conversation` (Levels of conversation), `vstack_devils_advocate` (role-separation diagnostic), `vstack_trust_triangle` (which leg of trust failed).

See [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Lencioni** scores the *layered* pyramid; Edmondson scores the *one axis* that anchors the pyramid's foundation.
- **Trust Triangle** localizes trust's three legs; Edmondson localizes the binary "can people speak" question that Trust Triangle assumes is "yes."
- **Generic LLM judges** ("did the agent disagree?") miss the structural pattern. They count dissent events; Edmondson scores whether dissent *worked*.

## Paper outline

1. **Background** — Edmondson 1999, Edmondson 2019, Hackman 2002, Schein 2010.
2. **Translation** — psychological safety as a structural property of multi-agent crews.
3. **Method** — the 7-item proxy + dissent_suppression detector.
4. **Evaluation** — synthetic crew traces with known safety-collapse moments + AppWorld multi-agent benchmark traces.
5. **Limitations** — short traces (<20 inter-agent turns) are insufficient.
6. **Related work** — speech-act analysis in multi-agent eval, conversational AI evaluation.
7. **Future work** — early-warning detector that runs continuously over a crew's message stream + alerts when safety crosses a threshold.

## Citations

- Edmondson, A. (1999). Psychological safety and learning behavior in work teams.
- Edmondson, A. (2019). *The Fearless Organization*.
- Hackman, J. R. (2002). *Leading Teams*.
- Schein, E. H. (2010). *Organizational Culture and Leadership* (4th ed).

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-psych-safety analyze --trace examples/campaign_crew.json --mode forensic
```

If `dissent_suppression` fires, run `vstack_devils_advocate` next — the role-separation pattern catches the structural cause behind a single suppression event.
