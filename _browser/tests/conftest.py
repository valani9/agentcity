"""Pytest configuration for the vstack browser test suite.

The browser module wraps an external Chrome subprocess via the
upstream chrome-devtools-mcp server. None of that is reachable in
CI, so every test in this dir mocks at the
``vstack.browser._client.open_session`` boundary or below.
"""
