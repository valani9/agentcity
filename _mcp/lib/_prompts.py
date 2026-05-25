"""MCP prompt templates — one per pattern plus a meta picker.

MCP prompts are reusable invocation templates a client can render
ahead of time. The server publishes:

* one ``vstack_<name>_invoke`` prompt per pattern that guides an LLM
  to populate that pattern's tool with a free-form trace description
  and a mode preference;
* one meta prompt ``vstack_pick_pattern`` that takes a free-form
  problem description and asks the LLM which of the 34 patterns is
  the right tool for the job.

The prompt text is intentionally terse — most of the patterning is
done at the MCP tool layer (which carries the input JSON schema and
the summary). Prompts only steer the LLM toward the right tool name
and the right mode choice.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._registry import PATTERNS, PATTERNS_BY_NAME, PatternEntry, tool_name_for


@dataclass(frozen=True)
class PromptArgSpec:
    name: str
    description: str
    required: bool


@dataclass(frozen=True)
class PromptSpec:
    name: str
    description: str
    arguments: tuple[PromptArgSpec, ...]


PICK_PATTERN_PROMPT = PromptSpec(
    name="vstack_pick_pattern",
    description=(
        "Given a free-form description of an AI-agent failure or "
        "team-design challenge, recommend which of the 34 vstack "
        "patterns to run and why."
    ),
    arguments=(
        PromptArgSpec(
            name="situation",
            description=(
                "Free-form description of the failure, design challenge, "
                "or diagnostic question. The richer this is, the more "
                "specific the pattern recommendation."
            ),
            required=True,
        ),
        PromptArgSpec(
            name="known_artifacts",
            description=(
                "Optional comma-separated hints about what artifacts you "
                "already have (e.g. 'agent trace, user complaint, "
                "team config') — narrows which pattern's input shape "
                "is achievable today."
            ),
            required=False,
        ),
    ),
)


def list_prompts() -> list[PromptSpec]:
    """Enumerate the prompt specs the server exposes."""
    out: list[PromptSpec] = [PICK_PATTERN_PROMPT]
    for p in PATTERNS:
        out.append(_invoke_prompt_for(p))
    return out


def _invoke_prompt_for(pattern: PatternEntry) -> PromptSpec:
    return PromptSpec(
        name=f"vstack_{pattern.name}_invoke",
        description=(
            f"Run the {pattern.friendly} diagnostic on a described "
            f"agent or team artifact. {pattern.summary}"
        ),
        arguments=(
            PromptArgSpec(
                name="artifact",
                description=(
                    "Free-form description of the artifact to diagnose "
                    f"(e.g. an agent trace, a team config, a debate "
                    f"transcript). The MCP client will translate this "
                    f"into the {pattern.input_cls} input schema for the "
                    f"{tool_name_for(pattern)} tool."
                ),
                required=True,
            ),
            PromptArgSpec(
                name="mode",
                description=(
                    "Pipeline mode: 'quick' (1 LLM call, scoring + top "
                    "intervention; CI / live ops), 'standard' (2 LLM "
                    "calls, full scoring + ranked interventions), or "
                    "'forensic' (4 LLM calls, deep diagnosis). Defaults "
                    "to 'standard' if omitted."
                ),
                required=False,
            ),
        ),
    )


def render_prompt(name: str, arguments: dict[str, str] | None = None) -> str:
    """Render a prompt to a plain-text message body.

    The MCP client passes the rendered text to its LLM as the user
    turn; the LLM then issues a tool call. We keep the rendering
    deterministic and self-contained so a client never needs to
    re-parse the prompt arguments.
    """
    arguments = arguments or {}
    if name == PICK_PATTERN_PROMPT.name:
        return _render_pick_pattern(arguments)
    if name.startswith("vstack_") and name.endswith("_invoke"):
        pattern_name = name[len("vstack_") : -len("_invoke")]
        pattern = PATTERNS_BY_NAME.get(pattern_name)
        if pattern is None:
            raise ValueError(f"Unknown vstack prompt: {name}")
        return _render_invoke(pattern, arguments)
    raise ValueError(f"Unknown vstack prompt: {name}")


def _render_pick_pattern(args: dict[str, str]) -> str:
    situation = args.get("situation", "(unspecified)")
    artifacts = args.get("known_artifacts", "")
    catalogue = "\n".join(f"- {tool_name_for(p)} ({p.group}) — {p.summary}" for p in PATTERNS)
    artifact_line = f"\nKnown artifacts: {artifacts}\n" if artifacts else "\n"
    return (
        "You are routing a vstack diagnostic request. The user described "
        "this situation:\n\n"
        f"---\n{situation}\n---\n"
        f"{artifact_line}"
        "Pick the single best vstack pattern from the catalogue below "
        "and call its MCP tool. If two or three patterns are equally "
        "good, recommend the upstream / foundational one first (AAR "
        "for postmortems, Lewin for attribution, Schein for culture) "
        "and note the downstream chain.\n\n"
        "Available tools:\n"
        f"{catalogue}\n\n"
        "Output a one-paragraph rationale, then call the chosen MCP "
        "tool with the artifact details extracted from the situation."
    )


def _render_invoke(pattern: PatternEntry, args: dict[str, str]) -> str:
    artifact = args.get("artifact", "(unspecified)")
    mode = args.get("mode", "standard")
    return (
        f"Run the {pattern.friendly} diagnostic.\n\n"
        f"What the diagnostic does: {pattern.summary}\n\n"
        f"Artifact to diagnose:\n---\n{artifact}\n---\n\n"
        f"Mode: {mode}\n\n"
        f"Call the MCP tool '{tool_name_for(pattern)}'. Translate the "
        f"artifact description above into the tool's input JSON schema "
        f"(see the {pattern.input_cls} model on the tool definition). "
        f"After the tool returns, write a short executive summary of "
        f"the top finding and the recommended next intervention."
    )
