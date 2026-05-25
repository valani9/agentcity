# GRPI Working Agreement — the pre-flight checklist for multi-agent crews

*#13 vstack_grpi* · *Module 2 — Multi-agent team (generative)*

> A four-agent marketing crew (researcher, strategist, critic, executor) was launched on a 14-day Q3 campaign. By day three, two of the agents were independently building competing campaign concepts; the critic had filed three rounds of dissent that nobody had explicitly accepted or rejected; the executor was waiting for "the decision" that no agent had been empowered to make. The team finally shipped on day fifteen with a watered-down hybrid that nobody had argued for. Postmortem said "communication breakdown." The actual diagnosis was simpler: the crew launched without a contract. Two of the four GRPI letters — Roles and Processes — had never been written down. Every downstream failure traced back to that omission.

## What the pattern catches

Most multi-agent failures are not capability failures. They are **setup failures** — the crew was deployed without a working agreement, and the missing letter of GRPI (Goals / Roles / Processes / Interactions) determined which failure mode showed up. Crews missing G optimize local metrics over the user's goal. Crews missing R produce planner-equals-evaluator pathology and duplicate work. Crews missing P loop indefinitely because no decision protocol exists. Crews missing I devolve into either silent agreement or unstructured conflict the first time stress hits.

vstack_grpi is the only **generative** pattern in this neighborhood — it doesn't diagnose existing failures, it produces the contract that prevents them. The analyzer answers: *what does a complete working agreement for this team, on this task, with these constraints, look like?*

## Why the OB literature is the right reference

The diagnostic is anchored in Beckhard 1972 (the canonical statement), Rubin, Plovnick & Fry 1977 (the first formal operationalization with assessment instruments), Hackman 2002 (the team-effectiveness anchor), Salas et al. 2018 (the modern review), Lencioni 2002 (the inverse perspective — what poor GRPI enables), and Edmondson 1999 (the interactions-dimension anchor).

**Beckhard's 1972 insight** was that team failures follow a *predictable cascade*: ambiguous Goals cascade to ambiguous Roles, which cascade to broken Processes, which cascade to dysfunctional Interactions. The four dimensions are ordered. Beckhard's contention — that every team failure he consulted on traced back to a missing letter, not lack of skill or effort — held up through fifty years of replication. Tannenbaum & Salas's 2020 *Teams that Work* opens with the GRPI model; McKinsey teaches it; the U.S. Army's TC 25-20 cites it.

The transfer to AI agents is direct because agent crews are bona fide multi-agent systems with the same four needs: a shared goal, owned roles, decision processes, and interaction norms. LangGraph, CrewAI, and Microsoft Agent Framework all skip the contract step by default — agents start without an agreement and the cascade plays out exactly as Beckhard predicted.

## How the analyzer works

Input is `TeamSetupRequest` — `team_id`, `task`, agent roster (`AgentRole` entries with name + description), `constraints`, `success_criteria`. The pipeline:

- **quick** — one LLM call. All four GRPI sections at minimum-viable detail.
- **standard** — two LLM calls. Section content + a `DysfunctionPreventionAudit` against Lencioni's five dysfunctions.
- **forensic** — four LLM calls. Adds per-section interaction rules, RACI assignments, escalation/abandonment criteria, and `ComposedPatternHandoff` recommendations.

```python
from vstack.grpi import GRPIWorkingAgreementAnalyzer, TeamSetupRequest, AgentRole
agreement = GRPIWorkingAgreementAnalyzer(llm, mode="forensic").run(
    TeamSetupRequest(
        team_id="marketing-q3",
        task="Design and launch a Q3 SaaS campaign in 14 days.",
        agents=[
            AgentRole(name="researcher", description="Market and competitor research"),
            AgentRole(name="strategist", description="Campaign strategy"),
            AgentRole(name="critic", description="Devil's-advocate review"),
            AgentRole(name="executor", description="Asset production"),
        ],
        constraints=["Budget $20K", "1 mandatory dissent round per decision"],
        success_criteria=["≥3 concepts proposed", "Launch by day 14"],
    )
)
print(agreement.to_markdown())                # human-readable contract
print(agreement.to_orchestrator_preamble())   # condensed prompt-prepend block
```

