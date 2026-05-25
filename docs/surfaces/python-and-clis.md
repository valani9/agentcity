# Python imports + 34 CLIs

The most direct way to use vstack: import the pattern and call it.

```python
from vstack.lewin import LewinAttributionDetector, AgentFailureTrace, FailureStep
from vstack.aar import AnthropicClient

detector = LewinAttributionDetector(AnthropicClient(), mode="standard")
detection = detector.run(
    AgentFailureTrace(
        agent_id="qa-bot",
        model_name="claude-opus-4-7",
        task="Answer 'When was Pluto reclassified?'",
        steps=[
            FailureStep(type="input",       content="When was Pluto reclassified?"),
            FailureStep(type="tool_call",   content="rag.search(query='pluto')"),
            FailureStep(type="observation", content="returned a 2003 Wikipedia revision"),
            FailureStep(type="output",      content="Pluto was reclassified in 2003."),
        ],
        outcome="Confidently wrong year (correct: 2006).",
        success=False,
        initial_attribution="model is bad at facts",
    )
)
print(detection.to_markdown())
```

Every pattern follows the same interface — see [The 5-layer pattern shape](../concepts/pattern-shape.md).

## 34 per-pattern CLIs

Every pattern also ships a CLI registered in `[project.scripts]`. The full list:

| CLI | Pattern |
|---|---|
| `vstack` | `vstack.aar` (foundational AAR) |
| `vstack-lewin` | `#01 Lewin attribution` |
| `vstack-goleman` | `#02 Goleman EI` |
| `vstack-johari` | `#03 Johari window` |
| `vstack-danva` | `#04 DANVA emotion reader` |
| `vstack-reappraisal` | `#05 Cognitive reappraisal` |
| `vstack-yerkes` | `#06 Yerkes-Dodson` |
| `vstack-hexaco` | `#07 HEXACO personality` |
| `vstack-grant` | `#08 Grant strengths` |
| `vstack-motivation` | `#09 Motivation traps` |
| `vstack-sdt` | `#10 SDT` |
| `vstack-mcgregor` | `#11 McGregor` |
| `vstack-vroom` | `#12 Vroom` |
| `vstack-grpi` | `#13 GRPI` |
| `vstack-process` | `#14 Process gain/loss` |
| `vstack-loafing` | `#15 Social loafing` |
| `vstack-superflocks` | `#16 Superflocks` |
| `vstack-lencioni` | `#17 Lencioni` |
| `vstack-trust-triangle` | `#18 Trust Triangle` |
| `vstack-mcallister` | `#19 McAllister trust` |
| `vstack-psych-safety` | `#20 Edmondson` |
| `vstack-glaser` | `#21 Glaser` |
| `vstack-feedback-triggers` | `#22 Stone-Heen` |
| `vstack-plus-delta` | `#23 Plus/Delta` |
| `vstack-smart-goal` | `#24 SMART goal` |
| `vstack-group-decision` | `#25 Group decision` |
| `vstack-debate-pathology` | `#26 Debate pathology` |
| `vstack-bias-stack` | `#27 Bias stack` |
| `vstack-devils-advocate` | `#28 Devil's advocate` |
| `vstack-thomas-kilmann` | `#29 Thomas-Kilmann` |
| `vstack-schein-culture` | `#31 Schein` |
| `vstack-robbins-culture` | `#32 Robbins-Judge` |
| `vstack-org-structure` | `#33 Org-structure` |
| `vstack-span-of-control` | `#34 Span-of-control` |

Each CLI has the same 7 subcommands: `analyze`, `batch`, `replay`, `validate`, `schema`, `playbooks`, `compose`.

```bash
vstack-lewin analyze --trace failure.json --mode forensic
vstack-lewin playbooks   # browse the failure-mode playbooks
vstack-lewin compose     # show the cross-pattern composition manifest
vstack-lewin schema --target trace   # print the trace JSON schema
```
