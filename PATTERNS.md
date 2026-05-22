# AgentCity Pattern Index

Every pattern is mapped to (a) the OB framework, (b) the named author/researcher, (c) the agent failure mode it addresses, (d) the MO221 class it derives from, and (e) the shipping status.

Status legend: `🟢 shipped` / `🟡 in progress` / `⚪ planned` / `🔴 deprecated`

---

## Module 1 — Individual Agent Patterns

| #   | Pattern                                | OB Framework / Author             | Class   | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|---------|-------------------------------------------------------------------------|--------|
| 01  | Lewin's Formula (B = f(I,E))           | Kurt Lewin                        | 1       | Misplaced effort to "fix the model" instead of the environment          | ⚪ planned |
| 02  | Goleman 4-Domain EI Audit              | Daniel Goleman                    | 2       | Agent lacks emotional self-awareness / social awareness in conversation | ⚪ planned |
| 03  | Johari Window Self-Audit               | Luft & Ingham                     | 2       | Confabulation (Blind), silent reasoning (Hidden), latent capability (Unknown) | ⚪ planned |
| 04  | DANVA-style Emotion Reader             | Nowicki & Duke                    | 2       | Agent cannot read user emotion from text                                | ⚪ planned |
| 05  | Cognitive Reappraisal Module           | Gross / Lazarus                   | 2       | Agent emotional suppression vs adaptive reframing under failure         | ⚪ planned |
| 06  | Yerkes-Dodson Optimal Workload         | Yerkes & Dodson                   | 3       | Agent corner-cutting under pressure / wandering with no pressure        | ⚪ planned |
| 07  | HEXACO Personality Profile             | Lee & Ashton                      | 3       | Mismatched agent personality for task type; safety = H-factor           | ⚪ planned |
| 08  | Strengths-as-Weaknesses Detector       | Adam Grant                        | 4       | Strength overuse (e.g., high agreeableness → executes DROP TABLE)       | ⚪ planned |
| 09  | 4 Motivation Traps Diagnostic          | Bror & Saxberg (HBR)              | 6       | Agent task abandonment — Values / Self-Efficacy / Emotions / Attribution | ⚪ planned |
| 10  | SDT Intrinsic Reward Shaping           | Deci & Ryan                       | 6       | Over-reliance on extrinsic reward signal vs Knowledge / Accomplishment / Stimulation | ⚪ planned |
| 11  | McGregor Theory X/Y Orchestrator Mode  | Douglas McGregor                  | 6       | Over-micro-managed sub-agents (X) vs under-supervised (Y) — find the mode | ⚪ planned |
| 12  | Vroom Expectancy Calculator            | Victor Vroom                      | 7       | Agent commits to tasks where Expectancy × Instrumentality × Valence ≈ 0 | ⚪ planned |

## Module 2 — Multi-Agent Team Patterns

