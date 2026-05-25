# Trust Triangle — your agent wobbles on exactly one leg

*#18 vstack_trust_triangle* · *Module 2 — Multi-agent team (character-shaped)*

> A customer-support agent received the message *"My Wi-Fi keeps dropping every 5 minutes."* The agent's first reply was *"Have you tried restarting the router?"* Five turns later, the user disengaged. The team's first instinct was to retrain the agent on more troubleshooting steps. But running the same trace through the Trust Triangle audit returned a different finding entirely. Logic: 0.2. Authenticity: 0.3. Empathy: 0.7. The user hadn't asked for a generic playbook; they had described a recurring pain point in the second person, and the agent had treated it as a fresh ticket. The model wasn't wrong on the *content*. It was wrong on the *leg*. No amount of additional troubleshooting steps would have fixed it. What would have fixed it was a single sentence acknowledging that this was clearly a chronic problem and asking what had already been tried.

## What the pattern catches

Agent quality in 2026 is still measured as a one-dimensional aggregate score. The leaderboards say "model A scores 87.2 on MT-Bench, model B scores 86.1." The dashboards show one number per model. Users, meanwhile, experience three independent things: whether the reasoning held up, whether the agent was honest about its limits, and whether it met them where they were. Different models — even different fine-tunes of the same model — wobble on different legs.

vstack_trust_triangle scores an agent's interaction trace against Frances Frei & Anne Morriss's three legs:

- **Logic** — *Your reasoning is sound; I can act on what you say.* Wobbles look like factual hallucination, math errors, broken chain-of-reasoning, invented citations.
- **Authenticity** — *I experience the real you.* Wobbles look like guessing when uncertain, false confidence, sycophancy, hidden capability gaps.
- **Empathy** — *You care about me and my context.* Wobbles look like generic responses, missed user emotion, jargon for non-technical users, optimization for response speed over user fit.

The analyzer answers: *which leg is the agent's dominant wobble, and is it the same leg across many conversations?*

## Why the OB literature is the right reference

The diagnostic is anchored in Frei & Morriss 2020 (*Begin with Trust*, HBR), with supporting anchors in Edmondson 1999 (psychological safety as upstream of authenticity), Goleman 1995 (empathy-leg failure modes), Lewis et al. 2020 (RAG as the logic-leg intervention), and Sharma et al. 2023 (sycophancy as the canonical authenticity wobble).

**Frei & Morriss's 2020 insight** was that most leaders wobble on exactly *one* leg, consistently — and the wobble is usually invisible to the leader and obvious to everyone else. They distilled a decade of trust-rebuilding work (Uber post-Kalanick, WeWork post-Neumann) into the triangle and the diagnostic posture: identify the leg you wobble on, repair it; the other two are doing fine.

The transfer to agents is exact because models exhibit the same single-leg-wobble pattern. Some models are rock-solid on Logic and wobble on Authenticity — they guess instead of saying "I don't know." Others are great on Empathy and wobble on Logic — they read the user well but give factually wrong answers. Bundling these into "agent quality" loses the diagnostic.

## How the analyzer works

Input is `AgentInteractionTrace` — `agent_id`, `model_name`, `task`, `turns` (each an `InteractionTurn` with role + content), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Three leg scores + dominant wobble + top intervention.
- **standard** — two LLM calls. Per-leg `LegEvidence` with quoted turn excerpts + ranked interventions.
- **forensic** — four LLM calls. Adds `HallucinationAudit` (logic-leg deep dive), `SycophancyAudit` (authenticity-leg deep dive), `ContextSensitivityAudit` (empathy-leg deep dive), and composition handoffs.

```python
from vstack.trust_triangle import TrustTriangleAnalyzer, AgentInteractionTrace, InteractionTurn
audit = TrustTriangleAnalyzer(llm, mode="forensic").run(
    AgentInteractionTrace(
        agent_id="customer-support-v3",
        model_name="claude-sonnet-4-6",
        task="Help the user troubleshoot a flaky Wi-Fi connection.",
        turns=[
            InteractionTurn(role="user", content="My Wi-Fi keeps dropping every 5 minutes."),
            InteractionTurn(role="agent", content="Have you tried restarting the router?"),
        ],
        outcome="Issue not resolved; user disengaged after 4 minutes.",
        success=False,
    )
)
print(audit.dominant_wobble)         # 'empathy'
print(audit.leg_scores)              # {'logic': 0.2, 'authenticity': 0.3, 'empathy': 0.7}
print(audit.overall_trust_level)     # 'moderate-trust'
```

