"""``vstack-browser`` CLI -- scrape traces / take screenshots / list tools.

Three subcommands cover the typical user flows:

* ``vstack-browser scrape <url>`` -- print the structured trace JSON
  the dashboard returned, with a suggested vstack pattern target.
* ``vstack-browser screenshot <url> --out file.png`` -- save a
  screenshot of any URL.
* ``vstack-browser tools`` -- list every chrome-devtools-mcp tool
  the upstream server publishes. Useful for power-user invocations.

Most users won't run this CLI directly -- the vstack skills call the
programmatic API. But it's the cleanest way to verify the upstream
chrome-devtools-mcp install is working.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Sequence

from ._client import BrowserToolError, open_session
from ._scrape import scrape_trace, screenshot_url


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-browser",
        description=(
            "Browser-driven trace ingestion + screenshotting via "
            "chrome-devtools-mcp. Requires Node.js + Chrome installed."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_scrape = sub.add_parser(
        "scrape",
        help=(
            "Navigate to an agent-observability dashboard URL and dump the structured trace JSON."
        ),
    )
    p_scrape.add_argument("url")
    p_scrape.add_argument(
        "--wait-for",
        default=None,
        help="Optional CSS selector to wait for after navigation.",
    )
    p_scrape.add_argument("--timeout", type=float, default=30.0)

    p_screen = sub.add_parser("screenshot", help="Take a full-page screenshot.")
    p_screen.add_argument("url")
    p_screen.add_argument("--out", required=True, help="Output file path for the PNG bytes.")
    p_screen.add_argument("--wait-for", default=None)
    p_screen.add_argument(
        "--viewport",
        action="store_true",
        help="Capture viewport only (default is full-page).",
    )

    sub.add_parser("tools", help="List every upstream chrome-devtools-mcp tool name.")

    args = parser.parse_args(argv)
    cmd = args.command
    if cmd is None:
        parser.print_help()
        return 0

    try:
        if cmd == "scrape":
            return asyncio.run(_run_scrape(args.url, args.wait_for, args.timeout))
        if cmd == "screenshot":
            return asyncio.run(
                _run_screenshot(
                    args.url,
                    args.out,
                    args.wait_for,
                    full_page=not args.viewport,
                )
            )
        if cmd == "tools":
            return asyncio.run(_run_tools())
    except BrowserToolError as e:
        print(f"vstack-browser: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(
            f"vstack-browser: {e}. Install Node.js + npx and ensure "
            "chrome-devtools-mcp is reachable (default: 'npx chrome-devtools-mcp@latest').",
            file=sys.stderr,
        )
        return 2
    parser.error(f"Unknown command: {cmd}")
    return 2


async def _run_scrape(url: str, wait_for: str | None, timeout: float) -> int:
    async with open_session() as session:
        scraped = await scrape_trace(
            url, session=session, wait_for_selector=wait_for, timeout_seconds=timeout
        )
    body = {
        "url": scraped.url,
        "vendor": scraped.vendor,
        "suggested_pattern": scraped.suggested_pattern,
        "captured_network_requests_summary": scraped.captured_network_requests[:10],
        "raw_payload": scraped.raw_payload,
    }
    print(json.dumps(body, indent=2, default=str))
    return 0


async def _run_screenshot(url: str, out_path: str, wait_for: str | None, *, full_page: bool) -> int:
    async with open_session() as session:
        png = await screenshot_url(
            url, session=session, wait_for_selector=wait_for, full_page=full_page
        )
    with open(out_path, "wb") as f:
        f.write(png)
    print(f"Wrote {len(png)} bytes to {out_path}")
    return 0


async def _run_tools() -> int:
    async with open_session() as session:
        tools = await session.list_tools()
    width = max((len(t.name) for t in tools), default=0)
    for tool in tools:
        desc = (getattr(tool, "description", "") or "").splitlines()[0][:120]
        print(f"  {tool.name:<{width}}  {desc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
