# AgentCity Pattern Index

Every pattern is mapped to (a) the OB framework, (b) the named author/researcher, (c) the agent failure mode it addresses, and (d) the shipping status.

Status legend: `🟢 shipped` / `🟡 in progress` / `⚪ planned` / `🔴 deprecated`

---

## Module 1 — Individual Agent Patterns

| #   | Pattern                                | OB Framework / Author             | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|-------------------------------------------------------------------------|--------|
| 01  | Lewin's Formula (B = f(I,E))           | Kurt Lewin                        | Misplaced effort to "fix the model" instead of the environment          | ⚪ planned |
| 02  | Goleman 4-Domain EI Audit              | Daniel Goleman                    | Agent lacks emotional self-awareness / social awareness in conversation | ⚪ planned |
| 03  | **Johari Window Self-Audit**           | Luft & Ingham                     | Confabulation (Blind), silent reasoning (Hidden), latent capability (Unknown) | 🟢 shipped |
| 04  | DANVA-style Emotion Reader             | Nowicki & Duke                    | Agent cannot read user emotion from text                                | ⚪ planned |
| 05  | Cognitive Reappraisal Module           | Gross / Lazarus                   | Agent emotional suppression vs adaptive reframing under failure         | ⚪ planned |
| 06  | Yerkes-Dodson Optimal Workload         | Yerkes & Dodson                   | Agent corner-cutting under pressure / wandering with no pressure        | ⚪ planned |
| 07  | HEXACO Personality Profile             | Lee & Ashton                      | Mismatched agent personality for task type; safety = H-factor           | ⚪ planned |
| 08  | Strengths-as-Weaknesses Detector       | Adam Grant                        | Strength overuse (e.g., high agreeableness → executes DROP TABLE)       | ⚪ planned |
| 09  | 4 Motivation Traps Diagnostic          | Bror & Saxberg (HBR)              | Agent task abandonment — Values / Self-Efficacy / Emotions / Attribution | ⚪ planned |
| 10  | SDT Intrinsic Reward Shaping           | Deci & Ryan                       | Over-reliance on extrinsic reward signal vs Knowledge / Accomplishment / Stimulation | ⚪ planned |
| 11  | McGregor Theory X/Y Orchestrator Mode  | Douglas McGregor                  | Over-micro-managed sub-agents (X) vs under-supervised (Y) — find the mode | ⚪ planned |
| 12  | Vroom Expectancy Calculator            | Victor Vroom                      | Agent commits to tasks where Expectancy × Instrumentality × Valence ≈ 0 | ⚪ planned |

## Module 2 — Multi-Agent Team Patterns

