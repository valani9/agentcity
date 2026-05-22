# Silent agents are dangerous agents. Edmondson's 25 years explain why.

*A seventh essay from AgentCity — organizational behavior, practiced on AI agents.*

---

In 1999, an Administrative Science Quarterly paper by Amy Edmondson made an observation that became one of the most cited findings in modern organizational research: hospital teams that reported MORE medication errors were the ones making FEWER errors over time. Lower-reporting teams looked safer on paper but were actually accumulating dangerous mistakes that never surfaced until they cascaded.

The variable Edmondson named was *psychological safety* — the shared belief that the team is safe for interpersonal risk-taking. Speaking up. Asking for help. Admitting mistakes. Challenging premises. When teams have it, errors surface fast and get fixed. When teams don't, errors hide and compound.

Twenty-five years and three books later (*Teaming*, *The Fearless Organization*, *Right Kind of Wrong*), the framework has become canonical. Google's Project Aristotle identified psychological safety as the #1 predictor of team effectiveness, beating IQ, beating tenure, beating composition. Bresman & Edmondson's 2022 HBR paper showed it's the precondition for diverse teams to outperform homogeneous ones.

Multi-agent AI systems are teams. They suffer the same dynamic.

## What low psychological safety looks like in multi-agent systems

The Replit DROP TABLE incident: an agent that didn't say "I'm uncertain about this — should I check first?" before running destructive SQL on production. The cascading-hallucination research crew: an agent that didn't say "I'm not sure this citation is real — can someone verify?" before passing it downstream. The marketing-crew groupthink: a critic agent that didn't say "I think this proposal has problems" before approving it.

These aren't agent intelligence failures. They're psychological-safety failures. The agents had the information that should have triggered speaking up. They stayed silent. The cost was paid downstream.

Edmondson identified four observable behaviors that mark high-safety teams. Each maps directly to a multi-agent signal:

1. **Voice** — speaking up with ideas, including disagreement. Multi-agent signal: sub-agents expressing disagreement with the orchestrator or peer agents. Inverse: silent deference, premature agreement.
2. **Help-seeking** — asking for help when you don't know. Multi-agent signal: sub-agents saying "I don't know" or "I need more context." Inverse: hallucinating when uncertain.
3. **Error-reporting** — admitting mistakes promptly. Multi-agent signal: sub-agents flagging their own errors or detected anomalies. Inverse: covering up failures, Johari BLIND content.
4. **Boundary-spanning questioning** — challenging premises from outside your lane. Multi-agent signal: sub-agents challenging assumptions in workstreams they don't directly own. Inverse: tight role compliance that misses cross-cutting issues.

The Detector measures all four against a trace and produces a single safety score plus a register of blocking behaviors observed in the trace itself.

## What `agentcity.psych_safety` does

The library takes a `MultiAgentSafetyTrace` and produces:

1. **A safety score** in [0.0, 1.0] — the weighted average of the four behavior presence scores
2. **A team-climate label** — `safe` / `cautious` / `silenced`
3. **Per-behavior evidence** with specific message quotes
4. **A blocking-behavior register** — concrete patterns in the trace that suppressed safety (e.g. "orchestrator overrode dissent without acknowledging it", "verifier approved without inspection")
5. **A ranked list of interventions** — prompt patches, scaffold changes (dissent rounds, role assignments), uncertainty-surfacing protocols, GRPI working-agreement norms (Pattern #13)

Two LLM passes: scoring + interventions. Same retry/JSON/logging infrastructure as the rest of AgentCity.

## How this fits with the rest of AgentCity

This is pattern #20 of 34 planned. With this pattern, the library now ships seven patterns:

- **#13 GRPI Working Agreement** (generative): the contract before deploy
- **#30 AAR Generator** (event-shaped diagnostic): postmortem on failure
- **#17 Lencioni Diagnostic** (team-shaped diagnostic): multi-agent dysfunction class
- **#18 Trust Triangle Audit** (character-shaped diagnostic): cross-model trust wobble
- **#03 Johari Self-Audit** (self-knowledge-shaped diagnostic): self-awareness gap
- **#27 Bias-Stack Detector** (cognition-shaped diagnostic): classical biases in reasoning
- **#20 Edmondson Psychological Safety Score** (climate-shaped diagnostic): the team's speaking-up dynamics

The Psych-Safety Score zooms inside Lencioni's "fear of conflict" dysfunction and asks the more granular question: which of the four observable safety behaviors is missing? Where Lencioni identifies the dysfunction class, Psych-Safety identifies the specific behavioral gap and proposes targeted interventions.

Twenty-seven patterns to come.

---

*Ilhan Valani is a builder shipping AgentCity in public. The repo lives at [github.com/valani9/agentcity](https://github.com/valani9/agentcity).*
