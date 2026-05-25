"""Core logic for ``vstack-hello``: synthetic trace + LLM resolution +
optional real-AAR run + sample-output fallback.

Split out from ``cli.py`` so it is unit-testable without spawning a
subprocess.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from vstack.aar import AAR, AgentTrace, TraceStep


class LLMResolutionStatus(str, Enum):
    """Outcome of looking for an LLM client in the environment."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    NONE = "none"


@dataclass(frozen=True)
class LLMResolution:
    """Result of ``resolve_llm_client``: either a usable client + label,
    or a reason no client was found."""

    status: LLMResolutionStatus
    client: Any | None
    label: str
    hint: str | None = None


@dataclass(frozen=True)
class HelloRunResult:
    """Everything ``run_hello`` produces. The CLI formats this; tests
    assert on the structured fields rather than parsed stdout."""

    resolution: LLMResolution
    trace: AgentTrace
    aar_markdown: str
    used_real_llm: bool
    elapsed_seconds: float | None = None
    notes: list[str] = field(default_factory=list)


# --- The synthetic trace ---------------------------------------------------

_FIXED_TS = datetime(2026, 5, 25, 14, 0, 0, tzinfo=timezone.utc)


def _build_sample_trace() -> AgentTrace:
    """A 7-step agent trace illustrating a recognizable failure mode:
    the agent loops on a failing tool call, then gives up without
    surfacing the upstream cause.

    The trace is deterministic — same fields every run — so the
    rendered output and any downstream comparison stays stable.
    """

    return AgentTrace(
        agent_id="hello-demo-agent",
        agent_framework="vstack-hello",
        goal="Add JWT authentication to the /login endpoint without breaking the existing session middleware.",
        steps=[
            TraceStep(
                timestamp=_FIXED_TS,
                type="thought",
                content=(
                    "I'll grep for the existing session middleware to see where to slot in JWT."
                ),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="tool_call",
                content="grep --include='*.py' -rn 'session_middleware' src/",
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="observation",
                content=("Found 3 matches in src/app/middleware.py. Reading the file..."),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="tool_call",
                content=(
                    "edit src/app/auth.py: insert "
                    "`from .jwt import encode_jwt` and patch /login "
                    "to call `encode_jwt(user_id)`."
                ),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="observation",
                content=(
                    "pytest tests/test_auth.py::test_login_session "
                    "FAILED — KeyError 'session_token' in "
                    "session_middleware (test expects the session "
                    "middleware to still see the legacy cookie)."
                ),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="tool_call",
                content=(
                    "edit src/app/auth.py: also write the JWT into a "
                    "`session_token` cookie to satisfy the old test."
                ),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="observation",
                content=(
                    "pytest still fails — now 2 tests broken. "
                    "test_logout_clears_session expects no Set-Cookie "
                    "header on logout, but session_middleware now "
                    "rewrites the JWT cookie on every response."
                ),
            ),
            TraceStep(
                timestamp=_FIXED_TS,
                type="message",
                content=(
                    "I added JWT to /login but the session middleware "
                    "is now coupling the two. Reverting JWT changes."
                ),
            ),
        ],
        outcome=(
            "Added JWT generation to /login, but the session middleware "
            "intercepts and rewrites the cookie on every response, "
            "breaking logout. Net: 2 new test failures and no JWT in "
            "production. Reverted."
        ),
        success=False,
        cost_usd=0.018,
        latency_seconds=42.5,
        retry_count=1,
    )


SAMPLE_TRACE: AgentTrace = _build_sample_trace()


# --- Pre-rendered sample AAR (offline fallback) ---------------------------

