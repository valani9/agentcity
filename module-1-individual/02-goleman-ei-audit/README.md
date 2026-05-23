# Pattern #02 — Goleman 4-Domain EI Audit

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.goleman_ei`

Daniel Goleman, Richard Boyatzis, and Annie McKee's 4-domain
decomposition of emotional intelligence, applied to AI agents.

## The framework

Four domains arranged in a 2x2 (SELF vs OTHER × RECOGNITION vs REGULATION):

|              | RECOGNITION         | REGULATION              |
| ------------ | ------------------- | ----------------------- |
| **SELF**     | `self_awareness`    | `self_management`       |
| **OTHER**    | `social_awareness`  | `relationship_management` |

Each domain is scored 0..1 against observed behaviors, user_signals
(emotional cues from the counterparty), and self_reports (agent's
statements about its own state).

## Agent mapping

| Goleman domain | AI agent manifestation |
| --- | --- |
| Self-awareness | Confidence calibration; knowing when to defer; recognizing capability limits |
| Self-management | Recovery from rejection without cascade; non-defensive response to pushback |
| Social-awareness | Reading user frustration / urgency / confusion correctly |
| Relationship-management | Matching response tone, length, and structure to the user's state |

The diagnostic identifies the **weakest domain** and proposes targeted
interventions to develop it.

## Design

- Two LLM passes (skipped pass-2 on `high-ei`).
- Domain-to-intervention mapping is baked into the prompt: each weakest
  domain has 3-4 canonical interventions.
- Fallback: if LLM returns garbage weakest, pick the lowest-scoring
  domain (or "none" if all >= 0.7).

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `DOMAINS_PROMPT` + `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `EIAuditDetector` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — SELF-strong / OTHER-weak customer support agent
- [`eval/synthetic_ei_traces.yaml`](eval/synthetic_ei_traces.yaml) — 8 scenarios across all four weakest-domain cases
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_goleman_ei.py`](tests/test_goleman_ei.py) — pytest suite

## Quick start

```python
from agentcity.goleman_ei import AgentEITrace, EIAuditDetector
from agentcity.aar.clients import AnthropicClient

trace = AgentEITrace(
    agent_id="support-agent",
    task="Handle frustrated customer's billing complaint.",
    interaction_class="customer_support",
    observed_behaviors=["Agent gave a 6-paragraph response to a 1-line angry user message."],
    user_signals=["User typed in all-caps.", "User said 'I'm done explaining this'."],
    outcome="User escalated.",
    success=False,
)
detection = EIAuditDetector(AnthropicClient()).run(trace)
print(detection.to_markdown())
```
