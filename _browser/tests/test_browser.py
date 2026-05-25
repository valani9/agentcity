"""Tests for ``vstack.browser``.

Every test mocks the upstream chrome-devtools-mcp connection -- we
verify the wrapping logic (request filtering, payload parsing, image
decoding, dashboard recipes) without actually launching Chrome.

Async test bodies are written as plain coroutines and driven by the
``@_async`` helper so we don't depend on pytest-asyncio.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import functools
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

import pytest

import vstack.browser as browser
from vstack.browser._client import (
    DEFAULT_DEVTOOLS_COMMAND,
    BrowserSession,
    BrowserToolError,
    _resolve_command,
    _summarize_content,
)
from vstack.browser._scrape import (
    KNOWN_DASHBOARDS,
    _decode_image,
    _extract_requests,
    _guess_pattern_for,
    _pick_trace_request,
    _result_structured,
    scrape_trace,
    screenshot_url,
)


# ----------------------------------------------------------------------
# Async helper -- avoids depending on pytest-asyncio.
# ----------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _async(fn: F) -> Callable[..., None]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        asyncio.run(fn(*args, **kwargs))

    return wrapper  # type: ignore[return-value]


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


@dataclass
class FakeTextContent:
    text: str
    type: str = "text"


@dataclass
class FakeImageContent:
    data: str  # base64
    mimeType: str = "image/png"
    type: str = "image"


@dataclass
class FakeCallToolResult:
    content: list[Any] = field(default_factory=list)
    structuredContent: Any = None
    isError: bool = False


@dataclass
class FakeTool:
    name: str
    description: str = ""


@dataclass
class FakeListToolsResult:
    tools: list[FakeTool] = field(default_factory=list)


class FakeSession:
    """Stand-in for ``mcp.ClientSession``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses: dict[str, FakeCallToolResult] = {}
        self.tools_list = FakeListToolsResult(
            tools=[
                FakeTool("navigate_page", "Navigate the browser"),
                FakeTool("list_network_requests", "List recent network requests"),
                FakeTool("get_network_request", "Fetch one network request body"),
                FakeTool("take_screenshot", "Take a screenshot"),
                FakeTool("wait_for", "Wait for a CSS selector"),
                FakeTool("fill", "Fill a form field"),
                FakeTool("click", "Click an element"),
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> FakeCallToolResult:
        self.calls.append((name, arguments))
        return self.responses.get(name, FakeCallToolResult())

    async def list_tools(self) -> FakeListToolsResult:
        return self.tools_list


# ----------------------------------------------------------------------
# _resolve_command
# ----------------------------------------------------------------------


def test_resolve_command_explicit_wins() -> None:
    cmd = _resolve_command(("my", "cmd"), {})
    assert cmd == ("my", "cmd")


def test_resolve_command_env_var() -> None:
    cmd = _resolve_command(None, {"VSTACK_DEVTOOLS_MCP_COMMAND": "chrome-devtools-mcp --headless"})
    assert cmd == ("chrome-devtools-mcp", "--headless")


def test_resolve_command_default() -> None:
    assert _resolve_command(None, {}) == DEFAULT_DEVTOOLS_COMMAND


def test_resolve_command_empty_env_var() -> None:
    assert _resolve_command(None, {"VSTACK_DEVTOOLS_MCP_COMMAND": "  "}) == DEFAULT_DEVTOOLS_COMMAND


# ----------------------------------------------------------------------
# BrowserSession
# ----------------------------------------------------------------------


@_async
async def test_session_call_tool_returns_result() -> None:
    fake = FakeSession()
    fake.responses["navigate_page"] = FakeCallToolResult(content=[FakeTextContent("ok")])
    session = BrowserSession(session=fake, tool_names=("navigate_page",))
    result = await session.call_tool("navigate_page", {"url": "https://example.com"})
    assert fake.calls == [("navigate_page", {"url": "https://example.com"})]
    assert result.content[0].text == "ok"


@_async
async def test_session_call_tool_raises_on_iserror() -> None:
    fake = FakeSession()
    fake.responses["navigate_page"] = FakeCallToolResult(
        content=[FakeTextContent("upstream said no")], isError=True
    )
    session = BrowserSession(session=fake)
    with pytest.raises(BrowserToolError) as exc:
        await session.call_tool("navigate_page", {"url": "x"})
    assert "upstream said no" in str(exc.value)


@_async
async def test_session_list_tools_unwraps() -> None:
    fake = FakeSession()
    session = BrowserSession(session=fake)
    tools = await session.list_tools()
    assert [t.name for t in tools] == [
        "navigate_page",
        "list_network_requests",
        "get_network_request",
        "take_screenshot",
        "wait_for",
        "fill",
        "click",
    ]


def test_summarize_content_pulls_first_text() -> None:
    result = FakeCallToolResult(
        content=[FakeTextContent("first line\nsecond"), FakeTextContent("third")],
        isError=True,
    )
    summary = _summarize_content(result)
    assert "first line" in summary


# ----------------------------------------------------------------------
# _scrape internals
# ----------------------------------------------------------------------


def test_extract_requests_from_structured() -> None:
    result = FakeCallToolResult(
        structuredContent={
            "requests": [
                {
                    "requestId": "r1",
                    "url": "https://x/api/foo",
                    "status": 200,
                    "size": 100,
                    "type": "xhr",
                },
                {
                    "requestId": "r2",
                    "url": "https://x/static/icon.png",
                    "status": 200,
                    "type": "Image",
                },
            ]
        }
    )
    rows = _extract_requests(result)
    assert len(rows) == 2
    assert rows[0]["id"] == "r1"


def test_extract_requests_from_text_json() -> None:
    payload = json.dumps({"requests": [{"requestId": "r1", "url": "https://x/api", "status": 200}]})
    result = FakeCallToolResult(content=[FakeTextContent(payload)])
    rows = _extract_requests(result)
    assert rows[0]["url"] == "https://x/api"


def test_pick_trace_request_honors_filter() -> None:
    captured = [
        {"id": "a", "url": "https://x/static/icon.png", "status": 200, "size": 50},
        {"id": "b", "url": "https://x/api/v1/runs/abc", "status": 200, "size": 500},
        {"id": "c", "url": "https://x/api/v1/runs/xyz", "status": 500, "size": 1500},
    ]
    picked = _pick_trace_request(captured, "/api/v1/runs/")
    assert picked["id"] == "b"  # status < 400 wins over c


def test_pick_trace_request_largest_xhr_fallback() -> None:
    captured = [
        {"id": "a", "url": "https://x/static/icon.png", "status": 200, "size": 50, "type": "Image"},
        {"id": "b", "url": "https://x/api/foo", "status": 200, "size": 500, "type": "xhr"},
        {"id": "c", "url": "https://x/api/bar", "status": 200, "size": 2000, "type": "fetch"},
    ]
    picked = _pick_trace_request(captured, None)
    assert picked["id"] == "c"


def test_pick_trace_request_handles_empty() -> None:
    assert _pick_trace_request([], None) is None
    assert _pick_trace_request([], "/api/x") is None


def test_guess_pattern_for_aar_shape() -> None:
    assert _guess_pattern_for({"goal": "x", "steps": [], "outcome": "y"}) == "aar"


def test_guess_pattern_for_lencioni_shape() -> None:
    assert _guess_pattern_for({"messages": [], "agents": []}) == "lencioni"


def test_guess_pattern_for_span_shape() -> None:
    assert _guess_pattern_for({"agents": [], "incoming_request_rate": 100.0}) == "span_of_control"


def test_guess_pattern_for_schein_shape() -> None:
    assert _guess_pattern_for({"observations": []}) == "schein_culture"


def test_guess_pattern_for_unknown() -> None:
    assert _guess_pattern_for({"random": "thing"}) is None
    assert _guess_pattern_for("not a dict") is None


def test_result_structured_prefers_structured_content() -> None:
    result = FakeCallToolResult(
        structuredContent={"foo": 1},
        content=[FakeTextContent('{"foo": 2}')],
    )
    assert _result_structured(result) == {"foo": 1}


def test_result_structured_falls_back_to_text_json() -> None:
    result = FakeCallToolResult(content=[FakeTextContent('{"foo": 2}')])
    assert _result_structured(result) == {"foo": 2}


def test_result_structured_handles_no_content() -> None:
    assert _result_structured(FakeCallToolResult()) is None


def test_decode_image_from_structured() -> None:
    payload = base64.b64encode(b"PNG bytes").decode()
    result = FakeCallToolResult(structuredContent={"data": payload})
    assert _decode_image(result) == b"PNG bytes"


def test_decode_image_from_image_content() -> None:
    payload = base64.b64encode(b"more PNG").decode()
    result = FakeCallToolResult(content=[FakeImageContent(data=payload)])
    assert _decode_image(result) == b"more PNG"


def test_decode_image_raises_when_empty() -> None:
    with pytest.raises(BrowserToolError):
        _decode_image(FakeCallToolResult())


def test_known_dashboards_cover_major_vendors() -> None:
    domains = list(KNOWN_DASHBOARDS)
    assert "smith.langchain.com" in domains
    assert "app.langfuse.com" in domains
    assert any("phoenix" in d for d in domains)
    assert any("helicone" in d for d in domains)


# ----------------------------------------------------------------------
# scrape_trace / screenshot_url end-to-end (with fake session)
# ----------------------------------------------------------------------


@_async
async def test_scrape_trace_langsmith_recipe() -> None:
    fake = FakeSession()
    fake.responses["list_network_requests"] = FakeCallToolResult(
        structuredContent={
            "requests": [
                {
                    "requestId": "r1",
                    "url": "https://smith.langchain.com/api/v1/runs/abc",
                    "status": 200,
                    "size": 1024,
                    "type": "xhr",
                }
            ]
        }
    )
    fake.responses["get_network_request"] = FakeCallToolResult(
        structuredContent={
            "body": json.dumps(
                {
                    "goal": "Test",
                    "steps": [{"type": "input", "content": "hi"}],
                    "outcome": "done",
                    "success": True,
                }
            )
        }
    )
    session = BrowserSession(session=fake)
    scraped = await scrape_trace(
        "https://smith.langchain.com/o/foo/projects/bar/r/abc",
        session=session,
    )
    assert scraped.vendor == "LangSmith"
    assert scraped.suggested_pattern == "aar"
    assert scraped.raw_payload["goal"] == "Test"
    # Recorded the navigate + list + get sequence.
    assert any(c[0] == "navigate_page" for c in fake.calls)
    assert any(c[0] == "list_network_requests" for c in fake.calls)
    assert any(c[0] == "get_network_request" for c in fake.calls)


@_async
async def test_scrape_trace_unknown_dashboard_uses_fallback() -> None:
    fake = FakeSession()
    fake.responses["list_network_requests"] = FakeCallToolResult(
        structuredContent={
            "requests": [
                {
                    "requestId": "r1",
                    "url": "https://example.com/api/data",
                    "status": 200,
                    "size": 5000,
                    "type": "xhr",
                }
            ]
        }
    )
    fake.responses["get_network_request"] = FakeCallToolResult(
        structuredContent={"body": '{"messages": [], "agents": []}'}
    )
    session = BrowserSession(session=fake)
    scraped = await scrape_trace("https://example.com/trace/123", session=session)
    assert scraped.vendor == "unknown"
    # Heuristic picked Lencioni from the payload shape.
    assert scraped.suggested_pattern == "lencioni"


@_async
async def test_scrape_trace_raises_when_no_candidate_request() -> None:
    fake = FakeSession()
    fake.responses["list_network_requests"] = FakeCallToolResult(structuredContent={"requests": []})
    session = BrowserSession(session=fake)
    with pytest.raises(BrowserToolError):
        await scrape_trace("https://example.com/trace/123", session=session)


@_async
async def test_screenshot_url_returns_decoded_png() -> None:
    fake = FakeSession()
    payload = base64.b64encode(b"PNG-OK").decode()
    fake.responses["take_screenshot"] = FakeCallToolResult(structuredContent={"data": payload})
    session = BrowserSession(session=fake)
    png = await screenshot_url("https://example.com", session=session)
    assert png == b"PNG-OK"


@_async
async def test_screenshot_url_with_wait_for_swallows_wait_error() -> None:
    """If the wait_for selector never fires, screenshot still proceeds."""
    fake = FakeSession()
    fake.responses["wait_for"] = FakeCallToolResult(
        content=[FakeTextContent("timeout")], isError=True
    )
    fake.responses["take_screenshot"] = FakeCallToolResult(
        structuredContent={"data": base64.b64encode(b"img").decode()}
    )
    session = BrowserSession(session=fake)
    png = await screenshot_url(
        "https://example.com",
        session=session,
        wait_for_selector="#never-appears",
    )
    assert png == b"img"


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_no_command_returns_0(capsys: pytest.CaptureFixture[str]) -> None:
    from vstack.browser.cli import main

    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "vstack-browser" in out


def test_cli_scrape_uses_open_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Drive vstack-browser scrape with a fully fake session manager."""
    from vstack.browser.cli import main

    fake = FakeSession()
    fake.responses["list_network_requests"] = FakeCallToolResult(
        structuredContent={
            "requests": [
                {
                    "requestId": "r1",
                    "url": "https://example.com/api",
                    "status": 200,
                    "size": 100,
                    "type": "xhr",
                }
            ]
        }
    )
    fake.responses["get_network_request"] = FakeCallToolResult(
        structuredContent={"body": '{"goal": "g", "steps": [], "outcome": "o", "success": true}'}
    )

    @contextlib.asynccontextmanager
    async def _fake_open(**_: Any):
        yield BrowserSession(session=fake)

    monkeypatch.setattr("vstack.browser.cli.open_session", _fake_open)

    rc = main(["scrape", "https://example.com/trace"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert body["url"] == "https://example.com/trace"
    assert body["raw_payload"]["goal"] == "g"


def test_cli_screenshot_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    from vstack.browser.cli import main

    fake = FakeSession()
    fake.responses["take_screenshot"] = FakeCallToolResult(
        structuredContent={"data": base64.b64encode(b"img-bytes").decode()}
    )

    @contextlib.asynccontextmanager
    async def _fake_open(**_: Any):
        yield BrowserSession(session=fake)

    monkeypatch.setattr("vstack.browser.cli.open_session", _fake_open)

    out_file = tmp_path / "shot.png"
    rc = main(["screenshot", "https://example.com", "--out", str(out_file)])
    assert rc == 0
    assert out_file.read_bytes() == b"img-bytes"


def test_cli_tools_lists_upstream(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vstack.browser.cli import main

    fake = FakeSession()

    @contextlib.asynccontextmanager
    async def _fake_open(**_: Any):
        yield BrowserSession(session=fake, tool_names=tuple(t.name for t in fake.tools_list.tools))

    monkeypatch.setattr("vstack.browser.cli.open_session", _fake_open)

    rc = main(["tools"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "navigate_page" in out
    assert "take_screenshot" in out


def test_module_exports() -> None:
    assert "open_session" in browser.__all__
    assert "ScrapedTrace" in browser.__all__
    assert "scrape_trace" in browser.__all__
    assert browser.__version__
