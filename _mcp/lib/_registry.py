"""Registry of all 34 vstack patterns for MCP exposure.

Every entry describes one pattern in enough detail that the MCP server
can synthesize a Tool, a Resource set (citations + playbooks +
composition), and a Prompt template without any pattern-specific code.

The registry is hand-curated rather than auto-discovered: the cost of
listing 34 four-tuples once is small compared to the cost of a
silent registration drift the next time a pattern's class is renamed.

When a new pattern is added to vstack, add a tuple here, run
``pytest _mcp/tests/test_registry.py``, and the MCP layer will pick
up the new tool, resource, and prompt without further changes.
"""

from __future__ import annotations

import importlib
import typing
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel


@dataclass(frozen=True)
class PatternEntry:
    """One pattern registered with the MCP server.

    Fields are all resolved lazily through the import_name to keep the
    registry module import cheap. The resolved attributes (analyzer
    class, input class, output class, mode literal, composition object,
    playbooks dict) are looked up on demand via :meth:`load`.
    """

    name: str
    """Snake-case import name, e.g. ``"lewin"``. Matches the
    ``vstack.<name>`` import path and the wheel directory under
    ``vstack/``."""

    friendly: str
    """Human-readable label, e.g. ``"Lewin Attribution"``. Used in
    MCP tool descriptions and prompt labels."""

    group: str
    """Module grouping label, e.g. ``"Module 1 / Individual"``. Used
    to organize the tool list in the meta prompt."""

    analyzer_cls: str
    """Class name of the synchronous analyzer entry point inside
    ``vstack.<name>``. Always has the uniform constructor
    ``(llm_client, model, *, mode, ...)`` and a ``.run(trace) -> detection``
    method."""

    input_cls: str
    """Class name of the Pydantic input trace model inside
    ``vstack.<name>``."""

    output_cls: str
    """Class name of the Pydantic output detection model inside
    ``vstack.<name>``."""

    mode_alias: str
    """Name of the ``Literal[...]`` mode alias inside ``vstack.<name>``,
    e.g. ``"LewinMode"``. Used to enumerate valid mode values for the
    JSON schema enum."""

    composition_attr: str
    """Name of the module-level composition manifest, e.g.
    ``"LEWIN_COMPOSITION"``. Loaded as an MCP resource so an LLM can
    inspect cross-pattern handoff recommendations without invoking
    a tool."""

    summary: str
    """One-sentence summary of what the diagnostic does. Used in the
    MCP tool description so an LLM can pick the right pattern from
    the tool list."""

    citations_present: bool = True
    """Whether ``CITATIONS.md`` is shipped alongside the pattern's
    module. AAR is the only exception; its citations live in the
    repo root CITATIONS.md instead of the per-pattern file."""

    def load(self) -> "ResolvedPattern":
        """Import the pattern module and resolve every class/attr."""
        mod = importlib.import_module(f"vstack.{self.name}")
        analyzer = getattr(mod, self.analyzer_cls)
        input_cls = getattr(mod, self.input_cls)
        output_cls = getattr(mod, self.output_cls)
        mode_lit = getattr(mod, self.mode_alias)
        mode_values = tuple(typing.get_args(mode_lit))
        composition = getattr(mod, self.composition_attr, None)
        playbooks = getattr(mod, "PLAYBOOKS", {})
        return ResolvedPattern(
            entry=self,
            module=mod,
            analyzer_cls=analyzer,
            input_cls=input_cls,
            output_cls=output_cls,
            mode_values=mode_values,
            composition=composition,
            playbooks=playbooks,
        )


@dataclass(frozen=True)
class ResolvedPattern:
    """A registry entry plus the imported references for runtime use."""

    entry: PatternEntry
    module: Any
    analyzer_cls: type
    input_cls: type[BaseModel]
    output_cls: type[BaseModel]
    mode_values: tuple[str, ...]
    composition: Any
    playbooks: Mapping[Any, Any]


