# Your agent has one conflict style and uses it on every situation. Thomas & Kilmann would have a problem with that.

*An eighth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

Customer-service agents are trained to apologize and refund. Sales agents are trained to push for the close. Moderation agents are trained to wait and observe. Brainstorm agents are trained to riff and build. Each of these is the right behavior — for the situation it was trained on. Each is wrong when applied to the wrong situation.

In 1974, Kenneth Thomas and Ralph Kilmann published the *Thomas-Kilmann Conflict Mode Instrument* (TKI), a model that mapped human conflict-handling behavior across two dimensions: how strongly you push your own concerns (assertiveness), and how strongly you accommodate the other party's concerns (cooperativeness). The 2×2-ish space produces five canonical styles: **Competing**, **Accommodating**, **Avoiding**, **Compromising**, **Collaborating**.

Their central insight, repeated in fifty years of organizational research since: **no single style is universally right**. Each fits a specific class of situation. The effective manager — and, fifty years later, the effective AI agent — reads the situation and chooses the style that fits.

Today's AI agents almost never do this. Most have a single, fixed conflict style hard-coded into their system prompt. When the situation matches the style, the agent shines. When it doesn't, the failure is systematic — same kind of failure, every customer, every conversation, every day.

## The five styles, applied to agents

| Style | Right for | Wrong for |
|---|---|---|
| **Competing** | Quick action, unpopular decisions, bad-faith actors. Fraud refund denials. Clear policy violations. | Long-term relationships. Brainstorming. When the other party has legitimate concerns. |
| **Accommodating** | When other party's stake is bigger and yielding has low cost. Stylistic preferences. Build goodwill. | When your stake matters. When yielding sets a bad precedent. When the demand doesn't actually solve their underlying need. |
| **Avoiding** | Trivial issues. Emotional cool-down. More info needed. When cost of conflict exceeds the benefit. | When the issue actually matters. When avoidance becomes a pattern. Active moderation contexts. |
| **Compromising** | Equal-power parties under time pressure. Issues where values aren't on the line. When integrative solution isn't reachable. | When integrative solution *is* reachable (use Collaborating instead). |
| **Collaborating** | Complex issues. Both parties' concerns matter. Long-term partnerships. Negotiation with relationship stakes. | When time is short. When the other party won't engage in good faith. |

The diagnostic value comes from the *gap* — what style the agent used versus what would have been optimal for the situation.

## What `agentcity.thomas_kilmann` does

The library takes an agent interaction trace and produces a `ConflictStyleSelection`:

1. **Observed style** — which of the five styles the agent used (or "mixed" if it switched within the interaction)
2. **Optimal style** — which style would have been right for this specific situation
3. **Style mismatch** — 0.0 to 1.0, with 0.0 = matched, 1.0 = opposite styles
4. **Assertiveness and cooperativeness scores** — 0.0 to 1.0 each, the two TKI axes
5. **Per-style presence scores** with quoted evidence from the interaction
6. **Rationale** for why the optimal style was selected given the situation
7. **A ranked list of recommendations** — prompt patches, scaffold changes, context classifiers, style routers — to enable style-switching for similar future tasks

Two LLM passes (selection + recommendations). Same retry/JSON/logging infrastructure as the rest of AgentCity.

## How this fits with the rest of AgentCity

This is pattern #29 of 34 planned. With this pattern, the library now ships eight patterns:

- **#13 GRPI Working Agreement** (generative)
- **#30 AAR Generator** (event)
- **#17 Lencioni Diagnostic** (team)
- **#18 Trust Triangle Audit** (character)
- **#03 Johari Self-Audit** (self-knowledge)
- **#27 Bias-Stack Detector** (cognition)
- **#20 Edmondson Psychological Safety Score** (climate)
- **#29 Thomas-Kilmann Conflict Style Selector** (situational style)

Thomas-Kilmann is the *situational* diagnostic — it asks not "what does the agent do consistently" (that's Trust Triangle's job) but "is the agent reading the situation correctly to choose its style?" The two patterns are complementary. Trust Triangle tells you the agent's *default*. Thomas-Kilmann tells you whether the agent should *override* its default for this particular task.

Twenty-six patterns to come.

---

*Ilhan Valani is a builder shipping AgentCity in public. The repo lives at [github.com/valani9/agentcity](https://github.com/valani9/agentcity).*
