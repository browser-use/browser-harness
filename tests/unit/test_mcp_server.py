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


@pytest.fixture
def reports(monkeypatch, tmp_path):
    from browser_harness import report, telemetry

    for name in ("BH_TELEMETRY", "BROWSER_HARNESS_TELEMETRY", "ANONYMIZED_TELEMETRY", "BROWSER_USE_OFFLINE", "BROWSER_USE_ZDR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(mcp_server, "_reports_sent", {"run": 0, "feedback": 0})
    events = []
    monkeypatch.setattr(telemetry, "_send_detached", lambda payload, host=None: events.append(payload))
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: pytest.fail("reports need no browser"))
    return events


def _call(name: str, arguments: dict):
    params = CallToolRequestParams(name=name, arguments=arguments)
    return asyncio.run(mcp_server.SERVER._handle_call_tool(None, params))


def test_browser_report_run_sends_harness_mcp_judgement_capped_per_process(reports):
    args = {"success": False, "failure_reason": "blocked", "gotchas": ["captcha on search"], "bot_block": True}
    texts = [_call("browser_report_run", args).content[0].text for _ in range(4)]

    assert texts[0] == "Run reported to the Browser Use team. Thanks."
    assert texts[3].startswith("Already reported 3")
    assert len(reports) == 3
    props = reports[0]["properties"]
    assert reports[0]["event"] == "library_judgement"
    assert (props["surface"], props["judge_source"], props["gotchas"]) == ("harness-mcp", "self", ["captcha on search"])
    assert props["bot_block_or_captcha_detected"] is True


def test_browser_feedback_sends_harness_mcp_feedback(reports):
    result = _call("browser_feedback", {"message": "browser_click misses", "category": "bug"})
    assert result.is_error is False
    assert reports[0]["event"] == "library_feedback"
    assert reports[0]["properties"]["source"] == "harness-mcp"


def test_mcp_reports_send_nothing_with_telemetry_off(reports, monkeypatch):
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "false")
    assert "nothing was sent" in _call("browser_feedback", {"message": "x"}).content[0].text
    assert "nothing was sent" in _call("browser_report_run", {"success": True}).content[0].text
    assert reports == []
    assert mcp_server._reports_sent == {"run": 0, "feedback": 0}


def test_browser_feedback_empty_message_is_a_tool_error(reports):
    assert _call("browser_feedback", {"message": "  "}).is_error is True
    assert reports == []