SAMPLE_AAR_MARKDOWN: str = """\
# After-Action Review — hello-demo-agent

## 1. What was the goal?

Add JWT authentication to the `/login` endpoint without breaking the
existing session middleware.

The agent was instructed to slot JWT in alongside an existing session
system. The task was scoped narrowly (one endpoint, one concern), but
the implicit contract — *don't break the middleware* — required
understanding two systems before touching either.

## 2. What actually happened?

The agent moved straight from "grep" to "edit" without reading the
session middleware in full. The first patch broke a session-coupling
test. The agent then tried to satisfy both the new JWT path and the
old session cookie path in the same response object, which broke a
second test (logout) because the middleware now re-wrote the cookie
on every response.

The agent never investigated the failing test's expectation, never
read the middleware's response-side logic, and ended by reverting
without surfacing the upstream cause.

## 3. Lessons learned

- **Pattern: edit-before-read.** The agent began modifying code
  before it had a complete model of the affected system. This is a
  recognizable failure mode in junior-engineer behavior and in
  agent traces — cross-link: **pattern #27 Bias-Stack Detector**
  (anchoring + availability) and **pattern #15 Social Loafing**
  (under-investing in the "boring" read phase).
  - Root cause: the agent treated grep matches as a sufficient
    map of the system. Three matches in one file gave the
    illusion of completeness.
  - Framework anchor: Wharton AAR — "What did the after-action
    investigation surface that you couldn't have known going in?"

- **Pattern: symptom-chasing.** When the first patch broke a test,
  the agent patched *that test's expectation* rather than asking
  *why* the test expected what it expected. This compounded the
  blast radius.
  - Root cause: missing the test-as-specification mindset.
  - Framework anchor: Stone & Heen, *Thanks for the Feedback* —
    coaching feedback says "the test is telling you something
    structural"; the agent heard "the test is in your way."

- **Pattern: silent-revert.** The final message announces a revert
  without naming the structural conflict. A future engineer (or
  agent) re-reading this trace cannot tell that the *session
  middleware rewrites response cookies* is the load-bearing fact.
  - Cross-link: **pattern #30 AAR Generator** (this one) —
    surfacing root cause is exactly what AARs are for.

## 4. Next steps

- **prompt_patch**: before any code edit, run an AAR pre-check —
  list every system that touches the endpoint being modified, then
  read each one end-to-end. Cost: ~1 extra LLM call up-front. Saves
  ~2-3 failure cycles downstream.
- **tool_addition**: give the agent a `read-response-side-of-middleware`
  helper so the "what does the middleware do to outgoing responses"
  question is one tool call, not a grep + read + summarize chain.
- **scaffold_change**: separate the JWT concern from the session
  concern at the middleware level (two middlewares, ordered) so
  future agents don't conflate them.
- **escalation**: if a fix patches a test's expectation without
  surfacing root cause, surface that to a human reviewer before
  shipping.

---

*Sample output — set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`, or run
a local Ollama instance) and re-run `vstack-hello` to see the AAR
generated against this trace by a real model.*
"""


# --- LLM resolution -------------------------------------------------------


def resolve_llm_client(env: dict[str, str] | None = None) -> LLMResolution:
    """Look at the process environment and return the first usable LLM
    client we can resolve, in this priority order:

    1. ``ANTHROPIC_API_KEY`` → ``AnthropicClient``
    2. ``OPENAI_API_KEY``    → ``OpenAIClient``
    3. ``OLLAMA_HOST``       → ``OllamaClient``

    If none are set, returns ``LLMResolutionStatus.NONE`` with a hint.
    """

    env = env if env is not None else dict(os.environ)

    if env.get("ANTHROPIC_API_KEY"):
        try:
            from vstack.aar.clients import AnthropicClient

            anthropic_client: Any = AnthropicClient()
            return LLMResolution(
                status=LLMResolutionStatus.ANTHROPIC,
                client=anthropic_client,
                label="Anthropic (claude-sonnet-4-6 default)",
            )
        except Exception as exc:
            return LLMResolution(
                status=LLMResolutionStatus.NONE,
                client=None,
                label="anthropic detected but client failed",
                hint=(
                    "ANTHROPIC_API_KEY is set but instantiating "
                    "AnthropicClient raised "
                    f"{type(exc).__name__}: {exc}. "
                    "Install the optional extra: "
                    "pip install 'valanistack[anthropic]'."
                ),
            )

    if env.get("OPENAI_API_KEY"):
        try:
            from vstack.aar.clients import OpenAIClient

            openai_client: Any = OpenAIClient()
            return LLMResolution(
                status=LLMResolutionStatus.OPENAI,
                client=openai_client,
                label="OpenAI (gpt-4o-mini default)",
            )
        except Exception as exc:
            return LLMResolution(
                status=LLMResolutionStatus.NONE,
                client=None,
                label="openai detected but client failed",
                hint=(
                    "OPENAI_API_KEY is set but instantiating "
                    "OpenAIClient raised "
                    f"{type(exc).__name__}: {exc}. "
                    "Install the optional extra: "
                    "pip install 'valanistack[openai]'."
                ),
            )

    if env.get("OLLAMA_HOST"):
        try:
            from vstack.aar.clients import OllamaClient

            ollama_client: Any = OllamaClient()
            return LLMResolution(
                status=LLMResolutionStatus.OLLAMA,
                client=ollama_client,
                label=f"Ollama ({env['OLLAMA_HOST']})",
            )
        except Exception as exc:
            return LLMResolution(
                status=LLMResolutionStatus.NONE,
                client=None,
                label="ollama detected but client failed",
                hint=(
                    "OLLAMA_HOST is set but instantiating "
                    "OllamaClient raised "
                    f"{type(exc).__name__}: {exc}. "
                    "Install the optional extra: "
                    "pip install 'valanistack[ollama]'."
                ),
            )

    return LLMResolution(
        status=LLMResolutionStatus.NONE,
        client=None,
        label="no LLM client detected — falling back to pre-rendered sample AAR",
        hint=(
            "Set ANTHROPIC_API_KEY (recommended), OPENAI_API_KEY, or "
            "OLLAMA_HOST to see a real AAR generated by an LLM. The "
            "sample below shows the exact shape of vstack's output."
        ),
    )


