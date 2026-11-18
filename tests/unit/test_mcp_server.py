import asyncio
import json
import urllib.error

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


class _Sent:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)

        class Response:
            def close(self):
                pass

        return Response()


def _feedback(monkeypatch, tmp_path, *, key=None, telemetry_on=True):
    monkeypatch.setattr(mcp_server, "_feedback_sent", 0)
    monkeypatch.setenv("BH_AUTH_PATH", str(tmp_path / "auth.json"))
    monkeypatch.delenv("BROWSER_USE_CLOUD_API_URL", raising=False)
    if key:
        monkeypatch.setenv("BROWSER_USE_API_KEY", key)
    else:
        monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setattr(mcp_server.telemetry, "is_enabled", lambda: telemetry_on)
    sent = _Sent()
    monkeypatch.setattr(mcp_server.urllib.request, "urlopen", sent)
    return sent


def _send(message="kind: integration_report\nBuilt: x", category="other"):
    params = CallToolRequestParams(name="browser_feedback", arguments={"message": message, "category": category})
    result = asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))
    return result, result.content[0].text


def test_feedback_posts_only_the_message_with_the_api_key_even_with_telemetry_off(monkeypatch, tmp_path):
    sent = _feedback(monkeypatch, tmp_path, key="bu_test_key", telemetry_on=False)

    result, text = _send()

    assert result.is_error is False
    assert text.startswith("Reported to the Browser Use team")
    [request] = sent.requests
    assert request.full_url == "https://api.browser-use.com/api/v4/feedback"
    assert request.get_method() == "POST"
    assert request.get_header("X-browser-use-api-key") == "bu_test_key"
    assert json.loads(request.data) == {"message": "kind: integration_report\nBuilt: x\ncategory: other"}


def test_feedback_without_a_key_sends_nothing_and_points_at_the_cli(monkeypatch, tmp_path):
    sent = _feedback(monkeypatch, tmp_path)

    _, text = _send(message="it's broken")

    assert sent.requests == []
    assert "uvx browser-use feedback --category other 'it'\"'\"'s broken'" in text


def test_feedback_without_a_key_respects_telemetry_opt_out(monkeypatch, tmp_path):
    sent = _feedback(monkeypatch, tmp_path, telemetry_on=False)

    _, text = _send()

    assert sent.requests == []
    assert "nothing was sent" in text and "uvx" not in text


def test_feedback_failed_send_falls_back_and_does_not_count(monkeypatch, tmp_path):
    _feedback(monkeypatch, tmp_path, key="bu_test_key")

    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(mcp_server.urllib.request, "urlopen", fail)

    result, text = _send()

    assert result.is_error is False
    assert text.startswith("Sending failed (429): nothing was sent") and "uvx browser-use feedback" in text
    assert mcp_server._feedback_sent == 0


def test_feedback_caps_sends_per_session_and_message_length(monkeypatch, tmp_path):
    sent = _feedback(monkeypatch, tmp_path, key="bu_test_key")

    texts = [_send(message="x" * 5000)[1] for _ in range(4)]

    assert len(sent.requests) == 3
    assert len(json.loads(sent.requests[0].data)["message"]) == 2000 + len("\ncategory: other")
    assert texts[-1] == "Already reported 3 times this session: nothing sent."