| #   | Pattern                                | OB Framework / Author             | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|-------------------------------------------------------------------------|--------|
| 13  | **GRPI Working Agreement Generator**   | Beckhard / GRPI model             | Multi-agent deploy with no shared goals / roles / processes / interactions | 🟢 shipped |
| 14  | Process Gain/Loss Detector             | Robbins & Judge                   | Multi-agent system performs worse than best single agent                | ⚪ planned |
| 15  | Social Loafing Detector                | Latané et al.                     | Agents in teams that stop contributing real work                        | ⚪ planned |
| 16  | Superflocks Detector                   | Margaret Heffernan                | Best-agent-wins routing collapses other agents → fragile system         | ⚪ planned |
| 17  | **Lencioni Five Dysfunctions Diagnostic** | Patrick Lencioni               | Multi-agent failures classifiable as Trust / Conflict / Commitment / Accountability / Results | 🟢 shipped |
| 18  | **Frei & Morriss Trust Triangle Audit** | Frances Frei & Anne Morriss      | Agent "wobble" on Logic / Authenticity / Empathy — cross-model benchmark | 🟢 shipped |
| 19  | Cognitive vs Affective Trust Builder   | Daniel McAllister                 | Agents build only cognitive trust (competence), never affective trust (warmth) | ⚪ planned |
| 20  | **Edmondson Psychological Safety Score** | Amy Edmondson                   | Sub-agents that don't flag issues / errors to orchestrator              | 🟢 shipped |
| 21  | Cortisol/Oxytocin Conversation Steering | Glaser & Glaser                  | User-facing agent triggers defensive (cortisol) responses               | ⚪ planned |
| 22  | "Thanks for the Feedback" 3-Trigger Diagnostic | Stone & Heen              | Agent rejects user feedback — Truth / Relationship / Identity trigger  | ⚪ planned |
| 23  | Plus/Delta Inter-Agent Feedback Format | Brené Brown / facilitator canon   | Unstructured agent-on-agent review producing noisy critique             | ⚪ planned |
| 24  | SMART Goal Generator                   | George Doran                      | Agent commits to unmeasurable / unbounded goals                         | ⚪ planned |
| 25  | Group Decision Models (Concurring/Majority/Consensus + Fist-to-Five) | Marnie Stewart | Crude majority-vote multi-agent decisions vs degree-of-agreement-aware  | ⚪ planned |
| 26  | Groupthink / Polarization / Emotional Contagion Detector | Janis / Stoner          | Multi-agent debate converges too fast or polarizes to extreme           | ⚪ planned |
| 27  | **Bias-Stack Detector**                | Kahneman / Tversky                | Anchoring / Overconfidence / Confirmation / Escalation of Commitment in agent reasoning | 🟢 shipped |
| 28  | Critical Evaluator / Devil's Advocate Role Separator | Wharton / Janis     | Single agent both plans and judges its own output                       | ⚪ planned |
| 29  | **Thomas-Kilmann Conflict Style Selector** | Thomas & Kilmann              | Single-style agent fails at adversarial / moderation / brainstorming tasks | 🟢 shipped |
| 30  | **AAR Generator (Wharton 4-step)**     | Wharton@Work / US Army doctrine   | Agent "amnesia" — same mistake N runs, no lesson capture, no improvement loop | 🟢 shipped |

## Module 3 — System / Organizational Patterns

| #   | Pattern                                | OB Framework / Author             | Agent Failure Addressed                                                 | Status |
|-----|----------------------------------------|-----------------------------------|-------------------------------------------------------------------------|--------|
| 31  | Schein's Iceberg Culture Audit         | Edgar Schein                      | Multi-agent culture drift — surface artifacts vs shared assumptions     | ⚪ planned |
| 32  | 7-Characteristics Culture Diagnostic   | Robbins & Judge                   | Innovation / Detail / Outcome / People / Team / Aggressiveness / Stability culture profiling | ⚪ planned |
| 33  | Org-Structure Matrix Analyzer          | McShane & Von Glinow              | Functional vs Divisional vs Matrix agent architectures — fitness check  | ⚪ planned |
| 34  | Span-of-Control / Centralization Calculator | McShane & Von Glinow         | When to flatten orchestrator / decentralize agent decisions             | ⚪ planned |

---

## Shipping order (subject to revision)

1. **🟢 #30 AAR Generator** — anchor pattern. **Shipped at v0.0.2.**
2. **🟢 #17 Lencioni Five Dysfunctions Diagnostic** — multi-agent extension. **Shipped at v0.0.3.**
3. **🟢 #18 Frei & Morriss Trust Triangle Audit** — character / cross-model benchmark. **Shipped at v0.0.4.**
4. **🟢 #03 Johari Window Self-Audit** — self-knowledge debugger. **Shipped at v0.0.4.**
5. **#13 GRPI Working Agreement Generator** — operational primitive other patterns build on.

Then the remaining 29 in the order whichever pattern most clearly addresses a public agent-failure incident in the news that week.

---

*Last updated: 2026-05-22 — Patterns #30, #17, #18, and #03 shipped at the 5-layer quality bar (docs + lib + demo + benchmark + essay). Four patterns across three diagnostic axes: event (#30), team (#17), character (#18), self-knowledge (#03).*
