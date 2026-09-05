import asyncio
import os

import pytest

from browser_harness import daemon


def test_publish_own_pid_never_truncates_parent_record(tmp_path, monkeypatch):
    pid_file = tmp_path / "daemon.pid"
    pid_file.write_text('{"pid":4321,"started":"process start with spaces"}')
    real_replace = os.replace
    observed = []

    def replace(src, dst):
        observed.append(pid_file.read_text())
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    daemon._publish_own_pid(pid_file, pid=4321)

    expected = '{"pid":4321,"started":"process start with spaces"}'
    assert observed == [expected]
    assert pid_file.read_text() == expected


@pytest.mark.parametrize(
    ("url", "label"),
    [
        (
            "ws://openclaw-internal:secret@127.0.0.1:18792/devtools/browser/id?token=x",
            "ws://127.0.0.1:18792",
        ),
        ("wss://provider.example/session/private-id?token=secret", "wss://provider.example"),
        ("wss://[::1]:9222/devtools/browser/id", "wss://[::1]:9222"),
        ("not-a-url", "<redacted-cdp-endpoint>"),
    ],
)
def test_safe_connection_label_removes_credentials_paths_and_queries(url, label):
    assert daemon._safe_connection_label(url) == label


def test_remote_stop_retries_and_succeeds(monkeypatch):
    attempts = []
    monkeypatch.setattr(daemon, "REMOTE_ID", "browser-1")
    monkeypatch.setattr(daemon, "_REMOTE_STOPPED", False)
    monkeypatch.setattr(daemon.auth, "get_browser_use_api_key", lambda: "key")
    monkeypatch.setattr(daemon.time, "sleep", lambda _seconds: None)

    def urlopen(_request, timeout):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise OSError("temporary")
        return type("Response", (), {"read": lambda self: b""})()

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)

    assert daemon.stop_remote(strict=True) is True
    assert attempts == [15, 15, 15]
    assert daemon._REMOTE_STOPPED is True


def test_shutdown_keeps_daemon_alive_when_cloud_stop_fails(monkeypatch):
    d = daemon.Daemon()
    d.stop = asyncio.Event()
    monkeypatch.setattr(
        daemon,
        "stop_remote",
        lambda strict=False: (_ for _ in ()).throw(RuntimeError("billing stop failed")),
    )

    response = asyncio.run(d.handle({"meta": "shutdown"}))

    assert response == {"error": "billing stop failed"}
    assert d.stop.is_set() is False


class _FakeCDP:
    """Records send_raw calls so tests can assert which CDP methods fired."""

    def __init__(self):
        self.calls = []  # list of (method, params, session_id)

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        # Set-session/initial-attach paths only need a benign response.
        return {}


def _fresh_daemon():
    d = daemon.Daemon()
    d.cdp = _FakeCDP()
    return d


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_tab_marker_can_be_disabled_before_set_session_schedules_it(monkeypatch, value):
    monkeypatch.setenv("BH_TAB_MARKER", value)
    d = _fresh_daemon()

    async def run():
        await d.handle({
            "meta": "set_session",
            "session_id": "session-without-marker",
            "target_id": "target-without-marker",
        })
        await asyncio.sleep(0)

    asyncio.run(run())

    assert not [call for call in d.cdp.calls if call[0] == "Runtime.evaluate"]


def test_tab_marker_stays_enabled_by_default(monkeypatch):
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    d = _fresh_daemon()

    async def run():
        await d.handle({
            "meta": "set_session",
            "session_id": "session-with-marker",
            "target_id": "target-with-marker",
        })
        await asyncio.sleep(0)

    asyncio.run(run())

    assert [call for call in d.cdp.calls if call[0] == "Runtime.evaluate"] == [
        (
            "Runtime.evaluate",
            {"expression": daemon.TAB_MARKER_JS},
            "session-with-marker",
        )
    ]


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_tab_marker_disabled_on_page_load_events(monkeypatch, value):
    monkeypatch.setenv("BH_TAB_MARKER", value)
    d = _fresh_daemon()
    d.session = "loaded-session"

    d._record_event("Page.loadEventFired", {}, "loaded-session")

    assert not [call for call in d.cdp.calls if call[0] == "Runtime.evaluate"]


