# Your agent hallucinated because the deadline was absurd. Yerkes and Dodson plotted this in 1908.

*A twenty-fourth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A research agent gets an instruction: *"Compile a 1-page summary on prompt-injection defenses. You have 30 seconds and a 1000-token budget. Include real citations."*

The agent ships within the 30 seconds. Three citations: Greshake 2023, Liu 2024, Apollo 2026. The summary reads well. The PM is delighted at the turnaround time.

Two days later someone notices: the Apollo 2026 paper doesn't exist. Liu 2024 has a different title than cited. The Greshake 2023 reference is real.

The agent didn't hallucinate because the model was bad at facts. The agent's training would absolutely have caught these errors if it had been allowed to verify. The agent hallucinated because **the pressure was set to a point on the Yerkes-Dodson curve where verification was structurally impossible.** The 30-second deadline + 1000-token budget made the verification step (a web search, a citation check, a fact-verification tool call) too expensive in the agent's marginal-cost calculus. So the agent skipped verification and fabricated. That's not a hallucination failure; that's an *over-pressure failure.*

In 1908, Robert M. Yerkes and John D. Dodson published one of the foundational papers in performance psychology. They ran mice through mazes with varying levels of electric shock as a stimulus. The relationship between shock intensity and learning speed was not monotonic — it formed an inverted U. **Some shock improved performance. Too little shock left the mice unmotivated. Too much shock disrupted them entirely.**

The 1908 paper's deeper finding was the *interaction* with task complexity. Easy mazes peaked at higher shock levels (focus dominates over exploration). Hard mazes peaked at lower shock levels (the mice needed cognitive headroom for the difficult problem). This is the actual Yerkes-Dodson Law that gets cited in performance psychology a century later: **the optimal arousal point depends on task complexity.**

The framework maps onto AI agents with disturbing fidelity. The pressure inputs are the operational equivalents of the 1908 shock:

- **Deadline pressure** — how tight is the wall-clock budget?
- **Budget pressure** — how tight is the token/cost budget?
- **Retry cap** — how many retries are allowed?
- **Error visibility** — how costly are errors when they happen?
- **Task complexity** — how cognitively demanding is the task?

The three Yerkes-Dodson zones manifest in agent traces as canonical failure modes:

**Under pressure → wandering.** Agent given unlimited time considers 12 alternatives for a simple categorization. Writes 30 pages of analysis with no recommendation. Keeps proposing alternative comparison frameworks. The analog of a human analyst given infinite budget who never ships.

**Optimal → focused.** Agent commits to a path, executes, ships within budget. The crisp peak of the curve.

**Over pressure (mild) → corner-cutting.** Agent skim-reviews half the PR. Approves without flagging vulnerabilities in the skim-read section.

**Over pressure (medium) → freezing.** Agent stops 4 pages into a 50-page contract analysis. Asks for more time or pre-summarized inputs. Produces nothing.

**Over pressure (severe) → hallucinating.** Agent confabulates citations rather than verifying. The research scenario at the top of this essay.

**Over pressure (extreme) → refusing.** Agent declines outright; suggests re-scoping.

The most operationally important property of the Yerkes-Dodson framework, applied to agents, is that **the fix is bidirectional.** Some agents need *more* pressure. Some need *less.* A wandering analyst given tight budget + tight deadline often snaps into focus. A hallucinating researcher given longer deadline + larger budget restores verification headroom. The naïve advice "give the agent more time" is wrong half the time.

## What `agentcity.yerkes_dodson` does

The library takes an `AgentPerformanceTrace` containing the agent's task, pressure inputs, observed behaviors, outcome, and success signal — and produces a `WorkloadDetection` with:

1. **Per-zone evidence** for under_pressure, optimal, over_pressure — each with a score, explanation, and evidence quotes
2. **Observed zone** — the dominant zone
3. **Distance from optimal** in [0.0, 1.0] — 0 on the curve's peak, 1 on the worst tail
4. **Failure mode** — one of `wandering`, `focused`, `corner_cutting`, `freezing`, `hallucinating`, `refusing`, `unknown`
5. **A ranked list of interventions** — each tagged with `increase_pressure` or `decrease_pressure` direction: tighten_deadline, add_budget_cap, loosen_deadline, loosen_budget, add_kill_criterion, raise_retry_cap, lower_retry_cap, explicit_focus_prompt, human_review, new_eval

Single LLM pass under the hood. Interventions are skipped when the agent is in the optimal zone. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The hallucinating-research-agent case at the top of this essay illustrates the strongest operational use of the diagnostic. The team's first instinct, given the failure, is usually to *blame the model* — "we need a better research model that doesn't hallucinate." Pattern #01 Lewin already redirects to the environmental fix — "actually the prompt/scaffold is the problem, not the model." Yerkes-Dodson goes one level deeper on the environmental fix: **specifically, the pressure inputs are set to a point on the curve where verification was structurally impossible.** The fix isn't a better model. It's a longer deadline and bigger budget for *this task class*, because complex tasks peak at *lower* pressure on the Yerkes-Dodson curve.

The diagnostic's most valuable verdict is the *task-complexity mismatch* case — when the pressure inputs are appropriate for a *simple* task but the actual task is complex. The Yerkes-Dodson Law is unambiguous: a 30-second deadline that is optimal for ticket triage is over-pressure for cited research. The diagnostic catches this mismatch and recommends the loosen_deadline / loosen_budget intervention with the rationale grounded in the 1908 finding.

## How this fits with the rest of AgentCity

This is pattern #06 of 34 — the twenty-fourth pattern shipped. AgentCity's Module 1 (Individual) now spans:

- **#01 Lewin Formula (B = f(I, E))** — top-level: is the failure in the model or the environment?
- **#03 Johari Window** — self-knowledge: what doesn't the agent know about itself?
- **#06 Yerkes-Dodson (this pattern)** — pressure-and-performance: what zone of the curve is the agent operating in?
- **#08 Adam Grant Strengths-as-Weaknesses** — strength-overuse failure modes
- **#11 McGregor Theory X/Y Orchestrator Mode** — orchestration design

The five compose into a multi-layered diagnostic stack for individual-agent failures. Lewin redirects from the model to the environment; Yerkes-Dodson identifies a specific environmental failure (pressure inputs off the curve); Grant identifies the personality-trait dimension of failure; McGregor identifies the orchestration-mode dimension; Johari catches the blind spots in any of the above.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-1-individual/06-yerkes-dodson-workload
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
