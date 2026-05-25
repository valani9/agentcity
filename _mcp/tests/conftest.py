"""Pytest configuration for the vstack MCP server test suite.

Tests import from the installed `vstack` package, which means the
``_mcp/lib/`` source folder is shipped under ``vstack/mcp/`` via the
hatchling ``force-include`` mapping in pyproject.toml. Install with
``pip install -e .`` from the repo root before running tests; if you
edit the MCP source you may need to re-run ``pip install -e .`` to
refresh the force-included copy under site-packages.
"""