def test_set_session_enables_all_four_default_domains_on_new_session():
    """Legacy set_session must retain domain parity with initial attach."""
    d = _fresh_daemon()
    new_session = "session-AFTER-switch"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": new_session,
        "target_id": "target-2",
    }))

    enabled_on_new = [
        method for (method, _params, sid) in d.cdp.calls
        if sid == new_session and method.endswith(".enable")
    ]
    assert set(enabled_on_new) == {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}, (
        f"set_session must enable Page/DOM/Runtime/Network on the new session "
        f"(parity with initial attach). Got: {enabled_on_new}"
    )
    assert d.session == new_session
    assert d.target_id == "target-2"


def test_prepare_target_attaches_once_without_changing_daemon_default():
    d = daemon.Daemon()
    d.cdp = _AttachCDP()
    d.session = "daemon-default-session"
    d.target_id = "daemon-default-target"

    result = asyncio.run(d.handle({
        "meta": "prepare_target",
        "target_id": "agent-target",
    }))
    again = asyncio.run(d.handle({
        "meta": "prepare_target",
        "target_id": "agent-target",
    }))

    assert result == {"session_id": "session-for-agent-target", "target_id": "agent-target"}
    assert again == result
    assert d.session == "daemon-default-session"
    assert d.target_id == "daemon-default-target"
    enabled = {
        method for method, _params, session_id in d.cdp.calls
        if session_id == "session-for-agent-target" and method.endswith(".enable")
    }
    assert enabled == {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}
    assert [method for method, _params, _session in d.cdp.calls].count("Target.attachToTarget") == 1
    assert [call for call in d.cdp.calls if call[0] == "Emulation.setFocusEmulationEnabled"] == [
        ("Emulation.setFocusEmulationEnabled", {"enabled": True}, "session-for-agent-target")
    ]
    asyncio.run(d.handle({"method":"Emulation.setFocusEmulationEnabled", "target_id":"agent-target", "params":{"enabled":False}}))
    asyncio.run(d.handle({"meta":"prepare_target", "target_id":"agent-target"}))
    assert [call[1] for call in d.cdp.calls if call[0] == "Emulation.setFocusEmulationEnabled"] == [
        {"enabled":True}, {"enabled":False}
    ], "reselecting a cached target must preserve the agent's override"
    assert not [
        call for call in d.cdp.calls
        if call[0] == "Network.disable" and call[2] == "daemon-default-session"
    ]


def test_concurrent_prepare_target_calls_share_one_attachment():
    class _SlowAttachCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "Target.attachToTarget":
                await asyncio.sleep(0)
                return {"sessionId": "shared-session"}
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _SlowAttachCDP()
        requests = [
            d.handle({"meta": "prepare_target", "target_id": "shared-target"}),
            d.handle({"meta": "prepare_target", "target_id": "shared-target"}),
        ]
        return d, await asyncio.gather(*requests)

    d, results = asyncio.run(run())

    expected = {"session_id": "shared-session", "target_id": "shared-target"}
    assert results == [expected, expected]
    assert [call[0] for call in d.cdp.calls].count("Target.attachToTarget") == 1


def test_concurrent_clients_keep_commands_on_their_target_sessions():
    class _ConcurrentCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            await asyncio.sleep(0)
            return {"value": f"{session_id}:{params['expression']}"}

    async def run():
        d = daemon.Daemon()
        d.cdp = _ConcurrentCDP()
        d.session = "daemon-default-session"
        d.target_sessions = {"target-a": "session-a", "target-b": "session-b"}
        d.session_targets = {"session-a": "target-a", "session-b": "target-b"}
        return d, await asyncio.gather(
            d.handle({
                "method": "Runtime.evaluate",
                "params": {"expression": "agent-a"},
                "target_id": "target-a",
            }),
            d.handle({
                "method": "Runtime.evaluate",
                "params": {"expression": "agent-b"},
                "target_id": "target-b",
            }),
        )

    d, results = asyncio.run(run())

    assert results == [
        {"result": {"value": "session-a:agent-a"}},
        {"result": {"value": "session-b:agent-b"}},
    ]
    assert d.session == "daemon-default-session"


