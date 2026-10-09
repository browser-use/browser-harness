"""Regression tests for recording browser actions invoked through MCP."""

import asyncio
import base64
import json

import pytest

pytest.importorskip("mcp")

from mcp_types import CallToolRequestParams

import mcp_server
from browser_harness import helpers, recorder


def _call_tool(name, arguments=None):
    response = asyncio.run(
        mcp_server.SERVER._handle_call_tool(
            None,
            CallToolRequestParams(name=name, arguments=arguments or {}),
        )
    )
    assert response.is_error is False, response
    return json.loads(response.content[0].text)


def test_recording_includes_successful_mcp_action(tmp_path, monkeypatch):
    inserted = []

    def fake_cdp(method, **params):
        if method == "Input.insertText":
            inserted.append(params["text"])
            return {}
        if method == "Runtime.evaluate":
            return {
                "result": {
                    "type": "object",
                    "value": {"url": "https://example.test/"},
                }
            }
        if method == "Page.captureScreenshot":
            return {"data": base64.b64encode(b"fake-jpeg-frame").decode()}
        raise AssertionError(f"Unexpected CDP method: {method}")

    monkeypatch.setattr(helpers, "cdp", fake_cdp)
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    monkeypatch.setattr(recorder, "_recordings_root", lambda: tmp_path)
    monkeypatch.setattr(recorder, "_SETTLE_SECONDS", 0)
    monkeypatch.setenv("BH_RECORD", "1")
    monkeypatch.setenv("BU_NAME", "mcp-recording-test")

    def recorded_events():
        path = tmp_path / "mcp-recording" / "events.jsonl"
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def recorded_helpers():
        return [event["helper"] for event in recorded_events()]

    started = _call_tool(
        "browser_start_recording",
        {"name": "mcp-recording"},
    )
    typed = _call_tool(
        "browser_type",
        {"text": "mcp-text"},
    )

    # Verify the action appears while recording is still active, rather than
    # being inferred later from stop_recording().
    assert typed == {"ok": True}
    assert inserted == ["mcp-text"]
    assert recorded_helpers() == [
        "start_recording",
        "type_text",
    ]
    type_event = recorded_events()[1]
    assert type_event["text"] == "mcp-text"

    stopped = _call_tool("browser_stop_recording")

    assert started["recording_dir"] == stopped["recording_dir"]
    assert recorded_helpers() == [
        "start_recording",
        "type_text",
        "stop_recording",
    ]
    assert len(list((tmp_path / "mcp-recording").glob("*.jpg"))) == 3
