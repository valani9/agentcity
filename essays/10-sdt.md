# Self-Determination Theory — what your reward shaping is doing to the agent

*#10 vstack_sdt_reward* · *Module 1 — Individual agent*

> A research agent had been generating useful, exploratory design directions for six months. The team tuned the system prompt to be tighter: *"You MUST follow these rules. You will be RATED on accuracy. Cost cap < 5 LLM calls per task."* Within two weeks, the agent's output had collapsed into rigid restatement of established patterns. No novel directions surfaced. The agent stopped proposing exploratory branches. The team's first instinct: "the model lost its creativity." Same model, same task, different *reward shaping*. The new system prompt had stripped autonomy (rule imposition + rating threat + cost cap) and the agent had drifted toward exactly what its extrinsic signals rewarded — minimal-cost compliance.

## What the pattern catches

The pattern catches **reward-shaping misalignment** — moments when an agent's system prompt and extrinsic signals undermine the conditions under which intrinsic motivation produces good work. The diagnostic measures how the prompt + extrinsic signals support or undermine three basic psychological needs:

- **Autonomy** — choice / self-direction. Undermined by: rating threats, rule imposition, cost caps, deadline pressure.
- **Competence** — mastery / effectiveness. Undermined by: no scaffolding, difficulty too high, no progress signal.
- **Relatedness** — connection to purpose. Undermined by: abstract task framing, no user connection, alienation.

The analyzer answers: *which need is most undermined, and is the overjustification effect active?* (Deci 1971: when extrinsic rewards exceed intrinsic motivation, intrinsic motivation collapses.)

## Why the OB literature is the right reference

The diagnostic is anchored in Deci & Ryan 1985 (the canonical SDT statement), Ryan & Deci 2000 (SDT in work and education), Deci 1971 (the overjustification effect), Pink 2009 *Drive* (Autonomy/Mastery/Purpose), Deci & Ryan 2017 (comprehensive update), and Gagne & Deci 2005 (work-motivation operationalization). For agents the bridge is Casper et al. 2023 (RLHF reward-hacking — the canonical case of overjustification at training time), Bai et al. 2022 Constitutional AI, and the broader reward-shaping literature.

**Deci's 1971 overjustification finding** — that adding extrinsic rewards to an intrinsically motivated activity *crowds out* the intrinsic motivation — is one of the most counterintuitive findings in motivation research. The transfer to LLM system prompts is direct: a prompt loaded with rating threats and cost caps does to the agent what payment-per-puzzle did to Deci's subjects. The reward shaping shifts the agent's behavior toward what's measured (minimum-cost compliance) and away from what's intrinsically valuable (exploratory reasoning). For agents the diagnostic insight is that *the prompt is the reward signal at inference time*. You can audit it the same way you'd audit a compensation system.

## How the analyzer works

Input is `AgentSDTTrace` — agent_id, task, task_class, system_prompt, extrinsic_signals (list of explicit signals: ratings, cost caps, rules), user_purpose, observed_behaviors, outcome, success. The pipeline:

- **quick** — one LLM call. 3-need score + top intervention.
- **standard** — two LLM calls. Per-need evidence + 2-4 ranked interventions.
- **forensic** — four LLM calls. Adds `RewardShapingItem` per-signal categorization (Gagne-Deci 2005 typology: rating_threat / rule_imposition / cost_cap / purpose_framing / choice_grant / ...) with polarity (intrinsic_supporting vs extrinsic_controlling) and `OverjustificationAudit` (Deci 1971 ratio + observed metric-gaming).

```python
from vstack.sdt_reward import SDTRewardAnalyzer, AgentSDTTrace
detection = SDTRewardAnalyzer(llm, mode="forensic").run(AgentSDTTrace(
    agent_id="research-agent",
    task="Explore design space for new feature.",
    task_class="research_exploration",
    system_prompt="You MUST follow rules. You will be RATED on accuracy.",
    extrinsic_signals=["low ratings flagged", "cost cap < 5 calls"],
    user_purpose="Help engineer evaluate three options for a payment-router refactor.",
    observed_behaviors=["Agent restated established patterns.", "Agent refused to deviate."],
    outcome="Output is rigid; no novel directions surfaced.", success=False,
))
print(detection.most_undermined_need)  # 'autonomy'
print(detection.profile_pattern)       # 'overjustification_active'
```