def test_browser_domain_commands_bypass_the_selected_target_session():
    d = _fresh_daemon()
    d._remember_target_session("agent-target", "agent-session")

    asyncio.run(d.handle({
        "method": "Browser.getVersion",
        "params": {},
        "target_id": "agent-target",
    }))

    assert d.cdp.calls == [("Browser.getVersion", {}, None)]


def test_target_scoped_event_drain_does_not_consume_another_agents_events():
    d = _fresh_daemon()
    d.session_targets = {"session-a": "target-a", "session-b": "target-b"}
    d._record_event("Network.requestWillBeSent", {"requestId": "a"}, "session-a")
    d._record_event("Network.requestWillBeSent", {"requestId": "b"}, "session-b")

    first = asyncio.run(d.handle({"meta": "drain_events", "target_id": "target-a"}))
    second = asyncio.run(d.handle({"meta": "drain_events", "target_id": "target-b"}))

    assert [event["params"]["requestId"] for event in first["events"]] == ["a"]
    assert [event["params"]["requestId"] for event in second["events"]] == ["b"]


def test_global_event_drain_preserves_raw_events_and_independent_tab_queues():
    d = _fresh_daemon()
    d.target_id = "default-target"
    d.session_targets = {"default-session": "default-target", "other-session": "other-target"}
    d._record_event("Network.requestWillBeSent", {"requestId": "default"}, "default-session")
    d._record_event("Network.requestWillBeSent", {"requestId": "other"}, "other-session")
    d._record_event("Browser.downloadWillBegin", {})
    d._record_event("Target.attachedToTarget", {})
    d._record_event("Network.requestWillBeSent", {}, "raw-iframe")

    default = asyncio.run(d.handle({"meta": "drain_events"}))
    other = asyncio.run(d.handle({"meta": "drain_events", "target_id": "other-target"}))

    assert len(default["events"]) == 5
    assert default["events"][-1]["session_id"] == "raw-iframe"
    assert [event["params"]["requestId"] for event in other["events"]] == ["other"]
    assert asyncio.run(d.handle({"meta":"drain_events"}))["events"] == []
    d._record_event("Network.responseReceived", {}, "other-session")
    asyncio.run(d.handle({"meta":"drain_events", "target_id":"other-target"}))
    assert len(asyncio.run(d.handle({"meta":"drain_events"}))["events"]) == 1


def test_pending_dialog_is_scoped_to_the_requesting_target():
    d = _fresh_daemon()
    d.session_targets = {"session-a": "target-a", "session-b": "target-b"}
    d._record_event("Page.javascriptDialogOpening", {"message": "A"}, "session-a")
    d._record_event("Page.javascriptDialogOpening", {"message": "B"}, "session-b")

    a = asyncio.run(d.handle({"meta": "pending_dialog", "target_id": "target-a"}))
    b = asyncio.run(d.handle({"meta": "pending_dialog", "target_id": "target-b"}))

    assert a == {"dialog": {"message": "A"}}
    assert b == {"dialog": {"message": "B"}}


def test_pending_dialog_survives_a_later_command_for_the_same_target():
    d = _fresh_daemon()
    d.session_targets["old-session"] = "same-target"
    d._record_event("Page.javascriptDialogOpening", {"message": "Still open"}, "old-session")

    result = asyncio.run(d.handle({
        "meta": "pending_dialog",
        "target_id": "same-target",
    }))

    assert result == {"dialog": {"message": "Still open"}}


def test_target_destroyed_cleans_cached_target_state():
    d = _fresh_daemon()
    d._remember_target_session("agent-target", "agent-session")
    d._record_event("Network.requestWillBeSent", {"requestId": "a"}, "agent-session")
    d._record_event("Page.javascriptDialogOpening", {"message": "A"}, "agent-session")

    d._record_event("Target.targetDestroyed", {"targetId": "agent-target"})

    assert "agent-session" not in d.session_targets
    assert "agent-target" not in d.target_sessions
    assert "agent-target" not in d.events_by_target
    assert "agent-target" not in d.dialogs_by_target


