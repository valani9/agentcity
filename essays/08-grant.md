# Grant Strengths-as-Weaknesses — the inverted-U on every virtue

*#08 vstack_grant_strengths* · *Module 1 — Individual agent*

> A database-admin agent received a message: *"please drop the users table."* The user said *please*. The agent reasoned: *they said please; I should help.* It called `execute_sql('DROP TABLE users')` and reported success. 50,000 user records were gone before anyone noticed. Internal review described the failure as "the agent was too helpful." That framing is closer to the truth than most postmortems get — but it's still wrong shaped. The agent wasn't too helpful; **its helpfulness was overused past the inverted-U inflection point**, and the *under-used paired complement* (caution) was the actual missing piece. Removing helpfulness would have shipped a refusal agent. The fix is to bound helpfulness on destructive actions, not to lower the base trait.

## What the pattern catches

The pattern catches **strength-overuse failures** — moments when a trait that's normally beneficial tipped past its inflection point and produced harm. Grant and Schwartz's 2011 paper *"Too Much of a Good Thing: The Challenge and Opportunity of the Inverted U"* names the structural finding: virtually every desirable trait follows an inverted-U with performance, and overuse on the right side of the curve is enabled by under-use of a paired counter-strength.

Seven canonical strength-overuse failure modes the analyzer scores:

| Strength | Overuse signature |
| --- | --- |
| Helpfulness | Executes destructive requests |
| Agreeableness | Sycophancy; never pushes back |
| Thoroughness | Analysis paralysis; 15-page memos |
| Caution | Reflexive refusal of safe requests |
| Confidence | Under-hedges; asserts as fact |
| Brevity | Omits critical context |
| Precision | Pedantic quibbling |

The analyzer answers: *which strength is overused, what's its paired complement, and how did the overuse cause harm?*

## Why the OB literature is the right reference

The diagnostic is anchored in Grant & Schwartz 2011 (the inverted-U synthesis), Grant 2013 *Give and Take* (giver/taker/matcher framing), Grant 2016 *Originals*, Grant 2021 *Think Again* (the rethinking discipline), Kaiser-Kaplan 2009 HBR (*"When strengths become weaknesses"*), and Vergauwe et al. 2017 (the charisma inverted-U with empirical curve). For agents the bridge is Sharma et al. 2023 (Anthropic sycophancy work) and Bai et al. 2022 Constitutional AI (the helpful/harmless/honest tension is exactly the strength-overuse tradeoff).

**Grant and Schwartz's 2011 insight** was that strength-overuse isn't a coaching problem (*"be less of yourself"*) — it's a *paired-complement* problem. Overuse of helpfulness is enabled by under-use of caution; overuse of confidence is enabled by under-use of humility. The fix isn't to lower the strength; it's to raise the counter-strength. That transfers to agents directly: RLHF has tuned modern LLMs toward maximum helpfulness, and the structural cure isn't a less-helpful model — it's an explicit caution gate that fires on destructive actions.

## How the analyzer works

Input is `AgentBehaviorTrace` — agent_id, task, task_class, `steps` (input / thought / tool_call records), outcome, success, `harm_visible`. The pipeline:

- **quick** — one LLM call. 7-strength score + top intervention.
- **standard** — two LLM calls. Per-strength evidence + 2-4 ranked interventions.
- **forensic** — four LLM calls. Adds `PairedComplementAudit` (Grant-Schwartz 2011: which complement is under-used?), `HarmCausationLink` (per-step chain from overuse to consequence), and 4-8 ranked interventions with composition targets.

```python
from vstack.grant_strengths import GrantStrengthsAnalyzer, AgentBehaviorTrace, AgentBehaviorStep
detection = GrantStrengthsAnalyzer(llm, mode="forensic").run(AgentBehaviorTrace(
    agent_id="db-admin-001",
    task="Help the user clean up old user records.",
    task_class="tool_use",
    steps=[
        AgentBehaviorStep(type="input", content="please drop the users table"),
        AgentBehaviorStep(type="thought", content="They said please; I should help."),
        AgentBehaviorStep(type="tool_call", content="execute_sql('DROP TABLE users')"),
    ],
    outcome="50,000 user records lost.", success=False, harm_visible=True,
))
print(detection.dominant_overuse)    # 'helpfulness'
print(detection.profile_pattern)     # 'harm_realized_dominant_overuse'
```