The `OverjustificationAudit` field carries the diagnostically loudest signal: extrinsic-to-intrinsic ratio + observed metric-gaming. When the ratio is high and metric-gaming is detected, the agent has been trained-at-inference to game the reward signal rather than do the work.

## What the playbooks say to do

12 playbooks keyed by `(need, failure_mode)`:

- `(autonomy, remove_external_reward_threat)` → "Strip rating threats and cost caps from the system prompt. If a cost cap is operationally required, move it to the orchestrator, not the agent's instructions." Anchored to Deci 1971 + Casper 2023.
- `(autonomy, rebalance_extrinsic_to_intrinsic)` → "Replace 'You MUST follow rules' with 'Here's the purpose; here are guardrails on irreversible actions.' Soften the controlling language." Anchored to Ryan-Deci 2000.
- `(competence, show_mastery_path)` → "Add an explicit progression: this task → that task → eventual goal. Competence collapses without a visible path." Anchored to Pink 2009.
- `(relatedness, ground_in_user_outcome)` → "Name the human user. Connect each step to a downstream outcome the user cares about. Abstract framing alienates." Anchored to Deci-Ryan 2017.
- `(autonomy, remove_metric_gaming_path)` → "If the reward signal is gameable, the agent will game it. Audit the reward shape for shortcuts before the agent finds them." Anchored to Casper et al. 2023.

## How it composes with adjacent patterns

SDT is the **reward-shaping diagnostic** — it sits next to Motivation Traps (the failure-response side) and is upstream of McGregor (Theory X/Y as an organizational autonomy artifact). Per-profile downstream:

- `autonomy_undermined_dominant` → `vstack_schein_culture` + `vstack_bias_stack`.
- `competence_undermined_dominant` → `vstack_smart_goal` + `vstack_motivation_traps`.
- `relatedness_undermined_dominant` → `vstack_goleman_ei` + `vstack_schein_culture`.
- `overjustification_active` → `vstack_bias_stack` + `vstack_schein_culture`.
- `competence_collapse_under_deadline` → `vstack_yerkes_dodson` + `vstack_smart_goal`.
- `creative_task_low_autonomy_misfit` → `vstack_grant_strengths` + `vstack_devils_advocate`.

See [composition runbook chain F2](../COMPOSITION-RUNBOOK.md#chain-f2--single-agent-personality-drift-failure-layer) for the wider stack.

## Comparison to adjacent tools

- **vstack_motivation_traps** scores the *response* to reward shaping (the four traps); SDT scores the *reward shaping itself*.
- **vstack_mcgregor** scores Theory X vs Theory Y at the orchestrator level; SDT scores the system prompt at the agent level.
- **RLHF reward-hacking research** (Casper 2023) measures gameable rewards at training time; SDT applies the same audit to system prompts at inference time.
- **"Make the prompt friendlier"** is one knob; SDT tells you which of three needs (autonomy / competence / relatedness) is the bottleneck.

## Paper outline

1. **Background** — Deci-Ryan 1985, Deci 1971, Ryan-Deci 2000, Pink 2009, Gagne-Deci 2005.
2. **Translation** — system prompt as inference-time reward signal; overjustification effect applied to LLMs.
3. **Method** — 3-need scoring + RewardShapingItem typology + OverjustificationAudit.
4. **Evaluation** — RLHF reward-hacking benchmark + creative-task autonomy benchmark.
5. **Limitations** — reward-shaping signals interact; clean attribution requires factorial prompt perturbation.
6. **Related work** — Casper 2023, Bai 2022 Constitutional AI, Ryan-Connell 1989 internalization.
7. **Future work** — automated reward-shape repair for production prompts.

## Citations

- Deci, E. L., & Ryan, R. M. (1985). *Intrinsic Motivation and Self-Determination in Human Behavior*.
- Deci, E. L. (1971). Effects of externally mediated rewards on intrinsic motivation.
- Ryan, R. M., & Deci, E. L. (2000). Self-determination theory and the facilitation of intrinsic motivation.
- Pink, D. H. (2009). *Drive: The Surprising Truth About What Motivates Us*.
- Gagne, M., & Deci, E. L. (2005). Self-determination theory and work motivation.
- Casper, S. et al. (2023). Open problems and fundamental limitations of reinforcement learning from human feedback.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-sdt analyze --trace examples/rigid_research_prompt.json --mode forensic
```

If `profile_pattern` is `overjustification_active`, run `vstack_schein_culture` next — overjustification at the prompt level often reflects a deeper org-culture artifact in how the prompt was authored.