# --- Orchestrator ---------------------------------------------------------


def run_hello(
    *,
    force_offline: bool = False,
    env: dict[str, str] | None = None,
) -> HelloRunResult:
    """Run the hello flow.

    Args:
        force_offline: If True, skip LLM resolution and always return
            the pre-rendered sample AAR. Useful for CI smoke tests and
            for users who explicitly want to see the canned output.
        env: Process environment to inspect. Defaults to ``os.environ``.
            Tests inject a fake env.

    Returns:
        A ``HelloRunResult`` containing the trace, the rendered AAR
        markdown, and metadata about which LLM (if any) was used.
    """

    notes: list[str] = []

    if force_offline:
        resolution = LLMResolution(
            status=LLMResolutionStatus.NONE,
            client=None,
            label="offline mode (--offline) — using pre-rendered sample AAR",
            hint=None,
        )
        notes.append("Offline mode requested — skipped LLM resolution.")
        return HelloRunResult(
            resolution=resolution,
            trace=SAMPLE_TRACE,
            aar_markdown=SAMPLE_AAR_MARKDOWN,
            used_real_llm=False,
            elapsed_seconds=None,
            notes=notes,
        )

    resolution = resolve_llm_client(env=env)

    if resolution.client is None:
        return HelloRunResult(
            resolution=resolution,
            trace=SAMPLE_TRACE,
            aar_markdown=SAMPLE_AAR_MARKDOWN,
            used_real_llm=False,
            elapsed_seconds=None,
            notes=notes,
        )

    import time

    from vstack.aar import AARGenerator

    started = time.monotonic()
    try:
        generator = AARGenerator(llm_client=resolution.client)
        aar: AAR = generator.generate(SAMPLE_TRACE)
        markdown = aar.to_markdown()
        elapsed = time.monotonic() - started
        return HelloRunResult(
            resolution=resolution,
            trace=SAMPLE_TRACE,
            aar_markdown=markdown,
            used_real_llm=True,
            elapsed_seconds=elapsed,
            notes=notes,
        )
    except Exception as exc:
        notes.append(
            "LLM call failed — falling back to the pre-rendered "
            f"sample AAR. Underlying error: {type(exc).__name__}: {exc}."
        )
        return HelloRunResult(
            resolution=LLMResolution(
                status=LLMResolutionStatus.NONE,
                client=None,
                label=f"{resolution.label} (failed — fell back)",
                hint=(
                    "Check your API key, billing, and network. Run "
                    "`vstack-doctor` for a full diagnostic."
                ),
            ),
            trace=SAMPLE_TRACE,
            aar_markdown=SAMPLE_AAR_MARKDOWN,
            used_real_llm=False,
            elapsed_seconds=None,
            notes=notes,
        )
