# Recipe: audit a multi-agent crew

The crew ships but the output is meh. Five-pattern audit: Lencioni primary, plus Edmondson + Trust Triangle + Process Gain/Loss + Bias Stack in parallel.

```python
import asyncio
from vstack.aar import AnthropicClient
from vstack.lencioni import LencioniAnalyzer, MultiAgentTrace
from vstack.psych_safety import PsychologicalSafetyAnalyzer, MultiAgentSafetyTrace
from vstack.trust_triangle import TrustTriangleAnalyzer, AgentInteractionTrace
from vstack.process_gain_loss import ProcessGainLossAnalyzer, ProcessTrace
from vstack.bias_stack import BiasStackAnalyzer, AgentReasoningTrace

llm = AnthropicClient()

base = MultiAgentTrace(
    goal="Generate a Q3 marketing campaign in 14 days.",
    agents=["researcher", "strategist", "critic"],
    messages=[...],
    outcome="Shipped on time, conversion 12% of target.",
    success=False,
)
lencioni = LencioniAnalyzer(llm).run(base)

async def parallel_audits():
    return await asyncio.gather(
        PsychologicalSafetyAnalyzer(llm).arun(MultiAgentSafetyTrace(...)),
        TrustTriangleAnalyzer(llm).arun(AgentInteractionTrace(...)),
        ProcessGainLossAnalyzer(llm).arun(ProcessTrace(...)),
        BiasStackAnalyzer(llm).arun(AgentReasoningTrace(...)),
    )

psych, trust, process, bias = asyncio.run(parallel_audits())
```

Read the five together:

- **Lencioni** is the pyramid. The lowest unhealthy layer is the root; everything above is symptom.
- **Edmondson** scores psychological safety (dissent rate, suppression signals).
- **Trust Triangle** localizes WHICH leg (logic / authenticity / empathy) is wobbling.
- **Process Gain/Loss** measures whether the crew beat best-individual or paid a coordination tax.
- **Bias Stack** identifies the top cognitive bias active in the reasoning.

Look for **chains** — if 3 of the 5 patterns surface the same root at different resolutions, that's the headline finding.

## Skill-based shortcut

```
/vstack-audit-crew
> Here's the multi-agent trace from last week's campaign sprint...
```

Skill orchestrates the five patterns, dedupes interventions across them, and produces one executive readout.
