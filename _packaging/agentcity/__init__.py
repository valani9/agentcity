"""AgentCity: organizational behavior, practiced on AI agents.

A library of 34 diagnostic patterns drawn from organizational behavior,
social psychology, and group dynamics — each one rewritten for the
domain of AI agents rather than human teams. Patterns ship as
independent sub-packages under the `agentcity.*` namespace and share a
common LLM-client + retry + JSON-parsing core in `agentcity.aar`.

Public API stability
--------------------
Every sub-package exposes its public surface via its own ``__all__``.
Symbols not listed in ``__all__`` are private and may change in any
release. Symbols in ``__all__`` follow this stability promise:

  - ``0.x.y`` releases: breaking changes permitted in ``minor`` bumps
    (``0.0.x`` → ``0.1.0``). Patch bumps (``0.x.y`` → ``0.x.(y+1)``)
    are non-breaking.
  - ``1.x.y`` and later: SemVer. Breaking changes only on ``major``.
    Deprecations are warned for one minor release before removal.

Quick start
-----------

    from agentcity.aar import AARGenerator, AgentTrace, TraceStep
    from agentcity.aar.clients import AnthropicClient

    generator = AARGenerator(llm_client=AnthropicClient())
    aar = generator.run(my_trace)
    print(aar.to_markdown())

See `PATTERNS.md` for the full pattern index and per-pattern import paths.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