| #   | Pattern                                | OB Framework / Author             | Class   | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|---------|-------------------------------------------------------------------------|--------|
| 13  | GRPI Working Agreement Generator       | Beckhard / GRPI model             | 4-5     | Multi-agent deploy with no shared goals / roles / processes / interactions | ⚪ planned |
| 14  | Process Gain/Loss Detector             | Robbins & Judge                   | 11      | Multi-agent system performs worse than best single agent                | ⚪ planned |
| 15  | Social Loafing Detector                | Latané et al.                     | 11      | Agents in teams that stop contributing real work                        | ⚪ planned |
| 16  | Superflocks Detector                   | Margaret Heffernan                | 11/12   | Best-agent-wins routing collapses other agents → fragile system         | ⚪ planned |
| 17  | Lencioni Five Dysfunctions Diagnostic  | Patrick Lencioni                  | 11      | Multi-agent failures classifiable as Trust / Conflict / Commitment / Accountability / Results | ⚪ planned |
| 18  | Frei & Morriss Trust Triangle Audit    | Frances Frei & Anne Morriss       | 11/12   | Agent "wobble" on Logic / Authenticity / Empathy — cross-model benchmark | ⚪ planned |
| 19  | Cognitive vs Affective Trust Builder   | Daniel McAllister                 | 11/12   | Agents build only cognitive trust (competence), never affective trust (warmth) | ⚪ planned |
| 20  | Edmondson Psychological Safety Score   | Amy Edmondson                     | 12      | Sub-agents that don't flag issues / errors to orchestrator              | ⚪ planned |
| 21  | Cortisol/Oxytocin Conversation Steering | Glaser & Glaser                  | 13      | User-facing agent triggers defensive (cortisol) responses               | ⚪ planned |
| 22  | "Thanks for the Feedback" 3-Trigger Diagnostic | Stone & Heen              | 13      | Agent rejects user feedback — Truth / Relationship / Identity trigger  | ⚪ planned |
| 23  | Plus/Delta Inter-Agent Feedback Format | Brené Brown / facilitator canon   | 13-14   | Unstructured agent-on-agent review producing noisy critique             | ⚪ planned |
| 24  | SMART Goal Generator                   | George Doran                      | 14      | Agent commits to unmeasurable / unbounded goals                         | ⚪ planned |
| 25  | Group Decision Models (Concurring/Majority/Consensus + Fist-to-Five) | Marnie Stewart | 15 | Crude majority-vote multi-agent decisions vs degree-of-agreement-aware  | ⚪ planned |
| 26  | Groupthink / Polarization / Emotional Contagion Detector | Janis / Stoner          | 15      | Multi-agent debate converges too fast or polarizes to extreme           | ⚪ planned |
| 27  | Bias-Stack Detector                    | Kahneman / Tversky                | 15      | Anchoring / Overconfidence / Confirmation / Escalation of Commitment in agent reasoning | ⚪ planned |
| 28  | Critical Evaluator / Devil's Advocate Role Separator | Wharton / Janis     | 15, 22  | Single agent both plans and judges its own output                       | ⚪ planned |
| 29  | Thomas-Kilmann Conflict Style Selector | Thomas & Kilmann                  | 17      | Single-style agent fails at adversarial / moderation / brainstorming tasks | ⚪ planned |
| 30  | **AAR Generator (Wharton 4-step)**     | Wharton@Work / US Army doctrine   | 22      | Agent "amnesia" — same mistake N runs, no lesson capture, no improvement loop | 🟡 in progress |

## Module 3 — System / Organizational Patterns

| #   | Pattern                                | OB Framework / Author             | Class   | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|---------|-------------------------------------------------------------------------|--------|
| 31  | Schein's Iceberg Culture Audit         | Edgar Schein                      | 18      | Multi-agent culture drift — surface artifacts vs shared assumptions     | ⚪ planned |
| 32  | 7-Characteristics Culture Diagnostic   | Robbins & Judge                   | 18      | Innovation / Detail / Outcome / People / Team / Aggressiveness / Stability culture profiling | ⚪ planned |
| 33  | Org-Structure Matrix Analyzer          | McShane & Von Glinow              | 19      | Functional vs Divisional vs Matrix agent architectures — fitness check  | ⚪ planned |
| 34  | Span-of-Control / Centralization Calculator | McShane & Von Glinow         | 19      | When to flatten orchestrator / decentralize agent decisions             | ⚪ planned |

---

## Shipping order (subject to revision)

1. **🟡 #30 AAR Generator** — anchor pattern. The credibility primer. Defines AgentCity's OB-language brand voice. Ships first.
2. **#17 Lencioni Five Dysfunctions Diagnostic** — multi-agent extension. Most enterprise-recognizable vocabulary.
3. **#18 Frei & Morriss Trust Triangle Audit** — first paper-shaped artifact. Cross-model benchmark.
4. **#03 Johari Window Self-Audit** — most novel individual-pattern, MCP-shaped.
5. **#13 GRPI Working Agreement Generator** — operational primitive other patterns build on.

Then the remaining 25 in the order whichever pattern most clearly addresses a public agent-failure incident in the news that week.

---

*Last updated: 2026-05-22 — initial scaffold. AAR Generator in active development.*
