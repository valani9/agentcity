"""Pytest configuration for the vstack memory test suite.

Tests import from the installed ``vstack`` package, which means the
``_memory/lib/`` source folder is shipped under ``vstack/memory/`` via
the hatchling ``force-include`` mapping in pyproject.toml. Install
with ``pip install -e .`` from the repo root before running tests;
if you edit the memory source you may need to re-run
``pip install -e .`` to refresh the force-included copy under
site-packages.
"""
