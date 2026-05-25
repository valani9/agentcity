# Browser dev tooling (`vstack.browser`)

Wraps the upstream `chrome-devtools-mcp` server so vstack can scrape agent traces from web observability dashboards, screenshot detection reports, and drive agents in the browser for evaluation.

## Install

```bash
pip install 'valanistack[browser]'
npm install -g chrome-devtools-mcp     # or rely on `npx` (the default)
```

Chrome / Chromium must be installed on the machine. The MCP server defaults to `npx chrome-devtools-mcp@latest`; override with `VSTACK_DEVTOOLS_MCP_COMMAND="..."` if you need a different binary path.

## Recognised dashboards

`vstack-browser` ships first-class scrape recipes for:

- **LangSmith** (`smith.langchain.com`)
- **Arize Phoenix** (`app.phoenix.arize.com`, `phoenix.arize.com`)
- **Helicone** (`us.helicone.ai`)
- **Langfuse** (`app.langfuse.com`)

For unrecognised URLs, the harness falls back to a "largest XHR JSON response with status < 400" heuristic and returns the most-likely candidate.

## CLI

```bash
# Scrape a trace from any dashboard URL:
vstack-browser scrape "https://smith.langchain.com/o/foo/projects/bar/r/<id>"

# Take a full-page screenshot:
vstack-browser screenshot "https://example.com" --out shot.png

# List every upstream chrome-devtools-mcp tool:
vstack-browser tools
```

The `scrape` command outputs JSON with the parsed trace payload + a suggested vstack pattern target (e.g. `"aar"` or `"lencioni"` based on payload shape).

## Programmatic

```python
import asyncio
from vstack.browser import open_session, scrape_trace, screenshot_url

async def main():
    async with open_session() as session:
        scraped = await scrape_trace(
            "https://smith.langchain.com/o/.../r/<id>",
            session=session,
        )
        print(scraped.vendor, scraped.suggested_pattern)
        print(scraped.raw_payload)

asyncio.run(main())
```

## Use cases

- Pull a real production trace from LangSmith → feed into `vstack_aar` (the `/vstack-post-incident` chain).
- Screenshot a detection report for incident channels.
- Drive a live agent UI as a black-box for evaluation.
