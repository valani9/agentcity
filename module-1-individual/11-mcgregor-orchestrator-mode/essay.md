# Your orchestrator approves every step. McGregor diagnosed this in 1960.

*A seventeenth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

Two production agent incidents from the last year:

**Incident A.** A CI-runner agent gated by per-step orchestrator approvals. Task: run the integration test suite on every PR. The agent has a clean track record across thousands of runs. Every test cycle now takes 5× the wall-clock time it should because the orchestrator demands approval before each test step, then intervenes mid-run to reorder fixtures alphabetically. The agent does the work correctly. The orchestrator overhead dominated. The incident report is short: "Process is too slow. Costs are too high."

**Incident B.** A privacy-agent handling a GDPR deletion request. Task: process the user's request end-to-end. The agent does. It also deletes the audit logs the regulator requires the company to retain for seven years. There was no pre-approval gate on log-touching operations. The agent had no way to know it shouldn't. The orchestrator gave one instruction and walked away. Cost to the company: a six-figure remediation effort and a regulatory disclosure.

These look like opposite failures. They are. They have the same root cause: the orchestrator's oversight mode didn't match the task's properties. The CI-runner case is Theory-X applied to a Theory-Y-appropriate task. The privacy-agent case is Theory-Y applied to a Theory-X-appropriate task. Same diagnostic, opposite recommendations.

In 1960, Douglas McGregor — then a professor at MIT Sloan — published *The Human Side of Enterprise.* The book made an argument about implicit assumptions in management. Two competing views were operating in industrial workplaces:

**Theory X** — workers need to be controlled and directed. They avoid work if they can. Effective management means tight supervision, every action approved, low trust.

**Theory Y** — workers want to do good work. They self-motivate if given the chance. Effective management means broad goals, autonomy, high trust.

McGregor's original argument was that Theory Y was empirically more accurate for most workers. But the framework's enduring utility — fifty-five years of management training programs — is the *axis*, not the position on it. Subsequent literature, from Hersey-Blanchard's situational-leadership model to Ouchi's Theory Z, treats the X/Y choice as **mode-per-situation**, not personality-per-manager. The right mode depends on task properties: risk level, reversibility, regulatory exposure, worker capability.

The empirical finding from the situational-leadership research is brutal in its symmetry. Misuse on either side is expensive:

- **Theory-X on routine work** wastes cycles. The CI-runner case. Pre-approval gates that don't mitigate any actual risk impose overhead without benefit. 5× wall-clock is not unusual.
- **Theory-Y on regulated work** invites incidents. The GDPR case. Autonomy granted on high-stakes work without adequate gates produces the publishable failures.

Most production multi-agent systems default to one mode or the other. The one that defaults to Theory-X pays the overhead. The one that defaults to Theory-Y pays the incidents. The one that picks per-task is the rarest — and the most expensive to build, because it requires explicit risk classification on each agent action.

## What `agentcity.mcgregor` does

The library takes an `OrchestratorTrace` containing:

- The **task** and **sub-agents** assigned
- **Task properties**: risk level, complexity, reversibility, regulatory exposure, agent capability
- The **steps** of the orchestrator-agent interaction, each tagged with type (delegate / check_in / approve / reject / intervene / broaden / narrow / abort / observation)
- The outcome and success signal

and produces an `OrchestratorModeDetection` with:

1. **Observed mode** — `theory_x`, `theory_y`, or `hybrid`
2. **Optimal mode** — given the task properties
3. **Mode mismatch** — 0.0 (matched) to 1.0 (opposite)
4. **Mode indicators** — quantitative scores for check-in frequency, autonomy granted, pre-approval required, intervention rate (each 0.0-1.0)
5. **Mode quality** — `well-matched`, `mild-mismatch`, or `severe-mismatch`
6. **Rationale** — why this mismatch matters for this specific task
7. **A ranked list of interventions**: tighten / loosen oversight, add / remove pre-approval gates, add a risk classifier, change check-in cadence, redefine agent boundaries

Two LLM passes under the hood. The intervention pass is skipped when the mode is well-matched (nothing to fix). Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The hybrid mode is what most production systems should converge on — Theory-X on the risky 5% of actions, Theory-Y on the routine 95%. But hybrid requires an explicit risk classifier, which is itself an engineering investment. Teams default to one mode for ergonomic reasons and pay the overhead-or-incident cost as a result.

The McGregor diagnostic is most valuable when it produces the OVERTURNS-style verdict — *"your task properties say Theory-Y, but you're operating in Theory-X; this is severe-mismatch."* That's the moment the team has the diagnostic data to justify removing the gates that are slowing the system down, or — symmetrically — to justify adding the gates that should have been there but weren't.

It's also where the *risk classifier* recommendation does its highest-impact work: rather than picking one mode at config time and living with it, the orchestrator gets a per-action classifier that decides mode on the fly. This is what Anthropic's own internal tooling does for high-stakes operations (deletions, large refunds, schema migrations), and it's what the diagnostic recommends for most teams whose current mode is wrong for their task mix.

## How this fits with the rest of AgentCity

This is pattern #11 of 34 — the seventeenth pattern shipped. AgentCity now opens the **orchestration-design** axis with this pattern, which sits alongside:

- **#28 Devil's Advocate Role Separator** — does a critic role exist *within* the agent's reasoning?
- **#11 McGregor Orchestrator Mode** (this pattern) — does the orchestrator's *oversight cadence* match the task's risk profile?
- **#13 GRPI Working Agreement** — what are the team's shared goals/roles/processes/interactions?
- **#24 SMART Goal Generator** — what are the individual agents' kill criteria?

The four cover the orchestration-design surface: critic structure (28), oversight cadence (11), team agreement (13), and individual-goal specification (24). Patterns #14 (Process Gain/Loss), #15 (Social Loafing), and #26 (Groupthink) then diagnose whether the designed system is *actually working* in production.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-1-individual/11-mcgregor-orchestrator-mode
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
