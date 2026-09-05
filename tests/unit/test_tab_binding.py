import asyncio
import json
import stat
from types import SimpleNamespace

import pytest

from browser_harness import daemon
from browser_harness import helpers
from browser_harness._tab_binding import TabBinding, TabLost, browser_key


class Browser:
    def __init__(self, targets):
        self.targets = targets
        self.calls = []
        async def event(*args):
            pass
        self._event_registry = SimpleNamespace(handle_event=event)

    async def start(self):
        pass

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if method == "Target.getTargets":
            return {"targetInfos": [{"targetId": t, "type": "page", "url": "https://example.test"} for t in self.targets]}
        if method == "Target.attachToTarget":
            return {"sessionId": "session-" + params["targetId"]}
        if session_id == "stale":
            raise RuntimeError("Session with given id not found")
        return {}


@pytest.fixture
def setup_browser(tmp_path, monkeypatch):
    browser = Browser(["owned", "other"])
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://localhost:9222/devtools/browser/id?token=secret")
    monkeypatch.setattr(daemon, "CDPClient", lambda url: browser)
    monkeypatch.setattr(daemon, "log", lambda msg: None)
    monkeypatch.setattr(daemon.ipc, "pid_path", lambda name: tmp_path / "daemon.pid")
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    return browser, tmp_path / "daemon.tab.json"


def test_restart_and_recovery_keep_selected_target_despite_reordering(setup_browser):
    browser, path = setup_browser
    async def run():
        first = daemon.Daemon()
        await first.start()
        await first.handle({"meta": "set_session", "session_id": "selected", "target_id": "other"})
        second = daemon.Daemon()
        await second.start()
        assert second.target_id == "other"
        second.session = "stale"
        assert await second.handle({"method": "Input.dispatchMouseEvent", "params": {"type": "mousePressed"}}) == {"result": {}}
        assert browser.calls[-1][2] == "session-other"
    asyncio.run(run())
    assert "secret" not in path.read_text()
    assert "localhost" not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("fault", ["closed", "changed-browser", "corrupt"])
def test_lost_binding_keeps_control_plane_and_requires_explicit_selection(setup_browser, monkeypatch, fault):
    browser, path = setup_browser
    async def run():
        first = daemon.Daemon()
        await first.start()
        if fault == "closed":
            browser.targets = ["other"]
        elif fault == "changed-browser":
            monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://localhost:9222/devtools/browser/new")
        else:
            path.write_text("broken")
        browser.calls.clear()
        second = daemon.Daemon()
        await second.start()
        assert not any(m == "Target.attachToTarget" for m, _, _ in browser.calls)
        result = await second.handle({"method": "Input.dispatchMouseEvent", "params": {"type": "mousePressed"}})
        assert result["error"].startswith("TabLost:")
        assert not any(m == "Input.dispatchMouseEvent" for m, _, _ in browser.calls)
        assert "result" in await second.handle({"method": "Target.getTargets"})
        await second.handle({"meta": "set_session", "session_id": "session-other", "target_id": "other"})
        assert await second.handle({"method": "Runtime.evaluate"}) == {"result": {}}
        assert json.loads(path.read_text())["target"] == "other"
    asyncio.run(run())


def test_recovery_never_falls_back_to_owned_tab(setup_browser, monkeypatch):
    browser, _ = setup_browser
    monkeypatch.setattr(daemon, "NAME", "worker")
    d = daemon.Daemon()
    d.cdp, d.target_id, d.dedicated_target_id, d.session = browser, "closed-selection", "owned", "stale"
    result = asyncio.run(d.handle({"method": "Input.dispatchMouseEvent", "params": {"type": "mousePressed"}}))
    assert "TabLost" in result["error"]
    assert not any(m in {"Target.attachToTarget", "Target.createTarget"} for m, _, _ in browser.calls)


def test_failed_atomic_save_retains_previous_binding_and_selection(setup_browser, monkeypatch):
    browser, path = setup_browser
    async def run():
        d = daemon.Daemon()
        await d.start()
        before = path.read_bytes()
        def fail(*args):
            raise OSError("disk full")
        monkeypatch.setattr("browser_harness._tab_binding.os.replace", fail)
        result = await d.handle({"meta": "set_session", "target_id": "other", "session_id": "new"})
        assert result["error"].startswith("TabBindingWriteFailed:")
        assert (d.target_id, d.session) == ("owned", "session-owned")
        assert path.read_bytes() == before
        assert list(path.parent.glob("daemon.tab.json.*")) == []
    asyncio.run(run())


@pytest.mark.parametrize("data", [[], {"version": 2}, {"version": 1, "browser": "key", "target": None}, {"version": 1, "browser": "key", "target": "tab", "owned": 3}])
def test_invalid_binding_is_not_treated_as_first_attach(tmp_path, data):
    path = tmp_path / "tab.json"
    path.write_text(json.dumps(data))
    with pytest.raises(TabLost):
        TabBinding(path, "key").load()


def test_browser_identity_ignores_rotating_credentials():
    assert browser_key("wss://a:b@host:443/browser/id?key=one") == browser_key("wss://x:y@host:443/browser/id?key=two")
    assert browser_key("wss://host/a", "cloud-1") == browser_key("wss://host/b", "cloud-1")
    assert browser_key("wss://host/a") != browser_key("wss://host/b")


@pytest.mark.parametrize("failure,detach", [(RuntimeError("TabBindingWriteFailed: disk full"), True), (helpers._IPCResponseTimeout("unknown outcome"), False)])
def test_switch_detaches_only_after_explicit_binding_rejection(monkeypatch, failure, detach):
    calls = []
    def cdp(method, **params):
        calls.append(method)
        return {"sessionId": "new"}
    def fail(req):
        raise failure
    monkeypatch.setattr(helpers, "cdp", cdp)
    monkeypatch.setattr(helpers, "_send", fail)
    with pytest.raises(type(failure)):
        helpers.switch_tab("selected")
    assert ("Target.detachFromTarget" in calls) is detach


def test_observed_detach_recovers_without_sending_into_dead_session(setup_browser):
    browser, _ = setup_browser
    async def run():
        d = daemon.Daemon()
        await d.start()
        old = d.session
        original = browser.send_raw
        async def send(method, params=None, session_id=None):
            result = await original(method, params, session_id)
            return {"sessionId": "recovered"} if method == "Target.attachToTarget" else result
        browser.send_raw = send
        d._record_event("Target.detachedFromTarget", {"sessionId": old})
        browser.calls.clear()
        await d.handle({"method": "Runtime.evaluate"})
        methods = [m for m, _, _ in browser.calls]
        assert methods[0] == "Target.getTargets"
        assert methods.index("Target.attachToTarget") < methods.index("Runtime.evaluate")
    asyncio.run(run())


def test_acknowledged_close_rejects_next_action_before_detach_event(setup_browser):
    browser, _ = setup_browser
    async def run():
        d = daemon.Daemon()
        await d.start()
        original = browser.send_raw
        async def send(method, params=None, session_id=None):
            if method == "Target.closeTarget":
                return {"success": True}
            return await original(method, params, session_id)
        browser.send_raw = send
        await d.handle({"method": "Target.closeTarget", "params": {"targetId": "owned"}})
        browser.calls.clear()
        result = await d.handle({"method": "Input.dispatchMouseEvent"})
        assert "TabLost" in result["error"]
        assert browser.calls == []
    asyncio.run(run())