# Order matches the canonical pattern numbering (01..34). The MCP
# server walks the registry in this order, so the tool list, resource
# list, and prompt list always come out in the same predictable order
# across clients.
PATTERNS: tuple[PatternEntry, ...] = (
    PatternEntry(
        name="lewin",
        friendly="Lewin Attribution",
        group="Module 1 / Individual",
        analyzer_cls="LewinAttributionDetector",
        input_cls="AgentFailureTrace",
        output_cls="LewinDetection",
        mode_alias="LewinMode",
        composition_attr="LEWIN_COMPOSITION",
        summary=(
            "Kurt Lewin's B = f(P, E) attribution framework: when an "
            "agent fails, is the cause INTERNAL (model/training), "
            "ENVIRONMENTAL (prompt/tools/scaffolding), or INTERACTIONAL?"
        ),
    ),
    PatternEntry(
        name="goleman_ei",
        friendly="Goleman EI Audit",
        group="Module 1 / Individual",
        analyzer_cls="EIAuditDetector",
        input_cls="AgentEITrace",
        output_cls="EIDetection",
        mode_alias="EIMode",
        composition_attr="GOLEMAN_COMPOSITION",
        summary=(
            "Daniel Goleman's emotional-intelligence quadrants "
            "(self-awareness / self-management / social awareness / "
            "relationship management) applied to agent dialogue."
        ),
    ),
    PatternEntry(
        name="johari",
        friendly="Johari Window",
        group="Module 1 / Individual",
        analyzer_cls="JohariSelfAuditor",
        input_cls="AgentSelfReportTrace",
        output_cls="JohariSelfAudit",
        mode_alias="JohariMode",
        composition_attr="JOHARI_COMPOSITION",
        summary=(
            "Luft & Ingham's Johari Window for agent self-awareness: "
            "classify trace content into OPEN / BLIND / HIDDEN / "
            "UNKNOWN quadrants and propose interventions to grow OPEN."
        ),
    ),
    PatternEntry(
        name="danva_emotion",
        friendly="DANVA Emotion Reader",
        group="Module 1 / Individual",
        analyzer_cls="EmotionRecognitionAnalyzer",
        input_cls="AgentEmotionTrace",
        output_cls="EmotionRecognitionAnalysis",
        mode_alias="DANVAMode",
        composition_attr="DANVA_COMPOSITION",
        summary=(
            "Nowicki-Duke DANVA emotion-recognition cascade applied "
            "to agent dialogue: detect missed user emotion cues that "
            "propagated to downstream response failures."
        ),
    ),
    PatternEntry(
        name="cognitive_reappraisal",
        friendly="Cognitive Reappraisal",
        group="Module 1 / Individual",
        analyzer_cls="ReappraisalAnalyzer",
        input_cls="AgentRegulationTrace",
        output_cls="RegulationDetection",
        mode_alias="ReappraisalMode",
        composition_attr="REAPPRAISAL_COMPOSITION",
        summary=(
            "James Gross's cognitive reappraisal vs. suppression "
            "applied to agent emotion regulation under hostile / "
            "ambiguous user input."
        ),
    ),
    PatternEntry(
        name="yerkes_dodson",
        friendly="Yerkes-Dodson Workload",
        group="Module 1 / Individual",
        analyzer_cls="WorkloadDetector",
        input_cls="AgentPerformanceTrace",
        output_cls="WorkloadDetection",
        mode_alias="YerkesDodsonMode",
        composition_attr="YERKES_DODSON_COMPOSITION",
        summary=(
            "Yerkes-Dodson inverted-U arousal/load curve applied to "
            "agent context-window pressure: detect under-load drift "
            "vs. over-load collapse."
        ),
    ),
    PatternEntry(
        name="hexaco",
        friendly="HEXACO Personality",
        group="Module 1 / Individual",
        analyzer_cls="HEXACOPersonalityAnalyzer",
        input_cls="AgentPersonalityTrace",
        output_cls="HEXACODetection",
        mode_alias="HEXACOMode",
        composition_attr="HEXACO_COMPOSITION",
        summary=(
            "Lee-Ashton HEXACO six-factor personality model used to "
            "profile agent behavioral signature and detect drift from "
            "the intended persona spec."
        ),
    ),
    PatternEntry(
        name="grant_strengths",
        friendly="Grant Strengths as Weaknesses",
        group="Module 1 / Individual",
        analyzer_cls="GrantStrengthsAnalyzer",
        input_cls="AgentBehaviorTrace",
        output_cls="StrengthOveruseDetection",
        mode_alias="GrantMode",
        composition_attr="GRANT_COMPOSITION",
        summary=(
            "Adam Grant's strength-overuse pattern applied to agents: "
            "detect when a productive trait (thoroughness, caution, "
            "creativity) flips into a failure mode under load."
        ),
    ),
    PatternEntry(
        name="motivation_traps",
        friendly="Motivation Traps",
        group="Module 1 / Individual",
        analyzer_cls="MotivationTrapsAnalyzer",
        input_cls="AgentMotivationTrace",
        output_cls="MotivationDetection",
        mode_alias="MotivationMode",
        composition_attr="MOTIVATION_COMPOSITION",
        summary=(
            "Saxberg-style motivation-trap diagnostic: detect when "
            "an agent's optimization target drifts away from the "
            "user's actual goal."
        ),
    ),
    PatternEntry(
        name="sdt_reward",
        friendly="SDT Intrinsic Reward",
        group="Module 1 / Individual",
        analyzer_cls="SDTRewardAnalyzer",
        input_cls="AgentSDTTrace",
        output_cls="SDTDetection",
        mode_alias="SDTMode",
        composition_attr="SDT_COMPOSITION",
        summary=(
            "Deci-Ryan Self-Determination Theory (autonomy / "
            "competence / relatedness) applied to agent reward "
            "design and intrinsic-motivation fit."
        ),
    ),
    PatternEntry(
        name="mcgregor",
        friendly="McGregor Orchestrator Mode",
        group="Module 1 / Individual",
        analyzer_cls="McGregorOrchestratorAnalyzer",
        input_cls="OrchestratorTrace",
        output_cls="OrchestratorModeDetection",
        mode_alias="McGregorMode",
        composition_attr="MCGREGOR_COMPOSITION",
        summary=(
            "Douglas McGregor's Theory X / Theory Y applied to agent "
            "orchestrators: detect over-controlling vs. under-trusting "
            "orchestration patterns."
        ),
    ),
    PatternEntry(
        name="vroom_expectancy",
        friendly="Vroom Expectancy",
        group="Module 1 / Individual",
        analyzer_cls="VroomExpectancyAnalyzer",
        input_cls="AgentExpectancyTrace",
        output_cls="VroomDetection",
        mode_alias="VroomMode",
        composition_attr="VROOM_COMPOSITION",
        summary=(
            "Vroom's expectancy theory (effort * instrumentality * "
            "valence) applied to agent task-engagement diagnosis."
        ),
    ),
    PatternEntry(
        name="grpi",
        friendly="GRPI Working Agreement",
        group="Module 2 / Team",
        analyzer_cls="GRPIWorkingAgreementAnalyzer",
        input_cls="TeamSetupRequest",
        output_cls="WorkingAgreement",
        mode_alias="GRPIMode",
        composition_attr="GRPI_COMPOSITION",
        summary=(
            "Beckhard's Goals/Roles/Processes/Interactions framework: "
            "generate a working agreement spec for a new multi-agent "
            "team given the task + agent roster."
        ),
    ),
    PatternEntry(
        name="process_gain_loss",
        friendly="Process Gain/Loss",
        group="Module 2 / Team",
        analyzer_cls="ProcessGainLossAnalyzer",
        input_cls="ProcessTrace",
        output_cls="ProcessGainLossDetection",
        mode_alias="ProcessGainLossMode",
        composition_attr="PROCESS_COMPOSITION",
        summary=(
            "Steiner's process gain/loss model: did the multi-agent "
            "team outperform the best individual agent (gain) or "
            "underperform (process loss from coordination friction)?"
        ),
    ),
    PatternEntry(
        name="social_loafing",
        friendly="Social Loafing Detector",
        group="Module 2 / Team",
        analyzer_cls="SocialLoafingAnalyzer",
        input_cls="MultiAgentTaskTrace",
        output_cls="SocialLoafingDetection",
        mode_alias="SocialLoafingMode",
        composition_attr="SOCIAL_LOAFING_COMPOSITION",
        summary=(
            "Latane-Williams-Harkins social-loafing pattern: detect "
            "agents that contribute less when responsibility is "
            "diffused across a multi-agent crew."
        ),
    ),
    PatternEntry(
        name="superflocks",
        friendly="Superflocks Detector",
        group="Module 2 / Team",
        analyzer_cls="SuperflocksAnalyzer",
        input_cls="RoutingTrace",
        output_cls="SuperflocksDetection",
        mode_alias="SuperflocksMode",
        composition_attr="SUPERFLOCKS_COMPOSITION",
        summary=(
            "Heffernan-style superflock pattern: detect when a "
            "multi-agent routing layer over-concentrates traffic on "
            "a small set of agents and starves the rest."
        ),
    ),
    PatternEntry(
        name="lencioni",
        friendly="Lencioni Five Dysfunctions",
        group="Module 2 / Team",
        analyzer_cls="LencioniAnalyzer",
        input_cls="MultiAgentTrace",
        output_cls="LencioniDiagnosis",
        mode_alias="LencioniMode",
        composition_attr="LENCIONI_COMPOSITION",
        summary=(
            "Patrick Lencioni's Five Dysfunctions pyramid (absence of "
            "trust -> fear of conflict -> lack of commitment -> "
            "avoidance of accountability -> inattention to results) "
            "applied to multi-agent teams."
        ),
    ),
    PatternEntry(
        name="trust_triangle",
        friendly="Trust Triangle Audit",
        group="Module 2 / Team",
        analyzer_cls="TrustTriangleAnalyzer",
        input_cls="AgentInteractionTrace",
        output_cls="TrustTriangleAudit",
        mode_alias="TrustTriangleMode",
        composition_attr="TRUST_TRIANGLE_COMPOSITION",
        summary=(
            "Frei & Morriss's Trust Triangle (logic / authenticity / "
            "empathy): which leg is wobbling in this agent's "
            "interaction trace, and how do we shore it up?"
        ),
    ),
    PatternEntry(
        name="mcallister_trust",
        friendly="McAllister Trust Balance",
        group="Module 2 / Team",
        analyzer_cls="TrustBalanceAnalyzer",
        input_cls="TrustConversationTrace",
        output_cls="TrustBalanceDetection",
        mode_alias="McAllisterMode",
        composition_attr="MCALLISTER_COMPOSITION",
        summary=(
            "McAllister's cognitive- vs. affective-based trust "
            "dimensions: is this agent trusted on competence, "
            "rapport, or neither?"
        ),
    ),
    PatternEntry(
        name="psych_safety",
        friendly="Edmondson Psychological Safety",
        group="Module 2 / Team",
        analyzer_cls="PsychologicalSafetyAnalyzer",
        input_cls="MultiAgentSafetyTrace",
        output_cls="PsychologicalSafetyDetection",
        mode_alias="PsychSafetyMode",
        composition_attr="PSYCH_SAFETY_COMPOSITION",
        summary=(
            "Amy Edmondson's psychological-safety scale applied to "
            "multi-agent teams: are agents willing to raise dissent, "
            "admit error, and surface bad news?"
        ),
    ),
    PatternEntry(
        name="glaser_conversation",
        friendly="Glaser Conversation Steering",
        group="Module 2 / Team",
        analyzer_cls="ConversationSteeringAnalyzer",
        input_cls="ConversationTrace",
        output_cls="ConversationSteeringDetection",
        mode_alias="GlaserMode",
        composition_attr="GLASER_COMPOSITION",
        summary=(
            "Judith Glaser's Level I/II/III conversational intelligence "
            "applied to agent-user interactions: how to escalate from "
            "transactional to co-creating dialogue."
        ),
    ),
    PatternEntry(
        name="feedback_triggers",
        friendly="Stone-Heen Feedback Triggers",
        group="Module 2 / Team",
        analyzer_cls="FeedbackTriggerAnalyzer",
        input_cls="FeedbackInteractionTrace",
        output_cls="FeedbackTriggerDetection",
        mode_alias="FeedbackTriggersMode",
        composition_attr="FEEDBACK_TRIGGERS_COMPOSITION",
        summary=(
            "Stone-Heen feedback-trigger taxonomy (truth / relationship "
            "/ identity triggers): which trigger fired when the agent "
            "got defensive or refused valid feedback?"
        ),
    ),
    PatternEntry(
        name="plus_delta",
        friendly="Plus/Delta Feedback",
        group="Module 2 / Team",
        analyzer_cls="PlusDeltaFeedbackAnalyzer",
        input_cls="FeedbackRequest",
        output_cls="PlusDeltaFeedback",
        mode_alias="PlusDeltaMode",
        composition_attr="PLUS_DELTA_COMPOSITION",
        summary=(
            "Facilitator-canon Plus/Delta feedback format: generate "
            "structured, behavioral, commitment-bearing feedback "
            "between agents instead of vague 'good job'."
        ),
    ),
    PatternEntry(
        name="smart_goal",
        friendly="SMART Goal Generator",
        group="Module 2 / Team",
        analyzer_cls="SMARTGoalAnalyzer",
        input_cls="GoalRequest",
        output_cls="SMARTGoal",
        mode_alias="SmartGoalMode",
        composition_attr="SMART_GOAL_COMPOSITION",
        summary=(
            "Doran's SMART criteria (specific / measurable / achievable "
            "/ relevant / time-bound): turn a vague agent goal into a "
            "self-auditable spec with kill criteria."
        ),
    ),
    PatternEntry(
        name="group_decision",
        friendly="Group Decision Protocol",
        group="Module 2 / Team",
        analyzer_cls="DecisionProtocolAnalyzer",
        input_cls="DecisionRequest",
        output_cls="DecisionProtocol",
        mode_alias="GroupDecisionMode",
        composition_attr="GROUP_DECISION_COMPOSITION",
        summary=(
            "Facilitator-canon decision models (concurring / majority / "
            "consensus / fist-to-five / unanimous): pick the right "
            "aggregation method for a multi-agent decision and emit "
            "the protocol spec."
        ),
    ),
    PatternEntry(
        name="debate_pathology",
        friendly="Debate Pathology",
        group="Module 2 / Team",
        analyzer_cls="DebatePathologyAnalyzer",
        input_cls="MultiAgentDebateTrace",
        output_cls="DebatePathologyDetection",
        mode_alias="DebatePathologyMode",
        composition_attr="DEBATE_PATHOLOGY_COMPOSITION",
        summary=(
            "Janis-style groupthink / Moscovici polarization / "
            "preference-contagion detection in multi-agent debates: "
            "did the crew converge prematurely or polarize past "
            "evidence?"
        ),
    ),
    PatternEntry(
        name="bias_stack",
        friendly="Bias Stack Detector",
        group="Module 2 / Team",
        analyzer_cls="BiasStackAnalyzer",
        input_cls="AgentReasoningTrace",
        output_cls="BiasStackDetection",
        mode_alias="BiasStackMode",
        composition_attr="BIAS_STACK_COMPOSITION",
        summary=(
            "Kahneman/Tversky cognitive-bias stack applied to agent "
            "reasoning traces: anchoring, availability, confirmation, "
            "framing, sunk-cost, etc."
        ),
    ),
    PatternEntry(
        name="devils_advocate",
        friendly="Devil's Advocate Separator",
        group="Module 2 / Team",
        analyzer_cls="RoleSeparationAnalyzer",
        input_cls="SingleAgentTrace",
        output_cls="RoleSeparationDetection",
        mode_alias="DevilsAdvocateMode",
        composition_attr="DEVILS_ADVOCATE_COMPOSITION",
        summary=(
            "Janis-style devil's-advocate role-separation diagnostic: "
            "does this single agent collapse advocate + critic into "
            "one role, undermining dissent?"
        ),
    ),
    PatternEntry(
        name="thomas_kilmann",
        friendly="Thomas-Kilmann Conflict",
        group="Module 2 / Team",
        analyzer_cls="ConflictStyleAnalyzer",
        input_cls="AgentInteractionTrace",
        output_cls="ConflictStyleSelection",
        mode_alias="ThomasKilmannMode",
        composition_attr="THOMAS_KILMANN_COMPOSITION",
        summary=(
            "Thomas-Kilmann five conflict styles (competing / "
            "collaborating / compromising / avoiding / accommodating): "
            "what style is this agent defaulting to, and is it the "
            "right one for the situation?"
        ),
    ),
    PatternEntry(
        name="aar",
        friendly="After-Action Review",
        group="Module 2 / Team",
        analyzer_cls="AARAnalyzer",
        input_cls="AgentTrace",
        output_cls="AAR",
        mode_alias="AARMode",
        composition_attr="AAR_COMPOSITION",
        summary=(
            "Wharton 4-step After-Action Review (goal / results / "
            "lessons / next steps) applied to agent runs. The "
            "foundational vstack diagnostic that every other pattern "
            "composes with."
        ),
        citations_present=False,
    ),
    PatternEntry(
        name="schein_culture",
        friendly="Schein Culture Audit",
        group="Module 3 / Organization",
        analyzer_cls="CultureAuditAnalyzer",
        input_cls="AgentCultureTrace",
        output_cls="CultureAuditDetection",
        mode_alias="ScheinMode",
        composition_attr="SCHEIN_COMPOSITION",
        summary=(
            "Edgar Schein's three-layer culture model "
            "(artifacts / espoused values / underlying assumptions) "
            "applied to agent-crew culture: where does the "
            "assumption-layer diverge from the espoused value?"
        ),
    ),
    PatternEntry(
        name="robbins_culture",
        friendly="Robbins-Judge Culture",
        group="Module 3 / Organization",
        analyzer_cls="CultureProfileAnalyzer",
        input_cls="AgentCultureTrace",
        output_cls="CultureProfileDetection",
        mode_alias="RobbinsMode",
        composition_attr="ROBBINS_COMPOSITION",
        summary=(
            "Robbins-Judge 7-characteristic culture profile (innovation, "
            "attention to detail, outcome orientation, people "
            "orientation, team orientation, aggressiveness, stability) "
            "applied to agent crews."
        ),
    ),
    PatternEntry(
        name="org_structure",
        friendly="Org Structure Matrix",
        group="Module 3 / Organization",
        analyzer_cls="StructureMatrixAnalyzer",
        input_cls="CrewStructureTrace",
        output_cls="StructureAnalysis",
        mode_alias="StructureMode",
        composition_attr="STRUCTURE_COMPOSITION",
        summary=(
            "Galbraith-Mintzberg structural-fit matrix across six "
            "dimensions (specialization, departmentalization, chain of "
            "command, span, centralization, formalization): does the "
            "crew structure fit the task class?"
        ),
    ),
    PatternEntry(
        name="span_of_control",
        friendly="Span of Control",
        group="Module 3 / Organization",
        analyzer_cls="SpanLoadCalculator",
        input_cls="CrewLoadTrace",
        output_cls="SpanLoadAnalysis",
        mode_alias="SpanMode",
        composition_attr="SPAN_COMPOSITION",
        summary=(
            "Deterministic Graicunas-Urwick span-of-control / "
            "centralization audit: six numeric metrics computed in "
            "Python with the LLM gated out of the math. Pairs with "
            "Org Structure Matrix for the qualitative fit story."
        ),
    ),
)


PATTERNS_BY_NAME: dict[str, PatternEntry] = {p.name: p for p in PATTERNS}


def tool_name_for(pattern: PatternEntry) -> str:
    """The MCP tool name exposed to clients, e.g. ``vstack_lewin``.

    MCP tool names should be safe identifiers; we use the underscore-
    prefixed form rather than dashes to maximize compatibility with
    clients that treat dashes as flag separators in their tool-listing
    UI.
    """
    return f"vstack_{pattern.name}"
