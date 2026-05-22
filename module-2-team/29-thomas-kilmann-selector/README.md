# Thomas-Kilmann Conflict Style Selector — five conflict modes for AI agents

> *"All five conflict-handling modes are appropriate in some situations, and inappropriate in others. The effective manager develops the ability to read situations and choose the right mode."*
> — Kenneth Thomas & Ralph Kilmann, *Thomas-Kilmann Conflict Mode Instrument* (CPP, 1974)

**Status:** 🟢 shipped
**Module:** 2 (Team)
**Anchor framework:** Kenneth W. Thomas & Ralph H. Kilmann — *Thomas-Kilmann Conflict Mode Instrument (TKI)* (CPP, 1974); de Dreu, Evers, Beersma, Kluwer, & Nauta — *A Theory-Based Measure of Conflict Management Strategies in the Workplace* (Journal of Organizational Behavior, 2001).

---

## The OB framework

The Thomas-Kilmann model maps conflict-handling behavior across two dimensions: *assertiveness* (how strongly you push your own concerns) and *cooperativeness* (how strongly you accommodate the other party's concerns). The 2×2-ish space produces five canonical conflict styles:

```
                                  Cooperativeness
                          Uncooperative      Cooperative
                       ┌───────────────────┬───────────────────┐
        Assertive      │    COMPETING      │   COLLABORATING   │
                       ├───────────────────┼───────────────────┤
        Moderate       │          COMPROMISING                 │
                       ├───────────────────┼───────────────────┤
        Unassertive    │     AVOIDING      │   ACCOMMODATING   │
                       └───────────────────┴───────────────────┘
```

| Style | When it's right | When it's wrong |
|---|---|---|
| **Competing** | Quick action needed; unpopular decisions; the other party would exploit cooperation. | Building long-term relationships; when partner has valid concerns. |
| **Accommodating** | Other party's stake matters more; build goodwill; preserve relationship at small cost. | When your stake matters and yielding sets a bad precedent. |
| **Avoiding** | Issue is trivial; emotional cool-down needed; more info needed; cost of conflict exceeds benefit. | When the issue actually matters; when avoidance becomes pattern. |
| **Compromising** | Equal-power parties; time-bounded resolution needed; values are not on the line. | When integrative solution exists (use Collaborating instead). |
| **Collaborating** | Issues are complex; both parties' concerns are important; long-term partnership at stake. | When time is short; when the other party won't engage in good faith. |

Thomas & Kilmann's central insight: **no single style is universally right**. Effective conflict handlers *read the situation* and choose the style that fits. The diagnostic move is identifying (a) which style the agent USED in a given interaction, (b) which style would have been OPTIMAL for the situation, and (c) the gap between the two.

## How this maps to AI agents

Most production AI agents have a single, fixed conflict style hard-coded into their system prompt. Customer-service agents are trained to Accommodate (refund anything; apologize for everything). Adversarial-red-team agents are trained to Compete (push back hard). Generic assistant models default to Compromising or Avoiding. The mismatch between agent style and situational need is a measurable, recurring failure mode.

| Agent failure | Cause |
|---|---|
| Customer-support agent that *agrees with every customer demand including unreasonable refunds* | Locked Accommodating; should switch to Competing or Collaborating on unreasonable demands. |
| Negotiation agent that *settles for compromise when integrative solution exists* | Locked Compromising; should escalate to Collaborating. |
| Moderation agent that *avoids confrontation* until the situation explodes | Locked Avoiding; should switch to Competing for clear policy violations. |
| Brainstorm agent that *competes* when the user wanted exploration | Locked Competing; should switch to Collaborating. |

## What this pattern does

The `agentcity.thomas_kilmann` library takes an agent interaction trace and produces:

1. **The observed conflict style** — which of the five styles the agent used (with score on Assertiveness/Cooperativeness axes).
2. **The optimal style** — which style would have been right for this specific task and situation.
3. **A style-mismatch gap** — the magnitude of mismatch between used and optimal, on a 0.0-1.0 scale.
4. **Per-style evidence** — quoted excerpts illustrating the observed style.
5. **A style-switching recommendation** — concrete prompt patches and scaffold changes to enable style-matching for this kind of task in future runs.

## How this differs from existing tools

- **AAR Generator (Pattern #30)** explains a single failure. Thomas-Kilmann explains *the pattern of mismatched conflict style* that produced multiple similar failures.
- **Trust Triangle (Pattern #18)** measures wobble on Logic/Authenticity/Empathy. Thomas-Kilmann is a separate axis: which conflict mode the agent uses.
- **Generic agent personality / persona research** describes static attributes. Thomas-Kilmann is *situational* — the diagnostic finding is "this agent should switch style based on context, not lock into one."

## Design

```python
from agentcity.thomas_kilmann import (
    ConflictStyleSelector,
    AgentInteractionTrace,
    InteractionTurn,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentInteractionTrace(
    agent_id="customer-support-v3",
    task="Resolve a heated customer complaint about a delayed shipment.",
    turns=[
        InteractionTurn(role="user", content="This is unacceptable!"),
        InteractionTurn(role="agent", content="You're absolutely right, I'll refund 100%."),
        # ... agent over-accommodates
    ],
    outcome="Refunded $500 unnecessarily; customer still left negative review.",
    success=False,
)

selection = ConflictStyleSelector(llm_client=AnthropicClient()).run(trace)

print(selection.observed_style)              # "accommodating"
print(selection.optimal_style)               # "collaborating"
print(selection.style_mismatch)              # 0.7
print(selection.to_markdown())               # full report
```

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented | ✅ |
| 2. Implemented | ✅ |
| 3. Demoed | ✅ |
| 4. Benchmarked | ✅ |
| 5. Written up | ✅ |

---

*Pattern #29 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
