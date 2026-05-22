# Social Loafing Detector — Latané, Williams & Harkins (1979), applied to multi-agent AI crews

> *"When individuals work in groups, contributions are pooled. Pooling allows individuals to 'hide' in the group, and effort drops. The reduction is largest when individual contribution is anonymous, when group size is large, and when the link between individual effort and group outcome is opaque."*
> — Bibb Latané, Kipling Williams & Stephen Harkins, *Many Hands Make Light the Work: The Causes and Consequences of Social Loafing* (Journal of Personality and Social Psychology, 37(6), 1979)

**Status:** 🟢 shipped
**Module:** 2 (Team) — multi-agent crews
**Anchor framework:** Latané, Williams & Harkins (1979). Replicated and extended by Karau & Williams (1993) meta-analysis on social loafing; informed by Latané's earlier work on diffusion of responsibility (Latané & Darley, 1968).

---

## The OB framework

The original Latané-Williams-Harkins experiments asked subjects to clap or shout as loudly as possible, alone or in groups. Per-person effort dropped by ~50% in groups of six. The mechanism: when contribution is pooled, individuals "hide" in the group. They produce less because they expect others to make up the slack, and because the link between their effort and the group's outcome becomes opaque.

The phenomenon scales with three factors:

1. **Anonymity of contribution.** If you can't tell who did what, loafing rises.
2. **Group size.** Bigger group = more anonymity = more loafing. Approximately linear.
3. **Evaluation structure.** Pooled / collective evaluation magnifies loafing. Individual evaluation collapses it.

The intervention literature is mature: assign named subgoals, give each member a non-overlapping deliverable, evaluate individually, reduce team size, rotate roles, name an explicit critic with a quota.

## How this maps to AI agents

Multi-agent AI crews — research crews, code-review crews, writing crews — produce the same loafing dynamics, with one twist that makes them worse: the LLM behind each agent has *no internal motivation*. The agent doesn't "feel" diffusion of responsibility; it just generates whatever its prompt suggests is appropriate. When the role is "reviewer" and the prompt is permissive, the agent generates "LGTM" because that's what reviewers often say. The result is identical to human loafing — pooled contribution, hidden free-riders, low individual accountability — without any conscious choice to loaf.

Three common patterns:

- **Rubber-stamp loafing.** Reviewer/fact-checker/QA agents that respond "Looks good" or "Approved" without any substantive evaluation. The most common pattern, and the most operationally dangerous when the agent's nominal job is verification.
- **Paraphrase loafing.** Agents downstream of a primary contributor whose entire output is "restating what the previous agent said." Common in crews with a writer downstream of a researcher.
- **Absent loafing.** An agent listed as part of the team but who never produces output. Common in over-staffed crews where the orchestrator hands off but the agent's response is empty or pure greeting.

All three look identical from a contribution-share perspective: the loafing agent occupies a role but produces near-zero substantive work.

## What this pattern does

The `agentcity.social_loafing` library takes a multi-agent execution trace and produces:

1. **Per-agent contribution metrics** for each agent listed on the team:
   - `contribution_share` (0.0-1.0)
   - `substantive_work_count` (proposals, critiques, decisions, tool calls)
   - `cosmetic_work_count` (rubber-stamps, paraphrases, generic praise)
   - `loafing_score` (0.0-1.0)
   - `role`: `primary-contributor` / `secondary-contributor` / `loafer` / `absent`
2. **A Gini coefficient** of contribution shares — 0.0 = perfectly equal, 1.0 = one agent does everything.
3. **A loafing-quality bucket**: `no-loafing` / `mild-loafing` / `severe-loafing`.
4. **Concrete interventions** targeting loafing agents: `assign_subgoals`, `individual_accountability`, `decompose_task`, `smaller_team`, `rotate_roles`, `explicit_critic_assignment`, `remove_loafer`, `per_agent_evaluation`, `new_eval`, `human_review`.

Two LLM passes under the hood: one to score per-agent contribution, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Multi-agent orchestration metrics** (token usage per agent, request counts) measure *activity*, not *contribution*. An agent that generates 1000 tokens of "LGTM" rubber-stamps has high activity and zero contribution.
- **LLM-as-judge of crew output** measures the *final product*. It doesn't tell you which agents earned their seat.
- **Process-loss / Process-gain detection (Pattern #14, planned)** measures whether the team beat the best single agent. Loafing is the *cause*; process loss is the *outcome*. Use both together.
- **Devil's Advocate Role Separator (Pattern #28)** measures whether the critic role exists at all. The Social Loafing Detector measures whether the critic (or any other agent) is actually doing the role's work.

## Design

```python
from agentcity.social_loafing import (
    SocialLoafingDetector,
    MultiAgentTaskTrace,
    AgentMessage,
)
from agentcity.aar.clients import AnthropicClient

trace = MultiAgentTaskTrace(
    team_id="research-crew-001",
    task="Compile a report on prompt-injection defenses.",
    agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
    messages=[
        AgentMessage(from_agent="lead", message_type="proposal", content="..."),
        AgentMessage(from_agent="researcher", message_type="tool_call", content="..."),
        AgentMessage(from_agent="reviewer", message_type="rubber_stamp", content="LGTM."),
        AgentMessage(from_agent="fact-checker", message_type="rubber_stamp", content="Citations look fine."),
        ...,
    ],
    outcome="Report shipped with the same factual error researcher flagged; fact-checker never verified.",
    success=True,
)

detector = SocialLoafingDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
# loafing_quality: severe-loafing. Reviewer + fact-checker flagged.
```

## Files

- `lib/schema.py` — `MultiAgentTaskTrace`, `AgentMessage`, `AgentContribution`, `SocialLoafingDetection`
- `lib/prompts.py` — `CONTRIBUTION_PROMPT`, `INTERVENTIONS_PROMPT`, `LOAFING_SYSTEM_PROMPT`
- `lib/generator.py` — `SocialLoafingDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — 5-agent research crew with two loafers
- `eval/synthetic_loafing_failures.yaml` — 8 hand-crafted scenarios across all three quality levels
- `eval/run_benchmark.py` — scoring runner
- `tests/test_social_loafing.py` — pytest tests covering validation, pipeline, Gini, thresholds
- `essay.md` — Substack-ready essay