def test_set_session_falls_back_to_existing_target_id_when_not_provided():
    """If a caller forgets target_id (passes None), the daemon should keep its
    existing target_id rather than overwriting it with None — otherwise
    subsequent calls that depend on self.target_id would break."""
    d = _fresh_daemon()
    d.target_id = "original-target"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-AFTER",
        "target_id": None,
    }))

    assert d.target_id == "original-target"
    assert d.session == "session-AFTER"


def test_enable_default_domains_swallows_errors_per_domain():
    """A single domain failing to enable must not prevent the others from
    being attempted — that would leave the daemon in a partially-configured
    state. Each Domain.enable call has its own try/except inside the helper."""
    class _PartialFailureCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method in ("DOM.enable", "Emulation.setFocusEmulationEnabled"):
                raise RuntimeError("simulated DOM failure")
            return {}

    d = daemon.Daemon()
    d.cdp = _PartialFailureCDP()

    asyncio.run(d._enable_default_domains("session-X"))

    attempted = [m for (m, _p, _s) in d.cdp.calls]
    assert "Page.enable" in attempted
    assert "DOM.enable" in attempted  # attempted, but raised
    assert "Runtime.enable" in attempted
    assert "Network.enable" in attempted
    assert "Emulation.setFocusEmulationEnabled" in attempted


def test_set_session_keeps_old_target_domains_enabled():
    """A legacy client moving the default must not disrupt target-aware clients."""
    d = _fresh_daemon()
    d.session = "session-OLD"
    d.target_id = "target-OLD"
    d._remember_target_session("target-OLD", "session-OLD")

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-NEW",
        "target_id": "target-NEW",
    }))

    assert not [call for call in d.cdp.calls if call[0] == "Network.disable"]
    assert d.target_sessions["target-OLD"] == "session-OLD"
    enabled_on_new = {
        method for (method, _p, sid) in d.cdp.calls
        if sid == "session-NEW" and method.endswith(".enable")
    }
    assert enabled_on_new == {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}


def test_set_session_runs_enables_in_parallel():
    """Legacy set_session keeps the four domain enables concurrent."""
    class _ConcurrencyProbeCDP:
        def __init__(self):
            self.calls = []
            self.in_flight = 0
            self.max_concurrent = 0
            self.release = None  # asyncio.Event, set inside the test loop

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            self.in_flight += 1
            self.max_concurrent = max(self.max_concurrent, self.in_flight)
            try:
                await self.release.wait()
            finally:
                self.in_flight -= 1
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _ConcurrencyProbeCDP()
        d.cdp.release = asyncio.Event()

        handle_task = asyncio.create_task(d.handle({
            "meta": "set_session",
            "session_id": "session-NEW",
            "target_id": "target-NEW",
        }))
        # Yield repeatedly until everything that's going to be in-flight is
        # in-flight. Cap iterations to avoid hanging if parallelization breaks.
        for _ in range(50):
            await asyncio.sleep(0)
            if d.cdp.in_flight >= 5:
                break
        peak = d.cdp.max_concurrent
        d.cdp.release.set()
        await handle_task
        return peak, d.cdp.calls

    peak, calls = asyncio.run(run())
    assert peak == 5, (
        f"set_session must run domain and focus enables concurrently "
        f"(observed peak in-flight = {peak}). Sequential await would peak at 1."
    )
    methods = sorted({m for (m, _p, _s) in calls})
    assert {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}.issubset(methods)


def test_current_tab_meta_passes_attached_target_id():
    """Regression for issue #304: helpers.current_tab() previously sent
    Target.getTargetInfo with no targetId. The daemon strips session_id for
    Target.* methods, so the call hit the browser-level connection with empty
    params, and Chrome returned info about the *browser* target (empty
    url/title) instead of the attached page. The daemon now resolves this
    server-side using its tracked target_id."""
    class _TargetInfoCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "Target.getTargetInfo":
                return {"targetInfo": {
                    "targetId": params["targetId"],
                    "url": "https://example.com/",
                    "title": "Example Domain",
                    "type": "page",
                }}
            return {}

    d = daemon.Daemon()
    d.cdp = _TargetInfoCDP()
    d.target_id = "page-target-abc"

    result = asyncio.run(d.handle({"meta": "current_tab"}))

    assert result == {
        "targetId": "page-target-abc",
        "url": "https://example.com/",
        "title": "Example Domain",
    }
    # The targetId must be passed through — that's the whole point of the fix.
    get_info_calls = [(p, s) for (m, p, s) in d.cdp.calls if m == "Target.getTargetInfo"]
    assert get_info_calls == [({"targetId": "page-target-abc"}, None)]


