import asyncio

import pytest

pytest.importorskip("mcp")

from mcp_types import CallToolRequestParams

import mcp_server


def _call_tool(name: str):
    params = CallToolRequestParams(name=name, arguments={})
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