## What the playbooks say to do

The generated artifact is the intervention. Each section maps to literature:

- **Goals** → measurable success criteria, scope boundaries, deliverables, and explicit *kill criteria* (Hackman 2002's "compelling direction").
- **Roles** → per-agent responsibilities + decision rights + accountability owner per work-stream. RACI summary. Prevents the planner-equals-evaluator pathology (Pattern #28).
- **Processes** → decision protocol (concurring / majority / consensus / orchestrator-decides), escalation path, abandonment criteria, communication cadence. Locks the failure mode that Pattern #14 (process loss) measures.
- **Interactions** → disagreement norms, feedback format, voice/turn-taking rules, explicit psychological-safety commitments. Anchors the interactions dimension to Edmondson 1999.

## How it composes with adjacent patterns

GRPI is the **pre-flight setup pattern** in chain D1 (calibration layer). Run it once at team formation; reference the resulting artifact in the orchestrator's system prompt at runtime. Then, when the crew fails despite the agreement, the diagnostic chain T1 picks up:

- `vstack_lencioni` runs first to identify the lowest unhealthy dysfunction.
- `vstack_trust_triangle` or `vstack_mcallister_trust` deepens trust-layer findings.
- `vstack_process_gain_loss` checks whether the team beat the best single agent.
- `vstack_social_loafing` checks whether roles are being done.

If Lencioni's finding is **lack of commitment**, the diagnostic almost always reads back to a missing or vague P (Process) dimension in the GRPI agreement — the contract needed a decision protocol that was never written. Pattern #13 closes that gap on the next setup.

Cross-link to [composition runbook chain D1](../COMPOSITION-RUNBOOK.md#chain-d1--pre-flight-setup-calibration-layer).

## Comparison to adjacent tools

- **CrewAI's `Crew` config / LangGraph state graphs** specify *what* the team does. GRPI specifies *how the team works together* — the meta-level contract.
- **System prompts** capture individual-agent behavior; they cannot express team-level interaction norms ("the critic must raise ≥2 alternatives before consensus is locked").
- **Pattern #28 (Devil's Advocate Separator)** is one specific R within GRPI. GRPI is the full contract; #28 is one role inside it.
- **Diagnostic patterns (Lencioni, Trust Triangle, AAR)** run *after* failure. GRPI prevents the failures they diagnose.

## Paper outline

1. **Background** — Beckhard 1972, Rubin/Plovnick/Fry 1977, Hackman 2002, Salas 2018, Lencioni 2002, Edmondson 1999.
2. **Translation** — agent crews as bona fide teams; the working-agreement-as-prompt-preamble pattern.
3. **Method** — generation pipeline, dysfunction-prevention audit, three modes (quick / standard / forensic).
4. **Evaluation** — paired study: same team, same task, with GRPI vs without; measure Lencioni dysfunction surfaces, process-gain/loss, social-loafing rates downstream.
5. **Limitations** — single-agent setups don't need a team contract; the generator rejects them.
6. **Related work** — agile working-agreements literature; CrewAI / LangGraph team configs.
7. **Future work** — auto-amendment of the agreement when AAR surfaces a missing letter.

## Citations

- Beckhard, R. (1972). Optimizing team-building effort. *Journal of Contemporary Business*, 1, 23-32.
- Rubin, I. M., Plovnick, M. S., & Fry, R. E. (1977). *Task-Oriented Team Development*. McGraw-Hill.
- Hackman, J. R. (2002). *Leading Teams: Setting the Stage for Great Performances*. HBS Press.
- Salas, E., et al. (2018). The science of team performance: Progress and the need for greater integration. *Annual Review of Org Psych*, 5, 593-620.
- Lencioni, P. (2002). *The Five Dysfunctions of a Team*. Jossey-Bass.
- Edmondson, A. C. (1999). Psychological safety and learning behavior in work teams. *Administrative Science Quarterly*, 44(2), 350-383.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-grpi generate --request examples/marketing_crew.json --mode forensic
```

Generate the agreement once at team formation, prepend it to the orchestrator's system prompt, and reference it whenever the crew falters. If failures still surface, run `vstack_lencioni` next to identify which letter of GRPI the contract under-specified.
