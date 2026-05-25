"""``vstack.hello`` — first-run smoke test that proves the install works
end-to-end by running the After-Action Review pattern against a canned
synthetic agent trace.

Run as a CLI:

    vstack-hello

If an LLM API key is set in the environment (``ANTHROPIC_API_KEY``,
``OPENAI_API_KEY``, or ``OLLAMA_HOST``), the command resolves a real
client and runs an actual AAR. Otherwise it falls back to a
pre-rendered sample so users always get a complete picture of what
vstack produces.

The module is intentionally small and dependency-light: it leans only
on ``vstack.aar`` (already a hard dependency of the library) and the
standard library.
"""

from __future__ import annotations

from ._hello import (
    LLMResolution,
    LLMResolutionStatus,
    SAMPLE_AAR_MARKDOWN,
    SAMPLE_TRACE,
    HelloRunResult,
    resolve_llm_client,
    run_hello,
)

__all__ = [
    "LLMResolution",
    "LLMResolutionStatus",
    "SAMPLE_AAR_MARKDOWN",
    "SAMPLE_TRACE",
    "HelloRunResult",
    "resolve_llm_client",
    "run_hello",
]