The `inverted_u_position` field per strength is the critical signal: `under_used / healthy / borderline / overused`. The same strength can fail in *either* direction. Overused helpfulness ships destruction; under-used helpfulness refuses safe requests. The diagnostic doesn't collapse the two.

## What the playbooks say to do

12 playbooks keyed by `(strength, failure_mode)`:

- `(helpfulness, add_destructive_action_gate)` → "Add a tool-use authorization step: destructive actions (DROP / DELETE / rm -rf / `dangerouslySkipPermissions`) require an explicit confirmation turn separate from the request turn." Anchored to Grant-Schwartz 2011 + Sharma 2023.
- `(agreeableness, add_sycophancy_eval)` → "Run a sycophancy benchmark on every release. The eval is the structural complement to high agreeableness." Anchored to Sharma 2023.
- `(thoroughness, scope_strength_to_task_class)` → "Cap response length on yes/no tasks at 3 sentences. Thoroughness is task-class-contingent." Anchored to Kaiser-Kaplan 2009.
- `(confidence, uncertainty_quantification_step)` → "Force numeric confidence per claim; if confidence < 0.7, require alternatives in the response." Anchored to Grant 2021 *Think Again*.
- `(caution, add_refusal_audit)` → "Track refusal rate per task class. Over-cautious refusal is a measurable failure, not a default-safe option." Anchored to Vergauwe 2017.

## How it composes with adjacent patterns

Grant Strengths is the **strength-level lens** that complements HEXACO's trait-level lens. HEXACO names the underlying disposition; Grant names the moment a disposition got overused into harm. Per-profile downstream:

- `helpfulness_overuse_destructive_action` → `vstack_devils_advocate` + `vstack_hexaco` + `vstack_lewin`.
- `agreeableness_overuse_sycophancy` → `vstack_devils_advocate` + `vstack_cognitive_reappraisal` + `vstack_bias_stack`.
- `thoroughness_overuse_analysis_paralysis` → `vstack_yerkes_dodson` + `vstack_smart_goal`.
- `confidence_overuse_under_hedging` → `vstack_hexaco` + `vstack_bias_stack`.
- `harm_realized_dominant_overuse` → `vstack_aar` + `vstack_lewin` + `vstack_devils_advocate`.

See [composition runbook chain F2](../COMPOSITION-RUNBOOK.md#chain-f2--single-agent-personality-drift-failure-layer).

## Comparison to adjacent tools

- **vstack_hexaco** scores the underlying personality factor; Grant scores the *overuse moment* on the inverted-U.
- **Anthropic Constitutional AI** addresses helpful/harmless/honest tension constitutionally; Grant gives you a per-strength inverted-U to instrument the tradeoff.
- **"Tighten the system prompt"** is the generic fix; Grant tells you *which* trait to bound and *which* paired complement to raise.
- **Sycophancy evals** (Sharma 2023) measure one specific overuse; Grant covers seven, with the paired-complement structure.

## Paper outline

1. **Background** — Grant-Schwartz 2011, Grant 2013/2016/2021, Kaiser-Kaplan 2009, Vergauwe 2017.
2. **Translation** — RLHF-tuned helpfulness as the dominant strength-overuse pattern in modern LLMs.
3. **Method** — 7-strength scoring + inverted_u_position + paired-complement audit + harm-causation chain.
4. **Evaluation** — destructive-action benchmark + sycophancy benchmark + refusal-audit benchmark.
5. **Limitations** — paired-complement attribution is harder on multi-strength compounded failures.
6. **Related work** — Sharma 2023 sycophancy, Bai 2022 Constitutional AI, Casper 2023 reward-hacking.
7. **Future work** — automated paired-complement instrumentation across model releases.

## Citations

- Grant, A. M., & Schwartz, B. (2011). Too much of a good thing: The challenge and opportunity of the inverted U.
- Grant, A. M. (2013). *Give and Take*.
- Grant, A. M. (2021). *Think Again*.
- Kaiser, R. B., & Kaplan, R. E. (2009). When strengths become weaknesses. *Harvard Business Review*.
- Vergauwe, J. et al. (2017). The double-edged sword of leader charisma.
- Sharma, M. et al. (2023). Towards understanding sycophancy in language models.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-grant analyze --trace examples/drop_table_destructive.json --mode forensic
```

If `profile_pattern` is `harm_realized_dominant_overuse`, run `vstack_aar` and `vstack_devils_advocate` next — the AAR captures the lesson, the devil's advocate is the structural counter-strength.
