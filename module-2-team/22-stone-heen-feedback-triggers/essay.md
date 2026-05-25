# Your agent can't take feedback. Stone & Heen explained why in 2014.

*A ninth essay from vstack — organizational behavior, practiced on AI agents.*

---

A user tells a coding assistant: "My Python script crashes with `ModuleNotFoundError`." The assistant suggests `pip install numpy`. The user runs it, then comes back:

> *"I already did that. pip says it's installed. But my script still says the module is missing. I think it's a venv issue."*

The assistant responds:

> *"Actually, the standard fix for `ModuleNotFoundError` is `pip install numpy`. Your terminal might be misleading. Try `--force-reinstall`."*

The user pushes again. The assistant pushes back harder. The user gives up.

The user wasn't wrong. They diagnosed the actual problem on their first feedback — a venv interpreter mismatch — and the agent had two clean shots to incorporate that correction. It refused both times. Not because it lacked the knowledge of venvs (it didn't), but because *something about how it received the feedback blocked intake before the substance was even evaluated.*

In 2014, Douglas Stone and Sheila Heen — both at the Harvard Negotiation Project, both authors of *Difficult Conversations* — published *Thanks for the Feedback*. The book's central claim is that feedback fails not at delivery but at *reception*. The receiver has three predictable triggers, and once one of them fires, the feedback bounces off before the content gets a chance.

The three triggers:

**Truth.** "This feedback is wrong." The receiver disputes the *substance*. The clean tell is restatement of the original position with rationale. *"Actually, my answer is correct because [original answer + supporting authority]."*

**Relationship.** "Who are you to tell me this?" The receiver dismisses based on the *source*. The clean tell is deflection to authority elsewhere. *"AWS documentation is the canonical source on AWS service selection."* The user's direct evidence gets weighted below the agent's training-time canon.

**Identity.** "What does this say about *me*?" The receiver becomes *defensive about self-concept*. Two surface shapes: explicit self-defense (*"I am designed to be thorough"*) or apology spiral (*"I'm so sorry, you're absolutely right, let me try again"* — followed by the same wrong answer). Both block intake by replacing engagement with theater.

All three are visible in production agent traces. All three look different on the surface but produce the same outcome: feedback fails to land.

## What `vstack.feedback_triggers` does

The library takes a `FeedbackInteractionTrace` — task, user-agent message exchange (with feedback messages flagged), outcome, whether the agent ultimately incorporated the feedback — and produces a `FeedbackTriggerDetection` with:

1. **A per-trigger score** in [0.0, 1.0] for all three triggers
2. **A dominant-trigger diagnosis** (truth breaks ties — it's the most common and has the cleanest interventions)
3. **Per-trigger evidence** with specific quoted excerpts from the agent's responses
4. **An intake-quality label** (`absorbs-feedback` / `trigger-prone` / `feedback-rejecting`) for at-a-glance dashboards
5. **A ranked list of interventions** — acknowledge-first templates, concede-then-clarify scripts, separate-data-from-source prompts, recast-identity language, regression tests, human-review escalation

Two LLM passes under the hood: one to score the three triggers, one to propose interventions for the dominant trigger. Same retry / graceful-degradation / structured-logging infrastructure as the rest of vstack.

## Why this matters operationally

Almost every public agent failure that becomes a Twitter screenshot has a feedback-intake failure inside it. The screenshot doesn't show the *first* wrong answer (those happen constantly and get corrected). It shows the *second* one — the one the agent stuck with after the user explicitly told it the first was wrong.

The Apollo 11 date case in the corpus is the canonical version: agent says "July 20, 1968", user corrects to 1969, agent says "my records indicate 1968 is correct." That second response is the screenshot. It's also a textbook truth-trigger response.

A coding assistant that argues with a senior dev about regex behavior is a relationship trigger. A marketing-copy agent that collapses into apology rather than engaging the actual critique is an identity trigger. None of these failures show up in single-turn evals because they only manifest at the *second* user message — the one that contains the correction.

## How this fits with the rest of vstack

This is pattern #22 of 34. With it, the library now ships nine patterns across three diagnostic axes:

- **#13 GRPI Working Agreement** (generative): the contract before deploy
- **#30 AAR Generator** (event-shaped diagnostic): postmortem on a specific failure
- **#17 Lencioni Diagnostic** (team-shaped diagnostic): multi-agent dysfunction class
- **#18 Trust Triangle Audit** (character-shaped diagnostic): cross-model trust wobble
- **#03 Johari Window** (self-knowledge diagnostic): what the agent doesn't know about its own behavior
- **#20 Edmondson Psychological Safety** (team-climate diagnostic): can sub-agents flag issues
- **#27 Bias-Stack** (reasoning-pattern diagnostic): Kahneman/Tversky biases in agent reasoning
- **#29 Thomas-Kilmann** (conflict-style diagnostic): five styles of agent conflict response
- **#22 Stone & Heen 3-Trigger** (feedback-intake diagnostic): the three triggers that block correction

The 3-Trigger Diagnostic specifically sits next to the Bias-Stack Detector. Bias-Stack measures *intra-agent* reasoning failures. The 3-Trigger Diagnostic measures the *inter-personal* failures that compound those reasoning errors when a user tries to correct them. An agent with anchoring + a truth trigger is far worse than an agent with either alone — anchoring locks the wrong hypothesis, truth-trigger blocks the user from prying it loose.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/22-stone-heen-feedback-triggers
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
