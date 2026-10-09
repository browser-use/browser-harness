import asyncio

import pytest

pytest.importorskip("mcp")

from mcp_types import CallToolRequestParams

import mcp_server


def _call_tool(name: str, arguments=None):
    params = CallToolRequestParams(name=name, arguments=arguments or {})
    return asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))


def test_helper_failure_uses_mcp_tool_error(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)

    def fail():
        raise RuntimeError("sentinel browser failure")

    monkeypatch.setattr(mcp_server, "page_info", fail)

    result = _call_tool("browser_page_info")

    assert result.is_error is True
    assert result.content[0].text == "Error executing tool browser_page_info: sentinel browser failure"


def test_helper_success_remains_a_normal_tool_result(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    monkeypatch.setattr(mcp_server, "page_info", lambda: {"url": "https://example.com"})

    result = _call_tool("browser_page_info")

    assert result.is_error is False
    assert result.content[0].text == '{"url": "https://example.com"}'


def test_browser_new_tab_forwards_default_window_option(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    calls = []

    def fake_new_tab(url, new_window=False):
        calls.append((url, new_window))
        return "target-window"

    monkeypatch.setattr(mcp_server, "new_tab", fake_new_tab)

    result = _call_tool("browser_new_tab", {"url": "https://example.com"})

    assert result.is_error is False
    assert result.content[0].text == '{"targetId": "target-window"}'
    assert calls == [("https://example.com", False)]


def test_browser_new_tab_forwards_background_window_option(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    calls = []

    def fake_new_tab(url, new_window=False):
        calls.append((url, new_window))
        return "target-window"

    monkeypatch.setattr(mcp_server, "new_tab", fake_new_tab)

    result = _call_tool(
        "browser_new_tab",
        {"url": "https://example.com", "new_window": True},
    )

    assert result.is_error is False
    assert result.content[0].text == '{"targetId": "target-window"}'
    assert calls == [("https://example.com", True)]