def test_current_tab_meta_returns_not_attached_when_no_target_id():
    """Without an attached page, current_tab() has no meaningful answer.
    Returning {error: not_attached} causes _send() to raise in helpers, which
    is the right signal for callers like ensure_real_tab() that wrap the call
    in try/except."""
    d = _fresh_daemon()
    d.target_id = None

    result = asyncio.run(d.handle({"meta": "current_tab"}))

    assert result == {"error": "not_attached"}
    # No CDP call should have been issued.
    assert d.cdp.calls == []


class _AttachCDP(_FakeCDP):
    """FakeCDP with realistic responses for the attach flow."""

    def __init__(self, targets=None, fail_method=None):
        super().__init__()
        self.targets = targets or []
        self.created = 0
        self.closed = []
        self.fail_method = fail_method

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if method == self.fail_method:
            raise RuntimeError(f"simulated {method} failure")
        if method == "Target.getTargets":
            return {"targetInfos": self.targets}
        if method == "Target.createTarget":
            self.created += 1
            tid = f"created-{self.created}"
            self.targets.append({"targetId": tid, "url": "about:blank", "type": "page"})
            return {"targetId": tid}
        if method == "Target.attachToTarget":
            return {"sessionId": f"session-for-{params['targetId']}"}
        if method == "Target.closeTarget":
            self.closed.append(params["targetId"])
        return {}


def test_named_daemon_creates_dedicated_tab(monkeypatch):
    """Named local/CDP daemons must not fight over the first existing tab."""
    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    existing = [{"targetId": "someone-elses-tab", "url": "https://example.com/", "type": "page"}]
    d = daemon.Daemon()
    d.cdp = _AttachCDP(existing)

    page = asyncio.run(d.attach_first_page())

    assert page["targetId"] == "created-1"
    assert d.target_id == "created-1"
    assert d.dedicated_target_id == "created-1"
    assert d.session == "session-for-created-1"
    attach_calls = [p for (m, p, _s) in d.cdp.calls if m == "Target.attachToTarget"]
    assert attach_calls == [{"targetId": "created-1", "flatten": True}]
    create_calls = [p for (m, p, _s) in d.cdp.calls if m == "Target.createTarget"]
    assert create_calls == [{"url": "about:blank", "background": True}]
    enabled = {m for (m, _p, s) in d.cdp.calls if s == d.session and m.endswith(".enable")}
    assert enabled == {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}


def test_default_daemon_still_attaches_first_page(monkeypatch):
    """The default daemon keeps reusing the user's first real page."""
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    existing = [{"targetId": "user-tab", "url": "https://example.com/", "type": "page"}]
    d = daemon.Daemon()
    d.cdp = _AttachCDP(existing)

    page = asyncio.run(d.attach_first_page())

    assert page["targetId"] == "user-tab"
    assert d.dedicated_target_id is None
    assert d.cdp.created == 0


def test_default_daemon_creates_missing_page_in_background(monkeypatch):
    """Fallback tabs must not steal the user's foreground Chrome tab."""
    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d = daemon.Daemon()
    d.cdp = _AttachCDP()

    page = asyncio.run(d.attach_first_page())

    assert page["targetId"] == "created-1"
    create_calls = [p for (m, p, _s) in d.cdp.calls if m == "Target.createTarget"]
    assert create_calls == [{"url": "about:blank", "background": True}]


def test_named_remote_daemon_keeps_first_page_attach(monkeypatch):
    """A cloud browser is exclusive, so a named cloud daemon needs no extra tab."""
    monkeypatch.setattr(daemon, "NAME", "r7k2")
    monkeypatch.setattr(daemon, "REMOTE_ID", "remote-browser-id")
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cloud")
    existing = [{"targetId": "cloud-blank", "url": "about:blank", "type": "page"}]
    d = daemon.Daemon()
    d.cdp = _AttachCDP(existing)

    page = asyncio.run(d.attach_first_page())

    assert page["targetId"] == "cloud-blank"
    assert d.dedicated_target_id is None
    assert d.cdp.created == 0


