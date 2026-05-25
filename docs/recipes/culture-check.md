# Recipe: run a culture check

Behavior doesn't match intent. Chain: **Schein iceberg → Robbins-Judge 7-characteristic → (optional) McGregor**.

```python
from vstack.aar import AnthropicClient
from vstack.schein_culture import CultureAuditAnalyzer, AgentCultureTrace
from vstack.robbins_culture import CultureProfileAnalyzer

llm = AnthropicClient()

base = AgentCultureTrace(
    crew_id="campaign-team",
    task="Generate marketing campaigns",
    observations=[
        # Each observation has a category: artifact / espoused_value / behavior
        {"category": "espoused_value", "content": "We value bold, distinctive voice."},
        {"category": "behavior", "content": "Every output reverts to corporate-safe tone."},
        {"category": "artifact", "content": "Style guide says 'always provocative'."},
        # ...
    ],
    outcome="Crew ships but tone defaults to corporate-safe.",
    success=False,
)

schein = CultureAuditAnalyzer(llm, mode="forensic").run(base)
robbins = CultureProfileAnalyzer(llm, mode="standard").run(base)

print(schein.dominant_layer, schein.alignment_drift_audit)
print(robbins.profile_type, robbins.seven_axis_scores)
```

If Schein surfaces an orchestrator-trust gap (assumptions like "agents need to be told what to do"), add McGregor:

```python
from vstack.mcgregor import McGregorOrchestratorAnalyzer, OrchestratorTrace
mcgregor = McGregorOrchestratorAnalyzer(llm).run(OrchestratorTrace(...))
```

## Reading the layered result

- **Schein** names the gap layer-by-layer: which espoused value the behavior is contradicting, and which underlying assumption is doing the contradicting.
- **Robbins-Judge** gives the *type* label (innovative / outcome-obsessed / stable-bureaucratic / etc.) so the user can compare to the type they wanted to build.
- **McGregor** places the orchestrator on the Theory X (controlling) ↔ Theory Y (autonomy-granting) axis.

## Skill-based shortcut

```
/vstack-culture-check
> Our agent crew keeps reverting to corporate-safe tone despite spec saying provocative ...
```
