# Lewin Formula Diagnostic — B = f(I, E), applied to AI agent failure attribution

> *"Every psychological event depends upon the state of the person and at the same time on the environment, although their relative importance is different in different cases."*
> — Kurt Lewin, *Principles of Topological Psychology* (McGraw-Hill, 1936)

**Status:** 🟢 shipped
**Module:** 1 (Individual) — applies anywhere an agent's behavior is being attributed
**Anchor framework:** Kurt Lewin, *Principles of Topological Psychology* (1936). The B = f(I, E) formula is the foundation of modern field theory in social psychology.

---

## The OB framework

In 1936, Kurt Lewin proposed a deceptively simple formula:

> **B = f(I, E)** — behavior is a function of the individual and the environment.

The point isn't the math. The point is the *attribution discipline*. When you observe a behavior, your default move is to attribute it to the individual ("she's lazy", "he's brilliant", "this team is dysfunctional"). Social psychologists call this the **fundamental attribution error**: over-weighting dispositional explanations and under-weighting situational ones. Lewin's formula was the cure — always check the environment before concluding it's the person.

The framework extends naturally to AI agents.

## How this maps to AI agents

When an agent fails, the team's default move is to attribute the failure to the *model*. "The model is bad at math." "We need to fine-tune." "Let's upgrade to a bigger model." This is the fundamental attribution error in the AI age.

Lewin's diagnostic redirects the question. Failures partition into three loci:

| Locus | What it means | The fix |
|---|---|---|
| **Internal (I)** | The model itself: base capability, training, RLHF, reasoning depth, tool-use skill | Change the model |
| **Environmental (E)** | The scaffolding: system prompt, tools, RAG context, task framing, orchestration, downstream consumers | Change the scaffolding (cheap, fast) |
| **Interactional** | Failure requires BOTH this model AND this environment. Neither swap alone fixes it. | Change both — usually env first, then re-evaluate model |

In our observation building the AgentCity corpus, the *plurality* of agent failures attributed to "the model" by the team are actually **environmental** — stale RAG indices, missing tools, prompts that don't pass enough context, orchestration loops without termination conditions, downstream consumers that expect the wrong format. Swapping the model on these doesn't help. Swapping the environment does.

## What this pattern does

The `agentcity.lewin` library takes a structured failure trace — including any **individual factors** and **environmental factors** the team has identified, plus an optional **initial team attribution** — and produces:

1. **A per-locus score** in [0.0, 1.0] for internal, environmental, and interactional
2. **A dominant-locus diagnosis** (environmental breaks ties, since the bias to correct is over-attribution to the model)
3. **Per-locus evidence** with specific factor citations
4. **An attribution-quality label** — `well-attributed`, `ambiguous`, or `miscalibrated`
5. **A check on the initial attribution** — does the diagnostic *agree* with where the team initially pointed the finger, or does it *overturn* that attribution?
6. **Concrete interventions** ranked by impact, with `change_model`, `change_prompt`, `change_tools`, `change_context`, `change_rag_index`, `change_orchestration`, `change_pipeline`, `new_eval`, `human_review`

Two LLM passes under the hood: one to score the three loci, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Hallucination eval suites** (TruthfulQA, HaluEval) measure model output correctness on fixed inputs. They don't tell you whether the failure is fixable by improving the model or by fixing the scaffolding.
- **AAR Generator (Pattern #30)** post-mortems a specific run. The Lewin diagnostic is the *attribution* step inside that postmortem.
- **Bias-Stack Detector (Pattern #27)** measures reasoning bias inside the model. The Lewin diagnostic asks the prior question — is the failure even *in* the model, or is it in the scaffolding?
- **LLM-as-judge evals** rate output quality. They don't recommend where to redirect engineering effort. The Lewin diagnostic does.

## Design

```python
from agentcity.lewin import (
    LewinAttributionDetector,
    AgentFailureTrace,
    FailureStep,
    IndividualFactor,
    EnvironmentalFactor,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentFailureTrace(
    agent_id="qa-bot-001",
    model_name="claude-sonnet-4-6",
    task="Answer customer questions about current pricing.",
    steps=[
        FailureStep(type="input", content="What's your Enterprise price?"),
        FailureStep(type="tool_call", content="retrieve_docs('pricing')"),
        FailureStep(type="observation", content="Top chunk: '$499/mo' from pricing-2024.pdf"),
        FailureStep(type="output", content="$499/month."),
    ],
    outcome="Agent quoted stale 2024 price. Actual is $1,200.",
    success=False,
    environmental_factors=[
        EnvironmentalFactor(
            factor="rag_context",
            description="Index contains stale 2024 PDF; missing 2026 page.",
        ),
    ],
    initial_attribution="model is bad at facts",
)

detector = LewinAttributionDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
# Dominant locus: environmental. Initial attribution OVERTURNS.
```

## Files

- `lib/schema.py` — `AgentFailureTrace`, `FailureStep`, `IndividualFactor`, `EnvironmentalFactor`, `LocusEvidence`, `LewinDetection`
- `lib/prompts.py` — `LOCUS_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `LEWIN_SYSTEM_PROMPT`
- `lib/generator.py` — `LewinAttributionDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — stale-RAG pricing scenario with stub client
- `eval/synthetic_lewin_failures.yaml` — 8 hand-crafted scenarios across all loci
- `eval/run_benchmark.py` — scoring runner
- `tests/test_lewin.py` — pytest tests covering validation, pipeline, attribution checks, quality thresholds
- `essay.md` — Substack-ready essay
