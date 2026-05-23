# McGregor Orchestrator Mode -- Literature Anchors

Anchored in McGregor's canonical Theory X/Y framework plus agency-theory
contingency models and modern LLM-orchestration research.

## Primary anchors

### 1. McGregor, D. (1960)

> *The Human Side of Enterprise.* McGraw-Hill.

The canonical Theory X / Theory Y statement. Establishes two
contrasting management orientations: Theory X assumes workers need
control; Theory Y assumes workers want to do good work and need
support to do it. For AI agents this is the assumed-trust dial on
the orchestrator.

### 2. McGregor, D. (1966)

> *Leadership and Motivation: Essays of Douglas McGregor.* MIT Press.

The posthumous mature development. Clarifies that the right mode is
**contingent on task properties** -- not a universal preference for
Theory Y. This is the basis for our task-properties-driven optimal-
mode decision rules.

### 3. Schein, E. H. (1990)

> *Organizational Culture and Leadership.* Jossey-Bass.

Adds the cultural-layer dimension. Theory-X or Theory-Y becomes a
cultural assumption that shapes how the organization (or, in our case,
the multi-agent system) operates day to day. The `agentcity.schein_
culture` composition target relates to this layer.

### 4. Pfeffer, J., & Salancik, G. R. (1978)

> *The External Control of Organizations: A Resource Dependence
> Perspective.* Harper & Row.

The task-property contingency framing. Provides the rigorous account
of why optimal control structure depends on the specific risk +
complexity + reversibility properties of the task. For AI agents this
justifies the per-task-class optimal-mode tables in the diagnostic.

### 5. Argyris, C. (1957)

> *Personality and Organization.* Harper.

The pathology of pure Theory-X. Shows that over-supervision produces
learned dependency, surface compliance, and creativity loss. For AI
agents the analogue is the `theory_x_on_proven_agent` and
`creative_task_over_supervised` profile patterns.

### 6. Eisenhardt, K. M. (1989)

> *Agency Theory: An Assessment and Review.* Academy of Management
> Review, 14(1), 57-74.

The principal-agent contingency model. Specifies when monitoring
(Theory X) beats outcome-based contracting (Theory Y) and vice versa.
For AI agents the principal-agent relationship is orchestrator-vs-sub-
agent. Eisenhardt's variables -- monitoring cost, outcome uncertainty,
agent risk aversion -- map cleanly to our task_properties schema.

### 7. Wang, X., et al. (2023) & LangGraph / CrewAI / AutoGen orchestration patterns

> Cooperative LLM Agents survey and modern LLM orchestration
> frameworks.

The modern LLM-specific anchor. Documents the actual orchestrator
patterns used in production: LangGraph state machines, CrewAI role-
based crews, AutoGen group chats, Anthropic Computer Use (sub-agent
authorization). Each has different default Theory X vs Y biases that
the diagnostic surfaces.

## Supporting anchors

### Anthropic Computer Use (2024)

> Anthropic. (2024). *Computer Use.* Anthropic API documentation.

Demonstrates the authorization-scope pattern -- explicit per-action
sub-agent authorization. This is the implementation of the
`add_authorization_scope` intervention and the
`elevate_to_human_on_irreversible` pattern in our intervention catalog.

### Likert, R. (1967) System 4

> *The Human Organization.* McGraw-Hill.

Adjacent framework extending McGregor to a 4-system continuum. For
the AgentCity diagnostic we collapse to Theory X / Y / Hybrid, but
the Likert work is relevant to the `rotate_to_hybrid` intervention.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| McGregor 1960 | Theory X / Y / Hybrid taxonomy. |
| McGregor 1966 | Contingent-optimal-mode framing. |
| Schein 1990 | Composition target `agentcity.schein_culture`. |
| Pfeffer-Salancik 1978 | Task-property -> optimal-mode rules. |
| Argyris 1957 | over-supervision pathologies (proven_agent_overcontrol). |
| Eisenhardt 1989 | Forensic OptimalityJustification structure. |
| Wang 2023 / orchestration | Framework overlays (langgraph / crewai / autogen). |
| Anthropic 2024 | `add_authorization_scope` + `elevate_to_human_on_irreversible`. |
| Likert 1967 | `rotate_to_hybrid` intervention. |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
