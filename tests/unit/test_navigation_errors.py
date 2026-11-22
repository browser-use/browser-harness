import asyncio
import json

import pytest

from browser_harness import helpers


@pytest.mark.parametrize("error", ["net::ERR_NAME_NOT_RESOLVED", "net::ERR_CONNECTION_REFUSED", "net::ERR_ABORTED", "private URL https://secret.test/?token=secret"])
def test_navigation_errors_raise_without_exposing_url(monkeypatch, error):
    monkeypatch.setattr(helpers, "cdp", lambda *args, **kwargs: {"errorText": error, "frameId": "frame"})
    with pytest.raises(RuntimeError, match="Navigation failed") as exc:
        helpers.goto_url("https://user:secret@example.test/?token=secret")
    assert "secret" not in str(exc.value)
    if error.startswith("net::ERR_"):
        assert error in str(exc.value)


@pytest.mark.parametrize("result", [{"frameId": "f", "loaderId": "l"}, {"frameId": "f"}, {"frameId": "f", "isDownload": True, "errorText": "net::ERR_ABORTED"}])
def test_success_same_document_and_download_keep_raw_shape(monkeypatch, result):
    monkeypatch.delenv("BH_DOMAIN_SKILLS", raising=False)
    monkeypatch.setattr(helpers, "cdp", lambda *args, **kwargs: result)
    assert helpers.goto_url("https://example.test/#section") is result


def test_new_tab_does_not_repeat_failed_navigation(monkeypatch):
    calls = []
    monkeypatch.setattr(helpers, "current_tab", lambda: {"targetId": "blank", "url": "about:blank"})
    def cdp(method, **kwargs):
        calls.append(method)
        return {"errorText": "net::ERR_CONNECTION_REFUSED"}
    monkeypatch.setattr(helpers, "cdp", cdp)
    with pytest.raises(RuntimeError, match="ERR_CONNECTION_REFUSED"):
        helpers.new_tab("http://example.test")
    assert calls == ["Page.navigate"]


def test_mcp_navigation_failure_is_a_tool_error_and_download_is_success(monkeypatch):
    pytest.importorskip("mcp")
    import mcp_server
    from mcp_types import CallToolRequestParams
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    result = {"errorText": "net::ERR_ABORTED"}
    monkeypatch.setattr(helpers, "cdp", lambda *args, **kwargs: result)
    params = CallToolRequestParams(name="browser_goto", arguments={"url": "https://example.test/file"})
    failed = asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))
    assert failed.is_error is True
    result["isDownload"] = True
    success = asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))
    assert success.is_error is False
    assert json.loads(success.content[0].text) == result
