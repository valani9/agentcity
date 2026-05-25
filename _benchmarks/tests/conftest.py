"""Pytest configuration for the vstack benchmarks test suite.

Real LLM spend is forbidden inside the suite. Every test passes a
:class:`vstack.aar.StubClient` (or no LLM at all -- the harness
short-circuits via the validation-error path then). The point of
the tests is that the harness scaffolding works; producing real
benchmark numbers is a separate operator concern.
"""