def test_named_reattach_reuses_dedicated_tab(monkeypatch):
    """A stale CDP session should not replace a tab that still exists."""
    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d = daemon.Daemon()
    d.cdp = _AttachCDP()

    asyncio.run(d.attach_first_page())
    asyncio.run(d.attach_first_page())

    assert d.cdp.created == 1
    assert d.cdp.closed == []
    assert d.target_id == "created-1"
    assert d.dedicated_target_id == "created-1"


def test_named_reattach_keeps_selected_tab_when_it_still_exists(monkeypatch):
    """A deliberate switch_tab remains the active tab after session recovery."""
    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d = daemon.Daemon()
    d.cdp = _AttachCDP()

    asyncio.run(d.attach_first_page())
    d.cdp.targets.append({"targetId": "selected-tab", "url": "https://example.com", "type": "page"})
    d.target_id = "selected-tab"
    asyncio.run(d.attach_first_page())

    assert d.cdp.created == 1
    assert d.cdp.closed == []
    assert d.target_id == "selected-tab"
    assert d.dedicated_target_id == "created-1"
    assert d.session == "session-for-selected-tab"


def test_named_reattach_creates_replacement_only_when_tab_is_gone(monkeypatch):
    """If the user closes the dedicated tab, the daemon creates one replacement."""
    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d = daemon.Daemon()
    d.cdp = _AttachCDP()

    asyncio.run(d.attach_first_page())
    d.cdp.targets = [t for t in d.cdp.targets if t["targetId"] != "created-1"]
    asyncio.run(d.attach_first_page())

    assert d.cdp.created == 2
    assert d.cdp.closed == []
    assert d.target_id == "created-2"
    assert d.dedicated_target_id == "created-2"


def test_concurrent_named_reattach_creates_one_replacement(monkeypatch):
    """Concurrent recovery after a user closes the tab shares one replacement."""
    class _ConcurrentAttachCDP(_AttachCDP):
        def __init__(self):
            super().__init__()
            self.get_calls = 0
            self.first_gets_done = asyncio.Event()

        async def send_raw(self, method, params=None, session_id=None):
            if method == "Target.getTargets":
                self.calls.append((method, params, session_id))
                snapshot = list(self.targets)
                self.get_calls += 1
                if self.get_calls <= 2:
                    if self.get_calls == 2:
                        self.first_gets_done.set()
                    await self.first_gets_done.wait()
                return {"targetInfos": snapshot}
            return await super().send_raw(method, params, session_id)

    async def run():
        d = daemon.Daemon()
        d.cdp = _ConcurrentAttachCDP()
        pages = await asyncio.gather(d.attach_first_page(), d.attach_first_page())
        return d, pages

    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d, pages = asyncio.run(run())

    assert [page["targetId"] for page in pages] == ["created-1", "created-1"]
    assert d.cdp.created == 1
    assert d.cdp.closed == []
    assert d.target_id == "created-1"
    assert d.dedicated_target_id == "created-1"


def test_named_attach_failure_reuses_created_tab_on_retry(monkeypatch):
    """A transient attach failure leaves the tab available for the next retry."""
    class _FailOnceAttachCDP(_AttachCDP):
        def __init__(self):
            super().__init__()
            self.fail_attach = True

        async def send_raw(self, method, params=None, session_id=None):
            if method == "Target.attachToTarget" and self.fail_attach:
                self.calls.append((method, params, session_id))
                self.fail_attach = False
                raise RuntimeError("simulated Target.attachToTarget failure")
            return await super().send_raw(method, params, session_id)

    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d = daemon.Daemon()
    d.cdp = _FailOnceAttachCDP()

    with pytest.raises(RuntimeError, match="Target.attachToTarget"):
        asyncio.run(d.attach_first_page())
    page = asyncio.run(d.attach_first_page())

    assert page["targetId"] == "created-1"
    assert d.cdp.created == 1
    assert d.cdp.closed == []
    assert d.dedicated_target_id == "created-1"


