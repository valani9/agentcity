# Lewin Attribution — was it the model, or was it the prompt?

*#01 vstack_lewin* · *Module 1 — Individual agent*

> A customer-support agent in production confidently answered that Pluto was reclassified in 2003. The user trusted it; the support ticket escalated to legal. The team's first instinct: "the model is bad at facts, let's swap to a smarter one." But the next day, with the same model, the agent got the answer right. What changed wasn't the model — it was the RAG index, which had served a stale 2003 Wikipedia revision the day before. The team would have spent two weeks fine-tuning the wrong thing.

## What the pattern catches

The default attribution most AI teams make when an agent fails is **"the model did it"** — and it's wrong most of the time. Kurt Lewin's mid-century behavior formula `B = f(P, E)` says behavior is jointly determined by Person (the model) and Environment (the scaffolding around it — prompt, tools, RAG context, orchestration). vstack_lewin scores an agent failure trace against three loci:

- **INTERNAL** — the model itself (training data, sampling parameters, version drift).
- **ENVIRONMENTAL** — everything around the model (system prompt, RAG corpus, tool definitions, observation formatting).
- **INTERACTIONAL** — the failure required both to misfire; fixing one alone won't help.

The analyzer answers: *which locus to fix first?*

## Why the OB literature is the right reference

The diagnostic is anchored in Heider 1958, Kelley 1967, Ross 1977, Gilbert & Malone 1995. **Ross's 1977 insight** was the fundamental attribution error: human observers systematically over-attribute behavior to disposition (the person) and under-attribute to situation (the environment). Engineers debugging AI agents make the same mistake — they over-attribute to the model.

Lewin's `B = f(P, E)` predates the AI ecosystem by 80 years and applies to it cleanly: AI agent behavior is jointly determined by the underlying model and its surrounding scaffolding. The fundamental attribution error transfers verbatim. So does Kelley's covariance principle — if the same model + same prompt + different RAG indexes produce different behavior, that's environmental, not internal.

## How the analyzer works

Input is `AgentFailureTrace` — agent_id, model_name, task, steps (input/tool_call/observation/output records), outcome, optional `initial_attribution`. The pipeline:

- **quick** — one LLM call. Scoring across 3 loci + top intervention.
- **standard** — two LLM calls. Full scoring + 4-6 ranked interventions.
- **forensic** — four LLM calls. Adds Kelley covariance reasoning (consensus / distinctiveness / consistency), counterfactual swap analysis ("would a different model with the same prompt have failed?"), Gilbert-Malone bias-mechanism diagnosis ("which specific FAE shortcut produced the wrong call?"), and 4-8 ranked interventions with composition targets.

```python
from vstack.lewin import LewinAttributionDetector, AgentFailureTrace
detection = LewinAttributionDetector(llm, mode="standard").run(
    AgentFailureTrace(
        agent_id="qa-bot",
        model_name="claude-opus-4-7",
        task="Answer 'When was Pluto reclassified?'",
        steps=[...],
        outcome="Confidently wrong year.",
        success=False,
        initial_attribution="model is bad at facts",
    )
)
print(detection.dominant_locus)   # 'environmental'
print(detection.initial_attribution_correct)  # False
```

The `initial_attribution_correct` field is the cleanest signal in the detection. If you came in convinced the model was bad and Lewin says no, **stop and re-read the trace** before you ship a model swap.

## What the playbooks say to do

12 playbooks anchored to specific `(locus, factor)` failure modes:

- `(environmental, rag_context)` → "Refresh the index nightly + dedupe revisions. Verify corpus freshness in CI before deploys."
- `(environmental, prompt_scaffolding)` → "Audit the system prompt for tool-call instructions that conflict with the LLM's defaults; tests should catch prompt regressions."
- `(internal, base_model)` → "Try a deliberate model swap with the SAME prompt + tools. If the swap fixes it, internal is confirmed. If not, internal was a misdiagnosis."
- `(interactional, prompt_x_model)` → "The prompt makes assumptions that aren't true for this model family. Either lift the assumption or fork the prompt per model."

## How it composes with adjacent patterns

Lewin is the **localization pass** in the post-incident chain. The full chain F1 is `AAR → Lewin → branch on locus`:

- If `internal` → run `vstack_bias_stack` (Kahneman/Tversky biases in the reasoning) or `vstack_hexaco` (personality drift).
- If `environmental` → run `vstack_glaser_conversation` (Levels I/II/III in user-agent dialogue) or `vstack_yerkes_dodson` (context overload).
- If `interactional` → run both.

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer).

## Comparison to adjacent tools

- **vstack_aar** generates universal lessons; Lewin is the *localization* pass. AAR doesn't try to attribute.
- **LangSmith / Phoenix / Helicone** show *what* happened (trace). They don't say *where the failure lives*.
- **W&B Weave / Arize evaluations** score outputs against expected outputs. They flag wrong answers; they don't tell you why.

## Paper outline

1. **Background** — Lewin 1936, Heider 1958, Kelley 1967, Ross 1977, Gilbert-Malone 1995.
2. **Translation** — why `B = f(P, E)` transfers to AI agents.
3. **Method** — the 3-locus scoring + the 4-LLM-call forensic pipeline.
4. **Evaluation** — synthetic FAE benchmark: 50 traces where the ground-truth locus is known; measure whether the analyzer + a control LLM-judge converge.
5. **Limitations** — interactional failures are hard for short traces.
6. **Related work** — root-cause analysis in distributed systems (Beschastnikh et al), AI fault localization (Bansal et al).
7. **Future work** — Bayesian update on attribution as more incidents accrue.

## Citations

- Lewin, K. (1936). *Principles of topological psychology*.
- Heider, F. (1958). *The psychology of interpersonal relations*.
- Kelley, H. H. (1967). Attribution theory in social psychology.
- Ross, L. (1977). The intuitive psychologist and his shortcomings.
- Gilbert, D. T., & Malone, P. S. (1995). The correspondence bias.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-lewin analyze --trace examples/pluto.json --mode forensic
```

If Lewin says `environmental` with `dominant_factor=rag_context`, run `vstack_glaser_conversation` on the user-agent dialogue — the conversational layer often masks an RAG staleness issue as a model issue.
