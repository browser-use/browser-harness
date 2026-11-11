import asyncio

import pytest

from browser_harness import helpers


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True, "1", None])
def test_invalid_timeout_never_contacts_browser(monkeypatch, timeout):
    monkeypatch.setattr(helpers, "_send", lambda *a, **k: pytest.fail("unexpected IPC"))
    with pytest.raises(ValueError):
        helpers.wait_until("true", timeout)


@pytest.mark.parametrize("condition", ["", "  ", None, 1])
def test_invalid_condition(condition):
    with pytest.raises(ValueError):
        helpers.wait_until(condition)


def test_wait_is_pinned_and_uses_one_monotonic_budget(monkeypatch):
    now, calls = [0.0], []
    monkeypatch.setattr(helpers.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(helpers.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(helpers.time, "time", lambda: pytest.fail("wall clock used"))
    def send(req, response_timeout, deadline):
        calls.append((req, response_timeout, deadline))
        if req.get("meta") == "session":
            now[0] += 0.2
            return {"session_id": "original"}
        assert req["session_id"] == "original"
        return {"result": {"result": {"value": len(calls) == 3}}}
    monkeypatch.setattr(helpers, "_send", send)
    assert helpers.wait_until("document.title === 'Done'", timeout=1) is True
    assert [c[2] for c in calls] == [1, 1, 1]
    assert calls[1][1] == pytest.approx(0.8)
    assert calls[2][1] == pytest.approx(0.7)
    assert calls[2][0]["params"]["timeout"] == pytest.approx(700)


@pytest.mark.parametrize("failure", ["false", "hung", "session", "js"])
def test_wait_failures_are_not_reported_as_success(monkeypatch, failure):
    now = [0.0]
    monkeypatch.setattr(helpers.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(helpers.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    def send(req, **kwargs):
        if req.get("meta") == "session":
            return {"session_id": "original"}
        if failure == "hung":
            raise helpers._IPCResponseTimeout("never-settled promise")
        if failure == "session":
            raise RuntimeError("Session with given id not found")
        if failure == "js":
            return {"result": {"exceptionDetails": {"text": "ReferenceError: missing"}}}
        return {"result": {"result": {"value": False}}}
    monkeypatch.setattr(helpers, "_send", send)
    error, match = (TimeoutError, "wait_until timed out after 0.25s") if failure in {"false", "hung"} else (RuntimeError, "Session|JavaScript")
    with pytest.raises(error, match=match):
        helpers.wait_until("missing", timeout=0.25)
    assert now[0] <= 0.25


def test_ipc_connect_and_response_share_deadline(monkeypatch):
    now, budgets = [10.0], []
    class Connection:
        def settimeout(self, value):
            budgets.append(value)
        def close(self):
            pass
    def connect(name, timeout):
        budgets.append(timeout)
        now[0] += 0.3
        return Connection(), None
    monkeypatch.setattr(helpers.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(helpers.ipc, "connect", connect)
    monkeypatch.setattr(helpers.ipc, "request", lambda *args, **kwargs: {"session_id": "s"})
    helpers._send({"meta": "session"}, response_timeout=1, deadline=10.5)
    assert budgets == pytest.approx([0.5, 0.2])


def test_partial_responses_do_not_restart_deadline(monkeypatch):
    now, budgets = [0.0], []
    class Connection:
        def settimeout(self, value):
            budgets.append(value)
        def sendall(self, value):
            pass
        def recv(self, size):
            now[0] += 0.3
            return b" "
    monkeypatch.setattr(helpers.ipc.time, "monotonic", lambda: now[0])
    with pytest.raises(TimeoutError, match="deadline exceeded"):
        helpers.ipc.request(Connection(), None, {}, deadline=0.5)
    assert budgets == pytest.approx([0.5, 0.2])


def test_mcp_wait_timeout_is_tool_error(monkeypatch):
    pytest.importorskip("mcp")
    import mcp_server
    from mcp_types import CallToolRequestParams
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    def timeout(*args, **kwargs):
        raise TimeoutError("wait_until timed out")
    monkeypatch.setattr(mcp_server, "wait_until", timeout)
    result = asyncio.run(mcp_server.SERVER._handle_call_tool(None, CallToolRequestParams(name="browser_wait_until", arguments={"js_condition": "false"})))
    assert result.is_error is True
    assert "wait_until timed out" in result.content[0].text
