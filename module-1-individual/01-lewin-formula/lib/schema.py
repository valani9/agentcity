"""Schema for the Lewin Formula Diagnostic: B = f(P, E).

Kurt Lewin's behavior formula (Lewin, 1936, *Principles of Topological
Psychology*, p. 12) states that every psychological event depends both
on the state of the person and on the environment, though their
relative importance differs case by case. The diagnostic operationalizes
that formula for AI agent failures.

The schema is split into three layers:

  - **Input**: an :class:`AgentFailureTrace` describing what the agent
    tried to do, what it actually did, and what individual + environmental
    factors the team has already enumerated. The schema is generous —
    you can pass a minimal trace (task, steps, outcome) or a fully
    enriched one (factors, initial attribution, covariance signal).

  - **Output**: a :class:`LewinDetection` with per-locus scores,
    evidence with confidence intervals, recommended interventions
    annotated with effort + risk + reversibility, and composition
    handoffs pointing to other AgentCity patterns that should run next.

  - **Auxiliary**: :class:`CovarianceSignal` (Kelley 1967 covariation
    inputs), :class:`BaselineComparison` (drift versus a stored
    historical detection), :class:`ComposedPatternHandoff` (where this
    detection feeds into the rest of the AgentCity library).

Three pipeline modes are exposed:

  - ``quick`` — single LLM call, scoring + one top intervention; CI / live ops.
  - ``standard`` — two-pass current behavior; human-driven postmortem.
  - ``forensic`` — four passes: covariance-aware scoring,
    counterfactual swap analysis, Gilbert-Malone bias mechanism
    diagnosis on the team's initial attribution, ranked interventions
    with composition targets.

The mapping of Lewin's two variables onto an LLM agent:

  - **INTERNAL (P)** — the model itself: base model, fine-tuning, RLHF,
    sampling configuration (temperature, top-p, seed), reasoning effort,
    context window, model version, safety filter strictness. These are
    the "person" components — properties of the agent that do not change
    between runs of the same model under the same configuration.

  - **ENVIRONMENTAL (E)** — everything the agent encounters in this turn:
    system prompt, tools available, RAG context, conversation history,
    memory store, task framing, user inputs, downstream consumers,
    rate limits, tool responses, output parser, orchestration topology,
    verification step, safety filter, caching layer. These are the
    "field" components — the situational features the team has direct
    control over without retraining.

  - **INTERACTIONAL** — failure requires both the specific model *and*
    the specific environment. Swapping either alone does not resolve
    it. This is the locus most teams under-diagnose.

The schema is conservative: every new field defaults to a sensible
no-op value so existing 0.0.x traces and detections continue to
deserialize. New severity values are *added* (the 7-point scale) but
the original four (``none``, ``low``, ``medium``, ``high``) remain
valid for backward compatibility.

Citations are tracked in :mod:`agentcity.lewin.CITATIONS`. The 11-source
literature thread (Lewin 1936, 1939, 1947, 1951; Heider 1958;
Jones & Harris 1967; Kelley 1967; Ross 1977; Mischel & Shoda 1995;
Funder & Ozer 1983; Gilbert & Malone 1995; Bandura 1986;
Cemri et al. 2025) is named in the README and reflected in the
generator's system prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Public locus tuple. Extended set including "indeterminate" used in
# diagnostic output when no locus reaches the confidence threshold.
LOCI: tuple[str, ...] = ("internal", "environmental", "interactional")
LOCI_WITH_INDETERMINATE: tuple[str, ...] = (*LOCI, "indeterminate")

# Pipeline mode controls how many LLM calls the detector issues and
# which auxiliary passes run. See the module docstring for the contract.
LewinMode = Literal["quick", "standard", "forensic"]
LEWIN_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# 7-point severity scale. The original 4-point scale ("none","low","medium","high")
# is preserved for backward compatibility — values are a strict superset.
Severity = Literal[
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_score(score: float) -> Severity:
    """Deterministically map a [0,1] locus score to a 7-point severity bucket.

    Used by the standard and forensic pipelines when the LLM omits
    severity or produces a value outside the expected enum. The bucket
    boundaries are chosen so that the original 4-point buckets map
    cleanly: 0.0 → none; (0,0.15] → trace; (0.15,0.35] → low;
    (0.35,0.55] → moderate; (0.55,0.7] → medium; (0.7,0.85] → high;
    (0.85,1.0] → critical.
    """
    s = max(0.0, min(1.0, float(score)))
    if s <= 0.0:
        return "none"
    if s <= 0.15:
        return "trace"
    if s <= 0.35:
        return "low"
    if s <= 0.55:
        return "moderate"
    if s <= 0.7:
        return "medium"
    if s <= 0.85:
        return "high"
    return "critical"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Covariation inputs — Kelley (1967)
# ---------------------------------------------------------------------------


class CovarianceSignal(BaseModel):
    """Kelley (1967) covariation principle inputs.

    Attribution theory holds that observers infer causes by checking
    three covariation dimensions:

      - **consensus** — does the same prompt elicit the failure across
        *other* models? High consensus implies the cause is the
        environment / task (everyone fails the same way). Low consensus
        implies the cause is internal to *this* model.
      - **distinctiveness** — does this model fail *only* on this task?
        High distinctiveness implies environment / task specificity.
      - **consistency** — does the failure recur across repeated runs of
        the same model on the same task? High consistency implies a
        stable cause (internal or environmental); low consistency implies
        a stochastic trigger (sampling, RAG freshness, tool latency).

    Joint pattern → typical attribution (Kelley 1967):

      - high consensus + high distinctiveness + high consistency →
        ENVIRONMENTAL (everyone fails this task; same model only fails
        here; failure repeats reliably)
      - low consensus + low distinctiveness + high consistency →
        INTERNAL (this model fails widely and reliably)
      - low consensus + high distinctiveness + low consistency →
        INTERACTIONAL (specific model × task × stochastic interaction)

    When ``consensus`` / ``distinctiveness`` / ``consistency`` are
    ``"unknown"`` the deterministic prior is the identity (no nudge).
    """

    consensus: Literal["unknown", "low", "mixed", "high"] = "unknown"
    distinctiveness: Literal["unknown", "low", "mixed", "high"] = "unknown"
    consistency: Literal["unknown", "low", "mixed", "high"] = "unknown"
    notes: str = Field(
        default="",
        description="Free-text context for any of the three dimensions; "
        "sanitized + fenced before injection into prompts.",
    )


# ---------------------------------------------------------------------------
# Input — factors, steps, trace
# ---------------------------------------------------------------------------


# Individual (P) factor enum — the model's "person" components.
# The original 9 values are preserved. The new values add:
#   - sampling_config: temperature, top-p, top-k, seed, repetition penalty.
#   - model_version: identical model id but a quiet update changes behavior.
#   - inference_settings: max output tokens, reasoning effort, tool-choice mode.
#   - safety_filter_strictness: how aggressively the model refuses.
#   - decoding_strategy: greedy vs sampling vs constrained decoding.
IndividualFactorName = Literal[
    "base_model",
    "fine_tuning",
    "rlhf",
    "training_cutoff",
    "reasoning_capability",
    "tool_use_skill",
    "language_support",
    "context_window_size",
    # New in v0.2.0 — schema extensions per the research thread.
    "sampling_config",
    "model_version",
    "inference_settings",
    "safety_filter_strictness",
    "decoding_strategy",
    "other",
]

INDIVIDUAL_FACTOR_NAMES: tuple[str, ...] = (
    "base_model",
    "fine_tuning",
    "rlhf",
    "training_cutoff",
    "reasoning_capability",
    "tool_use_skill",
    "language_support",
    "context_window_size",
    "sampling_config",
    "model_version",
    "inference_settings",
    "safety_filter_strictness",
    "decoding_strategy",
    "other",
)


class IndividualFactor(BaseModel):
    """A model-side factor that may have contributed to the failure.

    The factor enum covers the standard P-side dimensions for an LLM
    agent: training-time properties (base_model, fine_tuning, rlhf,
    training_cutoff), capability ceilings (reasoning_capability,
    tool_use_skill, language_support, context_window_size), and
    inference-time configuration (sampling_config, model_version,
    inference_settings, safety_filter_strictness, decoding_strategy).

    The ``factor_id`` field is optional; when provided it lets
    :class:`LocusEvidence` cite specific factors by id rather than by
    name only, supporting traces that include several factors with the
    same ``factor`` enum value (e.g. two sampling configurations
    compared across runs).
    """

    factor: IndividualFactorName
    description: str = Field(
        description="What this factor is, as concretely as possible. "
        "Sanitized + fenced before any LLM injection."
    )
    factor_id: str | None = Field(
        default=None,
        description="Optional stable id for this factor (e.g. 'p-temperature-0.7'). "
        "Lets LocusEvidence.factor_citations point to a specific factor "
        "instance when several share the same enum value.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Team's confidence that this factor is real / "
        "measurable (not whether it caused the failure).",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# Environmental (E) factor enum. Original 11 values plus 7 new ones
# tied to the MAST taxonomy (Cemri et al. 2025) and modern agent
# infrastructure: conversation_history, memory_store, output_parser,
# safety_filter, caching_layer, multi_agent_topology, verification_step.
EnvironmentalFactorName = Literal[
    "system_prompt",
    "tools_available",
    "rag_context",
    "task_framing",
    "user_inputs",
    "downstream_consumers",
    "rate_limits",
    "tool_responses",
    "feedback_loops",
    "orchestration",
    # New in v0.2.0.
    "conversation_history",
    "memory_store",
    "output_parser",
    "safety_filter",
    "caching_layer",
    "multi_agent_topology",
    "verification_step",
    "other",
]

ENVIRONMENTAL_FACTOR_NAMES: tuple[str, ...] = (
    "system_prompt",
    "tools_available",
    "rag_context",
    "task_framing",
    "user_inputs",
    "downstream_consumers",
    "rate_limits",
    "tool_responses",
    "feedback_loops",
    "orchestration",
    "conversation_history",
    "memory_store",
    "output_parser",
    "safety_filter",
    "caching_layer",
    "multi_agent_topology",
    "verification_step",
    "other",
)


class EnvironmentalFactor(BaseModel):
    """A non-model factor that may have contributed to the failure.

    The enum covers (in the order presented): the agent's textual
    scaffolding (system_prompt, task_framing, user_inputs), tool /
    runtime surface (tools_available, tool_responses, rate_limits,
    output_parser, caching_layer, safety_filter), retrieval /
    context (rag_context, conversation_history, memory_store),
    orchestration (orchestration, multi_agent_topology,
    verification_step, feedback_loops), and downstream (downstream_consumers).
    """

    factor: EnvironmentalFactorName
    description: str = Field(
        description="What this factor is, concretely. Sanitized + fenced before any LLM injection."
    )
    factor_id: str | None = Field(default=None)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureStep(BaseModel):
    """One step in the agent's trace leading up to the failure.

    The ``type`` Literal is a strict superset of the v0.0.x set. New
    types track multi-agent and memory operations:

      - ``clarification_request`` — agent asked the user / another
        agent for clarification (MAST FM-2.2: failure to ask).
      - ``verification`` — explicit verification step (MAST FM-3.2:
        no/incomplete verification when this is missing).
      - ``handoff`` — control transferred to another agent in a
        multi-agent topology.
      - ``memory_read`` / ``memory_write`` — agent read from or wrote
        to a persistent memory store.
    """

    type: Literal[
        "input",
        "tool_call",
        "observation",
        "thought",
        "decision",
        "output",
        "error",
        # New in v0.2.0.
        "clarification_request",
        "verification",
        "handoff",
        "memory_read",
        "memory_write",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentFailureTrace(BaseModel):
    """An agent failure ready for the Lewin diagnostic.

    The minimal useful trace has a ``task``, a non-empty ``steps`` list,
    and an ``outcome``. Everything else is optional and additive —
    traces produced by older versions of the library or by adjacent
    instrumentation (LangSmith, Phoenix, Langfuse) can be ingested
    with minimal transformation.

    Where the v0.0.x schema stopped at factors + initial attribution,
    v0.2.0 adds:

      - ``covariance_signal`` — Kelley (1967) inputs that the diagnostic
        uses both in prompts and in deterministic priors.
      - ``framework`` — which agent framework this trace came from
        (LangGraph, CrewAI, AutoGen, Claude Agent SDK, OpenAI Agents
        SDK, Mastra, Strands). Affects composition handoffs.
      - ``run_count`` — how many times this trace has been observed
        (helps populate Kelley ``consistency``).
      - ``baseline_detection_path`` — optional path to a previously
        recorded :class:`LewinDetection` for drift comparison.
    """

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[FailureStep] = Field(min_length=1)
    outcome: str
    success: bool = False
    individual_factors: list[IndividualFactor] = Field(default_factory=list)
    environmental_factors: list[EnvironmentalFactor] = Field(default_factory=list)
    initial_attribution: str | None = Field(
        default=None,
        description="Optional: what locus the team initially blamed. The "
        "diagnostic checks whether that attribution holds up — and, in "
        "forensic mode, names which Gilbert-Malone correspondence-bias "
        "mechanism is at play if it does not.",
    )
    covariance_signal: CovarianceSignal | None = Field(
        default=None,
        description="Kelley (1967) covariation inputs. Optional but "
        "improves diagnostic accuracy substantially when known.",
    )
    framework: str | None = Field(
        default=None,
        description="Originating agent framework: one of 'langgraph', "
        "'crewai', 'autogen', 'claude-agent-sdk', 'openai-agents-sdk', "
        "'mastra', 'strands', 'custom', etc. Used by composition handoff "
        "to recommend the right downstream pattern.",
    )
    run_count: int = Field(default=1, ge=1)
    baseline_detection_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output — locus evidence, interventions, baseline, handoff, detection
# ---------------------------------------------------------------------------


# Gilbert & Malone (1995) names four mechanisms by which observers
# over-attribute behavior to disposition (the correspondence bias):
#   - unaware: observer lacks awareness of situational constraints
#   - unrealistic_expectation: observer holds an unrealistic baseline
#     for typical situational behavior
#   - over_categorization: observer inflates the actor's category
#     ("the model hallucinates" as a fixed trait)
#   - incomplete_correction: observer corrects insufficiently after
#     learning of constraint
# In forensic mode the diagnostic names which mechanism appears to
# explain the team's initial misattribution. ``none`` means either
# no initial attribution was provided, or the attribution was correct.
GilbertMaloneMechanism = Literal[
    "unaware",
    "unrealistic_expectation",
    "over_categorization",
    "incomplete_correction",
    "none",
]


class LocusEvidence(BaseModel):
    """Evidence for one Lewin locus contributing to the failure.

    The v0.2.0 schema adds three forensic-relevant fields:

      - ``confidence`` — calibrates the score: a score of 0.8 with
        confidence 0.4 is a tentative inference; a score of 0.8 with
        confidence 0.9 is a strong claim.
      - ``factor_citations`` — explicit list of ``factor_id`` strings
        from the input :class:`IndividualFactor` / :class:`EnvironmentalFactor`
        lists. The LLM is instructed (in forensic mode) to populate
        this; readers can audit the chain from input factor to score.
      - ``counterfactual`` — populated by forensic mode: "if you
        swapped X to Y, the failure would / would-not persist." This
        is the operational test of the locus assignment.
      - ``gilbert_malone_mechanism`` — populated by forensic mode when
        the team's initial attribution was wrong: names the bias
        mechanism driving the misattribution.
    """

    locus: Literal["internal", "environmental", "interactional"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Severity
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Model's confidence in this locus score, separate from "
        "the score itself. Use to detect over-confident hallucinations.",
    )
    factor_citations: list[str] = Field(
        default_factory=list,
        description="List of factor_id strings cited from the input trace.",
    )
    counterfactual: str = Field(
        default="",
        description="Populated by forensic mode: the swap-and-rerun "
        "operational test for this locus.",
    )
    gilbert_malone_mechanism: GilbertMaloneMechanism = Field(
        default="none",
        description="Populated by forensic mode when the team's initial "
        "attribution was wrong: which of the four correspondence-bias "
        "mechanisms (Gilbert & Malone 1995) drove the misattribution.",
    )


# Intervention typology — original 9 values plus 5 new ones tied to
# the new factor types: change_sampling, change_memory,
# add_verification_step, change_topology, change_safety_filter.
InterventionType = Literal[
    "change_model",
    "change_prompt",
    "change_tools",
    "change_context",
    "change_rag_index",
    "change_orchestration",
    "change_pipeline",
    "new_eval",
    "human_review",
    # New in v0.2.0.
    "change_sampling",
    "change_memory",
    "add_verification_step",
    "change_topology",
    "change_safety_filter",
    "compose_pattern",
]

INTERVENTION_TYPES: tuple[str, ...] = (
    "change_model",
    "change_prompt",
    "change_tools",
    "change_context",
    "change_rag_index",
    "change_orchestration",
    "change_pipeline",
    "new_eval",
    "human_review",
    "change_sampling",
    "change_memory",
    "add_verification_step",
    "change_topology",
    "change_safety_filter",
    "compose_pattern",
)


# Effort scale matches the SRE convention used elsewhere in AgentCity:
# "1h" / "1d" / "1w" / "1m" / "ongoing". Effort estimates are
# coarse-grained on purpose — the LLM is poor at sub-hour estimation
# but reliable on order-of-magnitude.
EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


class LewinIntervention(BaseModel):
    """A concrete intervention targeting one locus.

    v0.2.0 adds the operational fields a deployment team actually needs
    to schedule the intervention:

      - ``effort_estimate`` — coarse-grained calendar effort.
      - ``risk`` — operational risk if the intervention misfires.
      - ``reversibility`` — Bezos two-way / one-way door distinction.
      - ``composition_target_pattern`` — when the intervention is
        "run another AgentCity pattern as the next step", names that
        pattern (e.g. ``"agentcity.aar"``).
      - ``preconditions`` — what must be true before applying.
      - ``success_metric`` — measurable indicator of whether the
        intervention worked.
    """

    target_locus: Literal["internal", "environmental", "interactional"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    # New in v0.2.0.
    effort_estimate: EffortEstimate = Field(
        default="1d",
        description="Coarse calendar effort to implement.",
    )
    risk: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Operational risk if the intervention misfires.",
    )
    reversibility: Literal["one-way-door", "two-way-door"] = Field(
        default="two-way-door",
        description="Bezos two-way / one-way door. one-way means "
        "the intervention is hard to undo (e.g. fine-tune the model). "
        "two-way means the intervention can be reverted (e.g. change "
        "the system prompt).",
    )
    composition_target_pattern: str | None = Field(
        default=None,
        description="If this intervention is 'run another AgentCity "
        "pattern next', names that pattern's import path "
        "(e.g. 'agentcity.aar').",
    )
    preconditions: list[str] = Field(default_factory=list)
    success_metric: str = Field(
        default="",
        description="Measurable indicator the intervention worked.",
    )


# ---------------------------------------------------------------------------
# Baseline + composition + playbook
# ---------------------------------------------------------------------------


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical :class:`LewinDetection`."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_dominant_locus: str | None = None
    locus_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of the AgentCity library.

    The composition graph is declared statically in
    :mod:`agentcity.lewin._composition`. At detection time the generator
    consults the graph and recommends concrete downstream patterns
    based on ``dominant_locus`` + the trace's ``framework`` +
    intervention shape.
    """

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the detection.

    Playbooks are statically declared in
    :mod:`agentcity.lewin._playbooks` keyed by ``(locus, factor)``. When
    an intervention targets a key with a known playbook, the playbook
    is attached so the consumer can act without leaving the detection.
    """

    locus: Literal["internal", "environmental", "interactional"]
    factor: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


# ---------------------------------------------------------------------------
# Detection — the full output document
# ---------------------------------------------------------------------------


class LewinDetection(BaseModel):
    """The full Lewin diagnostic output.

    Backward-compatible with v0.0.x detections — every new field has a
    default value. Existing renderers calling :meth:`to_markdown` will
    still work; new fields render under additional sections at the end.
    """

    agent_id: str | None = None
    model_name: str | None = None
    dominant_locus: Literal["internal", "environmental", "interactional", "indeterminate"]
    locus_scores: dict[str, float]
    loci: list[LocusEvidence]
    interventions: list[LewinIntervention]
    attribution_quality: Literal["well-attributed", "ambiguous", "miscalibrated"]
    initial_attribution_correct: bool | None = Field(
        default=None,
        description="If the trace included `initial_attribution`, does the "
        "diagnostic agree? None when no initial attribution was provided.",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0 — provenance + cost + composition.
    mode: LewinMode = "standard"
    covariance_signal: CovarianceSignal | None = None
    baseline: BaselineComparison | None = None
    composition_handoff: ComposedPatternHandoff | None = None
    attached_playbooks: list[AttachedPlaybook] = Field(default_factory=list)
    bias_mechanism: GilbertMaloneMechanism = Field(
        default="none",
        description="Forensic-mode summary: which Gilbert-Malone "
        "correspondence-bias mechanism explains the team's misattribution "
        "(when one occurred). Mirrors LocusEvidence.gilbert_malone_mechanism "
        "at the detection level.",
    )
    cost_usd: float = Field(default=0.0, ge=0.0)
    tokens_total: int = Field(default=0, ge=0)
    tokens_input: int = Field(default=0, ge=0)
    tokens_output: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    run_id: str | None = None

    # ---- Rendering --------------------------------------------------------

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Lewin Diagnostic (B = f(P, E))\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Attribution quality: **{self.attribution_quality.upper()}**_\n")
        out.append(f"_Dominant locus: **{self.dominant_locus}**_\n")
        if self.initial_attribution_correct is not None:
            verdict = "AGREES" if self.initial_attribution_correct else "OVERTURNS"
            out.append(f"_Initial attribution: **{verdict}**_\n")
        if self.bias_mechanism != "none":
            out.append(f"_Correspondence-bias mechanism: **{self.bias_mechanism}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), "
                f"{self.tokens_total} tokens, ${self.cost_usd:.4f}, "
                f"{self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Locus Scores\n")
        out.append("Per-locus score (0.0 = absent, 1.0 = dominant cause).\n\n")
        for locus in LOCI:
            score = self.locus_scores.get(locus, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{locus}**: {score:.2f}  {bar}\n")

        if self.covariance_signal:
            out.append("\n## Covariation Signals (Kelley 1967)\n")
            cs = self.covariance_signal
            out.append(f"- **consensus**: {cs.consensus}\n")
            out.append(f"- **distinctiveness**: {cs.distinctiveness}\n")
            out.append(f"- **consistency**: {cs.consistency}\n")
            if cs.notes:
                out.append(f"- _notes_: {cs.notes}\n")

        out.append("\n## Evidence by Locus\n")
        for ev in self.loci:
            out.append(f"\n### {ev.locus} ({ev.severity}, score {ev.score:.2f}")
            if ev.confidence != 0.5:
                out.append(f", confidence {ev.confidence:.2f}")
            out.append(")\n")
            out.append(f"{ev.explanation}\n")
            if ev.factor_citations:
                out.append(f"\nCited factors: {', '.join(ev.factor_citations)}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")
            if ev.counterfactual:
                out.append(f"\n**Counterfactual:** {ev.counterfactual}\n")
            if ev.gilbert_malone_mechanism != "none":
                out.append(f"\n**Bias mechanism (this locus):** {ev.gilbert_malone_mechanism}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_locus}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            out.append(f"- **Effort:** {iv.effort_estimate}\n")
            out.append(f"- **Risk:** {iv.risk}\n")
            out.append(f"- **Reversibility:** {iv.reversibility}\n")
            if iv.preconditions:
                out.append(f"- **Preconditions:** {'; '.join(iv.preconditions)}\n")
            if iv.success_metric:
                out.append(f"- **Success metric:** {iv.success_metric}\n")
            if iv.composition_target_pattern:
                out.append(f"- **Composes with:** `{iv.composition_target_pattern}`\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(f"\n### {pb.title}  _(locus={pb.locus}, factor={pb.factor})_\n")
                for j, step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {step}\n")
                if pb.anchor_citation:
                    out.append(f"\n_Anchor: {pb.anchor_citation}_\n")

        if self.composition_handoff and (
            self.composition_handoff.downstream_patterns
            or self.composition_handoff.upstream_patterns
        ):
            out.append("\n## Composition Handoff\n")
            ch = self.composition_handoff
            if ch.upstream_patterns:
                out.append(f"- **Upstream:** {', '.join(f'`{p}`' for p in ch.upstream_patterns)}\n")
            if ch.downstream_patterns:
                out.append(
                    f"- **Recommended downstream:** "
                    f"{', '.join(f'`{p}`' for p in ch.downstream_patterns)}\n"
                )
            if ch.rationale:
                out.append(f"- **Rationale:** {ch.rationale}\n")

        if self.baseline:
            out.append("\n## Baseline Comparison\n")
            b = self.baseline
            out.append(f"- **Baseline id:** {b.historical_baseline_id or '(unset)'}\n")
            if b.historical_generated_at:
                out.append(
                    f"- **Baseline generated at:** {b.historical_generated_at.isoformat()}\n"
                )
            out.append(f"- **Baseline dominant locus:** {b.baseline_dominant_locus or '(unset)'}\n")
            if b.locus_score_deltas:
                out.append("- **Score deltas:**\n")
                for k, v in b.locus_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