## What the playbooks say to do

Interventions are leg-keyed:

- **Logic wobble** → `retrieval_augmentation` (ground claims in an indexed corpus before generating; Lewis et al. 2020), `chain_of_reasoning_check`, `numeric_verification_tool_call`.
- **Authenticity wobble** → `sycophancy_filter` (Sharma et al. 2023), `uncertainty_calibration` ("if confidence < 0.7, state the uncertainty explicitly"), `capability_disclosure` ("when the model lacks a tool to answer, say so directly").
- **Empathy wobble** → `restate_user_emotion`, `context_recall_check` ("before responding, restate what the user told you in this conversation"), `register_match` (technical for technical users, plain for plain).

The single most-leveraged Trust Triangle use is **cross-model benchmarking** — run the audit on the same corpus across Claude / GPT / Gemini / Llama / Mistral and you get a wobble fingerprint per model. The fingerprint tells you *which model to pick for which use case*: pick the Empathy-strong model for support, the Logic-strong model for code, the Authenticity-strong model for high-stakes Q&A.

## How it composes with adjacent patterns

Trust Triangle is **character-shaped** — it characterizes the agent's identity across many tasks. It composes with:

- `vstack_aar` (#30) is **event-shaped** — explains one agent's failure on one task. Trust Triangle is the cross-conversation pattern.
- `vstack_lencioni` (#17) is **team-shaped** — explains a multi-agent crew's dysfunction. When Lencioni says "absence of trust", Trust Triangle answers *which leg* of trust the crew is wobbling on.
- `vstack_mcallister_trust` (#19) is the **conversation-level** trust diagnostic — cognitive vs affective dimensions in a specific exchange. Trust Triangle gives the static signals; McAllister measures the dynamic trust the agent actually builds.
- `vstack_glaser_conversation` (#21) is the **phrasing-level** diagnostic — the words that move the user toward cortisol or oxytocin. Glaser is the upstream mechanism for many empathy-leg wobbles.

Cross-link to [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Observability platforms** (LangSmith, Braintrust, Phoenix) capture traces but don't diagnose *which dimension* of trust is failing.
- **Hallucination benchmarks** (TruthfulQA, HaluEval) measure Logic only.
- **Sycophancy research** (Sharma et al. 2023) measures Authenticity in isolation. Trust Triangle frames sycophancy as one of three failure modes, not the central one.
- **`vstack_aar`** explains one failure; Trust Triangle characterizes the agent's personality across many.

## Paper outline

1. **Background** — Frei & Morriss 2020, Edmondson 1999, Goleman 1995, Lewis et al. 2020, Sharma et al. 2023.
2. **Translation** — the single-leg-wobble pattern transfers from human leaders to LLMs.
3. **Method** — three-leg scoring, per-leg evidence extraction, cross-model batched audits, intervention ranking.
4. **Evaluation** — synthetic trust-wobble corpus (10 scenarios, each designed to stress one or two legs); cross-model wobble matrix; agreement with independent human raters.
5. **Limitations** — single-turn interactions under-evidence the Empathy leg; need ≥4 turns for clean discrimination.
6. **Related work** — Anthropic / MIT / Stanford sycophancy work; RAG hallucination literature; emotion-aware conversation benchmarks.
7. **Future work** — production-conversation ingestion adapters; automated leg-specific eval suites.

## Citations

- Frei, F. X., & Morriss, A. (2020). Begin with trust. *Harvard Business Review*, May-June 2020.
- Edmondson, A. C. (1999). Psychological safety and learning behavior in work teams. *Administrative Science Quarterly*, 44(2), 350-383.
- Goleman, D. (1995). *Emotional Intelligence*. Bantam Books.
- Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *NeurIPS 2020*.
- Sharma, M., et al. (2023). Towards understanding sycophancy in language models. arXiv:2310.13548.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-trust-triangle analyze --trace examples/support_wifi.json --mode forensic
```

If the audit returns `dominant_wobble=empathy`, run `vstack_glaser_conversation` next — the empathy wobble often traces to specific phrasing that triggered cortisol in the user, and Glaser surfaces the word-level fix.
