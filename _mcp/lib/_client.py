"""LLM client resolution for the MCP server.

The MCP server runs as a stdio subprocess of the user's MCP client
(Claude Desktop, Cursor, Cline, etc.). It needs an LLM client of its
own to drive the vstack analyzer pipeline.

Three resolution strategies are supported, in priority order:

1. **Explicit ``VSTACK_MCP_LLM=stub``** — return a no-op client that
   echoes canned responses. Used by the smoke test.

2. **``VSTACK_MCP_LLM=anthropic|openai|ollama``** — construct the
   corresponding ``vstack.aar`` client. The required API key is read
   from the standard environment variable for that provider.

3. **Auto-detect** — if no explicit choice is set, prefer Anthropic
   if ``ANTHROPIC_API_KEY`` is present, else OpenAI if
   ``OPENAI_API_KEY`` is present, else Ollama if ``OLLAMA_HOST`` is
   set, else raise a structured error directing the user how to
   configure one.

MCP sampling (where the host LLM provides completions via the protocol
itself) is a natural future extension; the resolver returns the env-
var-resolved client today and can be swapped in place when more clients
ship sampling support.
"""

from __future__ import annotations

import os
from typing import Any, Protocol


class LLMCompleteClient(Protocol):
    """Duck-typed shape every vstack analyzer accepts."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class LLMResolutionError(RuntimeError):
    """Raised when no LLM client can be constructed.

    The error message is structured for an MCP client to surface back
    to the user; it lists every env var the resolver consulted and the
    install hint for each supported provider.
    """


def resolve_llm_client(
    *,
    preference: str | None = None,
    env: dict[str, str] | None = None,
) -> LLMCompleteClient:
    """Return an LLM client suitable for the analyzer pipeline.

    Parameters
    ----------
    preference:
        Explicit override; one of ``"stub"``, ``"anthropic"``,
        ``"openai"``, ``"ollama"``. Falls back to the
        ``VSTACK_MCP_LLM`` env var if unset, then auto-detection.
    env:
        Environment dict (defaults to ``os.environ``). Made injectable
        so tests can exercise the resolution table without mutating
        the global environment.
    """
    env = env if env is not None else dict(os.environ)
    pref = (preference or env.get("VSTACK_MCP_LLM") or "").strip().lower()

    # Stub: deterministic in-memory client for tests + zero-API-key dev loops.
    if pref == "stub":
        from vstack.aar import StubClient

        return StubClient([])  # canned responses populated by callers

    # Explicit provider preference.
    if pref == "anthropic":
        return _make_anthropic(env, explicit=True)
    if pref == "openai":
        return _make_openai(env, explicit=True)
    if pref == "ollama":
        return _make_ollama(env, explicit=True)

    # Auto-detect order: Anthropic > OpenAI > Ollama.
    if env.get("ANTHROPIC_API_KEY"):
        return _make_anthropic(env, explicit=False)
    if env.get("OPENAI_API_KEY"):
        return _make_openai(env, explicit=False)
    if env.get("OLLAMA_HOST") or env.get("OLLAMA_BASE_URL"):
        return _make_ollama(env, explicit=False)

    raise LLMResolutionError(
        "vstack-mcp cannot resolve an LLM client. Set one of:\n"
        "  - ANTHROPIC_API_KEY (recommended; pip install 'valanistack[anthropic]')\n"
        "  - OPENAI_API_KEY (pip install 'valanistack[openai]')\n"
        "  - OLLAMA_HOST or OLLAMA_BASE_URL (pip install 'valanistack[ollama]')\n"
        "Or set VSTACK_MCP_LLM=stub for a no-op test client."
    )


def _make_anthropic(env: dict[str, str], *, explicit: bool) -> LLMCompleteClient:
    try:
        from vstack.aar import AnthropicClient
    except ImportError as e:
        raise LLMResolutionError(
            "Anthropic client requested but the 'anthropic' extra is not "
            "installed. Run: pip install 'valanistack[anthropic]'"
        ) from e
    api_key = env.get("ANTHROPIC_API_KEY")
    if not api_key:
        msg = "ANTHROPIC_API_KEY is not set."
        if explicit:
            msg += " VSTACK_MCP_LLM=anthropic was requested explicitly."
        raise LLMResolutionError(msg)
    return AnthropicClient(api_key=api_key)


def _make_openai(env: dict[str, str], *, explicit: bool) -> LLMCompleteClient:
    try:
        from vstack.aar import OpenAIClient
    except ImportError as e:
        raise LLMResolutionError(
            "OpenAI client requested but the 'openai' extra is not "
            "installed. Run: pip install 'valanistack[openai]'"
        ) from e
    api_key = env.get("OPENAI_API_KEY")
    if not api_key:
        msg = "OPENAI_API_KEY is not set."
        if explicit:
            msg += " VSTACK_MCP_LLM=openai was requested explicitly."
        raise LLMResolutionError(msg)
    return OpenAIClient(api_key=api_key)


def _make_ollama(env: dict[str, str], *, explicit: bool) -> LLMCompleteClient:
    try:
        from vstack.aar import OllamaClient
    except ImportError as e:
        raise LLMResolutionError(
            "Ollama client requested but the 'ollama' extra is not "
            "installed. Run: pip install 'valanistack[ollama]'"
        ) from e
    kwargs: dict[str, Any] = {}
    host = env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST")
    if host:
        kwargs["base_url"] = host
    return OllamaClient(**kwargs)


def default_model_for(client: LLMCompleteClient) -> str:
    """Pick a sensible default model string given a client.

    The vstack analyzers accept any model string; this just gives the
    server a defaulted value for tool calls that omit ``model``.
    """
    cls_name = type(client).__name__
    if "Anthropic" in cls_name:
        return "claude-sonnet-4-6"
    if "OpenAI" in cls_name:
        return "gpt-4o"
    if "Ollama" in cls_name:
        return "llama3.1:8b"
    return "stub-model"