def test_named_local_attach_cleans_inspect_tabs_before_return(monkeypatch):
    """The named-daemon early path must retain local inspect-tab cleanup."""
    monkeypatch.setattr(daemon, "NAME", "worker-a")
    monkeypatch.setattr(daemon, "REMOTE_ID", None)
    monkeypatch.setattr(daemon, "BROWSER_KIND", "local")
    monkeypatch.setattr(daemon, "harness_opened_inspect", lambda: True)
    inspect = {"targetId": "inspect-tab", "url": "chrome://inspect/#remote-debugging", "type": "page"}
    d = daemon.Daemon()
    d.cdp = _AttachCDP([inspect])

    asyncio.run(d.attach_first_page())

    methods = [method for method, _params, _session in d.cdp.calls]
    assert methods.index("Target.closeTarget") < methods.index("Target.createTarget")
    assert d.cdp.closed == ["inspect-tab"]


def test_shutdown_closes_only_the_daemon_owned_tab(monkeypatch):
    """Run cleanup closes the daemon-created tab without touching a user tab."""
    d = daemon.Daemon()
    d.cdp = _AttachCDP()

    async def start():
        d.dedicated_target_id = "daemon-tab"
        d.target_id = "user-selected-tab"
        d.stop = asyncio.Event()
        d.stop.set()

    async def wait_forever(*_args):
        await asyncio.Event().wait()

    d.start = start
    monkeypatch.setattr(daemon, "Daemon", lambda: d)
    monkeypatch.setattr(daemon.ipc, "serve", wait_forever)
    monkeypatch.setattr(daemon.ipc, "sock_addr", lambda _name: "test-socket")
    monkeypatch.setattr(daemon.ipc, "cleanup_endpoint", lambda _name: None)
    monkeypatch.setattr(daemon, "log", lambda _message: None)

    asyncio.run(daemon.main())

    assert d.cdp.closed == ["daemon-tab"]
    assert d.dedicated_target_id is None
    assert d.target_id == "user-selected-tab"


def test_delayed_stale_request_follows_recovery_during_domain_enable(monkeypatch):
    """Publish the replacement before post-attach domain setup can yield."""
    class _RecoveryWindowCDP(_FakeCDP):
        def __init__(self):
            super().__init__()
            self.slow_started = None
            self.release_slow = None
            self.enable_started = None
            self.release_enables = None

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "Runtime.evaluate" and session_id == "stale-session":
                if params["expression"] == "slow":
                    self.slow_started.set()
                    await self.release_slow.wait()
                raise RuntimeError("Session with given id not found")
            if method == "Target.getTargets":
                return {"targetInfos": [
                    {"targetId": "same-tab", "url": "https://example.com", "type": "page"}
                ]}
            if method == "Target.attachToTarget":
                return {"sessionId": "replacement-session"}
            if method.endswith(".enable") and session_id == "replacement-session":
                self.enable_started.set()
                await self.release_enables.wait()
                return {}
            if method == "Runtime.evaluate" and session_id == "replacement-session":
                return {"value": params["expression"]}
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _RecoveryWindowCDP()
        d.cdp.slow_started = asyncio.Event()
        d.cdp.release_slow = asyncio.Event()
        d.cdp.enable_started = asyncio.Event()
        d.cdp.release_enables = asyncio.Event()
        d.session = "stale-session"
        d.target_id = "same-tab"

        slow = asyncio.create_task(d.handle({
            "method": "Runtime.evaluate", "params": {"expression": "slow"}
        }))
        await d.cdp.slow_started.wait()
        fast = asyncio.create_task(d.handle({
            "method": "Runtime.evaluate", "params": {"expression": "fast"}
        }))
        await d.cdp.enable_started.wait()
        # Recovery has attached but is still blocked enabling domains. The
        # delayed request must already be able to find the replacement.
        d.cdp.release_slow.set()
        slow_result = await slow
        d.cdp.release_enables.set()
        return d, await fast, slow_result

    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d, fast, slow = asyncio.run(run())

    assert fast == {"result": {"value": "fast"}}
    assert slow == {"result": {"value": "slow"}}
    assert d._session_replacements == {"stale-session": "replacement-session"}


