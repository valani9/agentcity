"""vstack.browser -- Chrome DevTools MCP integration for trace
ingestion from web-based agent observability dashboards.

Wraps the upstream ``chrome-devtools-mcp`` server so vstack can:

* Scrape an agent trace from a web dashboard (LangSmith, Phoenix,
  Arize, Helicone) without screen-scraping the rendered HTML --
  navigate, inspect the network requests, dump the structured trace
  payload, and feed it directly into a pattern's input model.
* Screenshot a vstack detection report for sharing in incident
  channels.
* Drive an agent in the browser end-to-end as a black-box for
  evaluation (open a live agent UI, send canned prompts, collect
  the displayed response).

The module is import-gated -- ``chrome-devtools-mcp`` is heavy and
runs Chrome under the hood -- so users who only want the rest of
vstack don't pay the cost. Install via the ``[browser]`` extra::

    pip install valanistack[browser]

Programmatic surface
--------------------

* :class:`BrowserSession` -- holds an :class:`AsyncMcpClient`
  connection to a running ``chrome-devtools-mcp`` server.
* :func:`open_session` -- async context-manager that launches the
  upstream MCP server as a subprocess and returns a session.
* :class:`ScrapedTrace` -- a structured representation of a trace
  the browser scraped from a dashboard (raw payload + URL + the
  vstack pattern target it was scraped for).
* :func:`scrape_trace` / :func:`screenshot_url` / :func:`fill_form`
  -- convenience helpers that wrap the most common DevTools-MCP
  request/response pairs.

CLI
---

::

    vstack-browser scrape <url>                  # JSON trace -> stdout
    vstack-browser screenshot <url> --out file
    vstack-browser tools                         # list upstream MCP tools
"""

from ._client import (
    BrowserSession,
    BrowserToolError,
    DEFAULT_DEVTOOLS_COMMAND,
    open_session,
)
from ._scrape import (
    KNOWN_DASHBOARDS,
    ScrapedTrace,
    fill_form,
    scrape_trace,
    screenshot_url,
)

__all__ = [
    "BrowserSession",
    "BrowserToolError",
    "DEFAULT_DEVTOOLS_COMMAND",
    "open_session",
    "KNOWN_DASHBOARDS",
    "ScrapedTrace",
    "fill_form",
    "scrape_trace",
    "screenshot_url",
]

__version__ = "0.5.0"
