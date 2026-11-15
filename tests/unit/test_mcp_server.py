import asyncio

import pytest

pytest.importorskip("mcp")

from mcp_types import CallToolRequestParams

import mcp_server


def _call_tool(name: str, arguments: dict | None = None):
    params = CallToolRequestParams(name=name, arguments=arguments or {})
    return asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))


@pytest.fixture(autouse=True)
def no_captcha_note(monkeypatch):
    """No daemon in these tests: a real captcha_note() would ask whichever daemon this machine runs."""
    monkeypatch.setattr(mcp_server, "captcha_note", lambda: "")


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


NOTE = "[Captcha solver running (cloudflare) on https://a.test/ for 3 s. Wait with solve_captcha(); do not reload, navigate or switch tabs.]"


def test_every_result_ends_with_the_captcha_note(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    monkeypatch.setattr(mcp_server, "captcha_note", lambda: NOTE)
    monkeypatch.setattr(mcp_server, "page_info", lambda: {"url": "https://a.test/"})

    result = _call_tool("browser_page_info")

    assert result.is_error is False
    assert result.content[0].text == '{"url": "https://a.test/"}\n' + NOTE


def test_a_failed_tool_still_shows_the_captcha_note(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    monkeypatch.setattr(mcp_server, "captcha_note", lambda: NOTE)

    def fail():
        raise RuntimeError("page gone")

    monkeypatch.setattr(mcp_server, "page_info", fail)

    result = _call_tool("browser_page_info")

    assert result.is_error is True
    assert result.content[0].text.endswith("page gone\n" + NOTE)


def test_solve_captcha_tool_waits_for_the_solver(monkeypatch):
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    calls = []

    def solve(start_timeout, timeout):
        calls.append((start_timeout, timeout))
        return {"solved": True, "detail": "solved", "seconds": 4.2, "vendor": "recaptcha"}

    monkeypatch.setattr(mcp_server, "solve_captcha", solve)

    result = _call_tool("browser_solve_captcha", {"timeout": 30})

    assert result.is_error is False
    assert result.content[0].text == '{"solved": true, "detail": "solved", "seconds": 4.2, "vendor": "recaptcha"}'
    assert calls == [(20.0, 30.0)]