def test_tab_switch_waits_for_recovery_and_keeps_old_action_on_old_tab(monkeypatch):
    """A switch during target discovery cannot redirect the recovered action."""
    class _SwitchRaceCDP(_FakeCDP):
        def __init__(self):
            super().__init__()
            self.discovery_started = None
            self.release_discovery = None

        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if (
                method == "Runtime.evaluate"
                and params.get("expression") == "old-tab-action"
                and session_id == "old-session"
            ):
                raise RuntimeError("Session with given id not found")
            if method == "Target.getTargets":
                self.discovery_started.set()
                await self.release_discovery.wait()
                return {"targetInfos": [
                    {"targetId": "old-tab", "url": "https://example.com", "type": "page"}
                ]}
            if method == "Target.attachToTarget":
                return {"sessionId": "recovered-old-session"}
            if (
                method == "Runtime.evaluate"
                and params.get("expression") == "old-tab-action"
                and session_id == "recovered-old-session"
            ):
                return {"value": "old-tab-action"}
            return {}

    async def run():
        d = daemon.Daemon()
        d.cdp = _SwitchRaceCDP()
        d.cdp.discovery_started = asyncio.Event()
        d.cdp.release_discovery = asyncio.Event()
        d.session = "old-session"
        d.target_id = "old-tab"

        request = asyncio.create_task(d.handle({
            "method": "Runtime.evaluate",
            "params": {"expression": "old-tab-action"},
        }))
        await d.cdp.discovery_started.wait()
        switch = asyncio.create_task(d.handle({
            "meta": "set_session",
            "session_id": "new-session",
            "target_id": "new-tab",
        }))
        await asyncio.sleep(0)  # let set_session wait on the recovery lock
        d.cdp.release_discovery.set()
        result, switch_result = await asyncio.gather(request, switch)
        await asyncio.sleep(0)  # let the cosmetic marker task finish
        return d, result, switch_result

    monkeypatch.setattr(daemon, "NAME", "default")
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    d, result, switch_result = asyncio.run(run())

    assert result == {"result": {"value": "old-tab-action"}}
    assert switch_result == {"session_id": "new-session"}
    assert d.session == "new-session"
    assert d.target_id == "new-tab"
    assert d._session_replacements == {"old-session": "recovered-old-session"}
    redirected = [
        (params, sid)
        for method, params, sid in d.cdp.calls
        if method == "Runtime.evaluate"
        and params.get("expression") == "old-tab-action"
        and sid == "new-session"
    ]
    assert redirected == []


def test_explicit_stale_session_is_not_redirected():
    """Explicit session requests retain their exact-session semantics."""
    class _AlwaysStaleCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            raise RuntimeError("Session with given id not found")

    d = daemon.Daemon()
    d.cdp = _AlwaysStaleCDP()
    d.session = "current-session"

    result = asyncio.run(d.handle({
        "method": "Runtime.evaluate",
        "params": {"expression": "1"},
        "session_id": "explicit-stale-session",
    }))

    assert result == {"error": "Session with given id not found"}
    assert d.cdp.calls == [
        ("Runtime.evaluate", {"expression": "1"}, "explicit-stale-session")
    ]


def test_stale_target_session_reattaches_to_the_same_target():
    class _StaleTargetCDP(_FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            self.calls.append((method, params, session_id))
            if method == "Runtime.evaluate" and session_id == "stale-session":
                raise RuntimeError("Session with given id not found")
            if method == "Target.attachToTarget":
                return {"sessionId": "replacement-session"}
            if method == "Runtime.evaluate" and session_id == "replacement-session":
                return {"value": "same-target"}
            return {}

    d = daemon.Daemon()
    d.cdp = _StaleTargetCDP()
    d._remember_target_session("agent-target", "stale-session")

    result = asyncio.run(d.handle({
        "method": "Runtime.evaluate",
        "params": {"expression": "1"},
        "target_id": "agent-target",
    }))

    assert result == {"result": {"value": "same-target"}}
    assert d.target_sessions["agent-target"] == "replacement-session"
    assert d.session_targets["replacement-session"] == "agent-target"
