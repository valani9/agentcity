# Your multi-agent crew has loafers. Latané proved this in 1979.

*A thirteenth essay from vstack — organizational behavior, practiced on AI agents.*

---

A 5-agent research crew gets assigned to produce a report on prompt-injection defenses. The roster:

- `lead` — set goals, approve structure, ship decision
- `researcher` — gather sources, propose framing
- `writer` — draft the report
- `reviewer` — check structure
- `fact-checker` — verify citations

The trace tells a familiar story. Lead sets the plan. Researcher runs the web search, surfaces eight papers, proposes a four-section structure, and — critically — flags one specific claim ("Apollo 2026 reports 92% reduction in attack-success-rate from structured prompts") as *needs verification*. Lead approves. Writer's contribution: "Drafting per researcher's framing." Reviewer: "Structure LGTM. Proceed." Fact-checker: "Citations look fine to me." Lead ships.

The report goes out. Two days later someone notices the Apollo paper actually reported 62%, not 92%. The researcher had explicitly *flagged* the claim for verification. The fact-checker, who exists for exactly this case, waved it through with a four-word rubber-stamp.

This is not a hallucination problem. The researcher correctly noted that the claim needed verification. The fact-checker had access to the same tools the researcher did. The system architecture was correct. The failure was that three of five agents on the crew produced near-zero substantive work — and the one whose entire job was verification produced zero verifications.

In 1979, Bibb Latané, Kipling Williams, and Stephen Harkins published *Many Hands Make Light the Work* in the *Journal of Personality and Social Psychology*. The paper documented a phenomenon they named **social loafing**: when individuals work in groups where contribution is pooled and anonymous, per-person effort drops by ~50% in groups of six. The mechanism is intuitive once you see it. When the boss can't tell who contributed what, individuals can "hide" in the group. They produce less because they expect others to make up the slack, and because the link between their effort and the group's outcome becomes opaque.

The phenomenon scales with three factors that should sound familiar to anyone deploying multi-agent crews:

1. **Anonymity of contribution.** "The team produced this report" hides which agent did what.
2. **Group size.** More agents = more anonymity = more loafing.
3. **Pooled evaluation.** When the team is judged as a unit, loafing is rewarded; when individuals are judged separately, it collapses.

Multi-agent AI crews exhibit *all three of these conditions by default.* The crew has a shared output. The orchestrator evaluates the crew, not the agents. The team is over-staffed because adding agents looks like adding capability. And — the twist that makes AI loafing worse than human loafing — the LLM behind each agent has no internal motivation to fight the gravitational pull of the role. The "reviewer" prompt suggests reviewers often say "looks good"; the model generates "looks good." There's no friction, no embarrassment, no peer noticing. The loafing is structural.

## What `vstack.social_loafing` does

The library takes a `MultiAgentTaskTrace` — task, the list of agents on the team, the messages each agent produced (each tagged with `message_type`: proposal / critique / approval / rubber_stamp / paraphrase / tool_call / observation / decision / handoff / question / other), outcome, success — and produces a `SocialLoafingDetection` with:

1. **Per-agent contribution metrics**: contribution share, substantive-vs-cosmetic work counts, loafing score, role label (primary-contributor / secondary-contributor / loafer / absent), and evidence quotes.
2. **A Gini coefficient** of contribution shares. 0.0 = perfectly equal team; 1.0 = one agent did everything.
3. **A loafing-quality bucket**: `no-loafing`, `mild-loafing`, `severe-loafing`.
4. **A ranked list of interventions** targeting the loafing agents: assign-subgoals, individual-accountability, decompose-task, smaller-team, rotate-roles, explicit-critic-assignment, remove-loafer, per-agent-evaluation.

Two LLM passes: one to score per-agent contribution, one to propose interventions. Same retry / graceful-degradation / structured-logging infrastructure as the rest of vstack.

## Why this matters operationally

The most operationally dangerous form of loafing is the *rubber-stamp on the verification role*. A reviewer agent that doesn't review, a fact-checker that doesn't fact-check, a QA agent that doesn't QA — these aren't just unhelpful. They're *worse than the agent's absence*, because their existence makes the team's output look authoritative when it isn't. The shipped report that contains the wrong number wouldn't have shipped if there were *no* fact-checker; the existence of a fact-checker box, even an empty one, conveys "this was checked."

The diagnostic catches this. The fact-checker's nominal job was to verify citations; their trace contains zero tool calls and one four-word rubber-stamp. The diagnostic flags them as `loafer` with `loafing_score: 1.0` and recommends `individual_accountability` with the specific intervention: *for every numeric claim, the fact-checker must (1) state the claim, (2) execute the verifying tool call, (3) paste the verifying evidence. A response without these three elements per claim is invalid.* That single intervention — making verification *observable* — is the textbook Latané solution. Individual accountability collapses loafing.

The second most operationally relevant loafing pattern is *paraphrase loafing*: an agent downstream of a primary contributor whose entire output is a restatement. The classic case is a writer agent who follows a researcher agent. The researcher does all the substantive work; the writer paraphrases. The intervention here is `decompose_task` — give the writer a non-overlapping deliverable (executive summary, threat-model framing, open-questions section) so their work isn't just downstream-of-researcher.

## How this fits with the rest of vstack

This is pattern #15 of 34 — the thirteenth pattern shipped. vstack now ships three patterns that diagnose different multi-agent crew dysfunctions:

- **#17 Lencioni Five Dysfunctions** — the high-level team dysfunction taxonomy (trust → conflict → commitment → accountability → results)
- **#28 Devil's Advocate Role Separator** — is the critic role *structurally present*?
- **#15 Social Loafing Detector** — given the roles exist, are they actually being *done*?

The three compose: Lencioni for the team-shape diagnostic, Devil's Advocate for the role-structure diagnostic, Social Loafing for the per-agent contribution diagnostic. Most failing multi-agent crews score badly on at least two of the three.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/15-social-loafing-detector
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
