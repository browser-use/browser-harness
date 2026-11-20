import asyncio
import json
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
    """Regression: switch_tab() / new_tab() in helpers.py route through the
    `set_session` IPC, which previously only enabled Page on the new
    session. With Network disabled, wait_for_network_idle() silently stops
    receiving events after a tab switch. Initial attach enables all four
    (Page, DOM, Runtime, Network); set_session must enable the same set."""
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
            if method == "DOM.enable":
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


def test_set_session_disables_network_on_old_session_before_enabling_new():
    """When switching tabs, the previous session's Network domain must be
    disabled so background tabs (polling, SSE, etc.) stop emitting events
    into the global buffer that wait_for_network_idle reads. Initial attach
    has no `old_session` so this disable doesn't fire then."""
    d = _fresh_daemon()
    d.session = "session-OLD"
    d.target_id = "target-OLD"

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-NEW",
        "target_id": "target-NEW",
    }))

    disabled = [
        (method, sid) for (method, _params, sid) in d.cdp.calls
        if method == "Network.disable"
    ]
    assert disabled == [("Network.disable", "session-OLD")], (
        f"Network.disable must fire on the old session before re-enabling on "
        f"the new one. Got: {disabled}"
    )

    # Sanity: the new session still gets Network.enable.
    enabled_on_new = {
        method for (method, _p, sid) in d.cdp.calls
        if sid == "session-NEW" and method.endswith(".enable")
    }
    assert "Network.enable" in enabled_on_new


def test_set_session_does_not_disable_network_when_no_previous_session():
    """First set_session call (e.g. very early in startup before any attach)
    has no old_session — the Network.disable path must be skipped."""
    d = _fresh_daemon()
    d.session = None  # no prior attach

    asyncio.run(d.handle({
        "meta": "set_session",
        "session_id": "session-FIRST",
        "target_id": "target-FIRST",
    }))

    disables = [m for (m, _p, _s) in d.cdp.calls if m == "Network.disable"]
    assert disables == [], (
        f"Network.disable must not fire when there's no previous session "
        f"to disable. Got: {disables}"
    )


def test_set_session_runs_disable_and_enables_in_parallel():
    """The four Domain.enable calls (plus Network.disable on the old session)
    must run concurrently via asyncio.gather, not sequentially. With the old
    sequential code, helpers.switch_tab() would block in _send() for up to
    ~22s on a slow/remote daemon while the helper's IPC socket has a 5s
    read timeout, causing client-side socket timeouts. Verifying that all
    five CDP calls reach send_raw before any returns proves parallelization."""
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
        d.session = "session-OLD"  # ensures Network.disable on old fires
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
            # 5 = Network.disable on OLD + 4 enables on NEW.
            if d.cdp.in_flight >= 5:
                break
        peak = d.cdp.max_concurrent
        d.cdp.release.set()
        await handle_task
        return peak, d.cdp.calls

    peak, calls = asyncio.run(run())
    assert peak == 5, (
        f"set_session must run disable + 4 enables concurrently via gather "
        f"(observed peak in-flight = {peak}; expected 5 = 1 disable on OLD + "
        f"4 enables on NEW). Sequential await would peak at 1."
    )
    # Sanity: the right calls were made.
    methods = sorted({m for (m, _p, _s) in calls})
    assert "Network.disable" in methods
    assert {"Page.enable", "DOM.enable", "Runtime.enable", "Network.enable"}.issubset(methods)


def test_set_session_first_attach_runs_four_enables_in_parallel():
    """When there's no previous session, the disable path is skipped — only
    the four enables run, still in parallel."""
    class _ConcurrencyProbeCDP:
        def __init__(self):
            self.calls = []
            self.in_flight = 0
            self.max_concurrent = 0
            self.release = None

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
        d.session = None  # no previous session
        d.cdp.release = asyncio.Event()

        handle_task = asyncio.create_task(d.handle({
            "meta": "set_session",
            "session_id": "session-FIRST",
            "target_id": "target-FIRST",
        }))
        for _ in range(50):
            await asyncio.sleep(0)
            if d.cdp.in_flight >= 4:
                break
        peak = d.cdp.max_concurrent
        d.cdp.release.set()
        await handle_task
        return peak

    peak = asyncio.run(run())
    assert peak == 4, (
        f"first set_session must run 4 enables concurrently "
        f"(observed peak = {peak}). No Network.disable should fire."
    )


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


# BH_CDP_DENY=tokens: opt-in fail-closed CDP filter for browser tokens.

_TOKENS_DENIED = [
    ("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}),
    ("Fetch.continueRequest", {"requestId": "1"}),
    ("Tracing.start", {}),
    ("Target.attachToBrowserTarget", {}),
    ("Target.exposeDevToolsProtocol", {"targetId": "t"}),
    ("Target.sendMessageToTarget", {"message": '{"id":1,"method":"Fetch.enable"}', "sessionId": "s"}),
    # DevTools frontend can drive the backend itself (review repro: Fetch via InspectorFrontendHost).
    ("Target.openDevTools", {"targetId": "page-target"}),
    ("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True}),
    ("Target.autoAttachRelated", {"targetId": "page-target", "waitForDebuggerOnStart": False}),
    ("Target.setDiscoverTargets", {"discover": False}),
    ("Target.createBrowserContext", {"proxyServer": "http://attacker.example:8080"}),
    ("Security.setIgnoreCertificateErrors", {"ignore": True}),
    ("Security.handleCertificateError", {"eventId": 1, "action": "continue"}),
    ("Network.setRequestInterception", {"patterns": [{"urlPattern": "*"}]}),
    ("Network.getResponseBody", {"requestId": "1"}),
    ("Network.searchInResponseBody", {"requestId": "1", "query": "4111"}),
    ("Network.streamResourceContent", {"requestId": "1"}),
    ("Network.replayXHR", {"requestId": "1"}),
    ("Network.getRequestPostData", {"requestId": "1"}),
    ("Page.getResourceContent", {"frameId": "f", "url": "https://shop.example.com/"}),
    ("Page.navigateToHistoryEntry", {"entryId": 1}),
    ("Audits.getEncodedResponse", {"requestId": "1", "encoding": "webp"}),
    ("Extensions.loadUnpacked", {"path": "/tmp/ext"}),
    ("ServiceWorker.inspectWorker", {"versionId": "1"}),
    ("Browser.executeBrowserCommand", {"commandId": "openTabSearch"}),
    ("DOM.setFileInputFiles", {"files": ["/etc/passwd"], "nodeId": 1}),
    ("Input.dispatchDragEvent", {"type": "drop", "x": 1, "y": 1, "data": {"items": [], "files": ["/etc/passwd"], "dragOperationsMask": 1}}),
    ("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": "/home/u/.config/browser-harness/agent-workspace"}),
    ("Page.setDownloadBehavior", {"behavior": "allowAndName", "downloadPath": "/tmp"}),
    ("Page.navigate", {"url": "chrome://net-export"}),
    ("Page.navigate", {"url": "FILE:///etc/passwd"}),
    ("Page.navigate", {"url": " \tchr\tome://settings"}),
    ("Page.navigate", {"url": "devtools://devtools/bundled/inspector.html"}),
    ("Page.navigate", {"url": "view-source:file:///etc/passwd"}),
    ("Page.navigate", {"url": "chrome-untrusted://print"}),
    ("Page.navigate", {"url": "chrome-extension://abcdefghijklmnopabcdefghijklmnop/options.html"}),
    ("Page.navigate", {"url": "isolated-app://xyz/"}),
    ("Page.navigate", {"url": "edge://net-export"}),
    ("Page.navigate", {"url": ["chrome://net-export"]}),
    ("Target.createTarget", {"url": "chrome://net-internals"}),
    ("Target.createTarget", {"url": "file:///tmp/x.html", "background": True}),
]

_TOKENS_ALLOWED = [
    ("Page.navigate", {"url": "https://shop.example.com/checkout"}),
    ("Page.navigate", {"url": "about:blank"}),
    ("Page.navigate", {"url": "https://example.com/?next=chrome://settings"}),
    ("Target.createTarget", {"url": "about:blank", "background": True}),
    ("Target.getTargets", {}),
    ("Runtime.evaluate", {"expression": "1"}),
    ("Network.enable", {}),
    ("Input.insertText", {"text": "4242 4242 4242 4242"}),
    ("Accessibility.getFullAXTree", {}),
    ("DOM.getBoxModel", {"backendNodeId": 1}),
    ("Page.captureScreenshot", {"format": "png"}),
    ("Browser.getVersion", {}),
    ("Browser.setDownloadBehavior", {"behavior": "deny"}),
    ("Input.dispatchDragEvent", {"type": "dragEnter", "x": 1, "y": 1, "data": {"items": [], "dragOperationsMask": 1}}),
]

_PAGE = {"targetId": "page-target", "type": "page", "url": "https://shop.example.com/"}


class _TargetsCDP(_FakeCDP):
    """_FakeCDP that knows targets, for the tokens-mode attach check."""

    def __init__(self, targets=()):
        super().__init__()
        self.targets = {t["targetId"]: t for t in targets}

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            if params["targetId"] not in self.targets:
                raise RuntimeError("No target with given id found")
            return {"targetInfo": self.targets[params["targetId"]]}
        if method == "Target.attachToTarget":
            return {"sessionId": f"session-{params['targetId']}"}
        return {}


@pytest.fixture(autouse=True)
def _isolated_deny_marker(monkeypatch, tmp_path):
    marker = tmp_path / "bu.deny"
    monkeypatch.setattr(daemon, "_deny_marker", lambda: marker)
    return marker


def _deny_daemon(monkeypatch, value, targets=()):
    if value is None:
        monkeypatch.delenv("BH_CDP_DENY", raising=False)
    else:
        monkeypatch.setenv("BH_CDP_DENY", value)
    d = _fresh_daemon()
    d.cdp = _TargetsCDP([_PAGE, *targets])
    d.session = "page-session"
    d.target_id = _PAGE["targetId"]
    d._track_session("page-session", _PAGE)
    return d


def _call(d, method, params=None, **req):
    return asyncio.run(d.handle({"method": method, "params": params or {}, **req}))


@pytest.mark.parametrize("method,params", _TOKENS_DENIED)
def test_cdp_deny_unset_passes_every_call_through(monkeypatch, method, params):
    d = _deny_daemon(monkeypatch, None)

    result = _call(d, method, params)

    assert result == {"result": {}}
    assert [call[0] for call in d.cdp.calls] == [method]


@pytest.mark.parametrize("method,params", _TOKENS_DENIED)
def test_cdp_deny_tokens_refuses_without_reaching_chrome(monkeypatch, method, params):
    d = _deny_daemon(monkeypatch, "tokens")

    result = _call(d, method, params)

    assert "BH_CDP_DENY=tokens" in result["error"]
    assert method in result["error"]
    assert d.cdp.calls == []


@pytest.mark.parametrize("method,params", _TOKENS_ALLOWED)
def test_cdp_deny_tokens_keeps_normal_calls_working(monkeypatch, method, params):
    d = _deny_daemon(monkeypatch, "tokens")

    result = _call(d, method, params)

    assert result == {"result": {}}
    assert [call[0] for call in d.cdp.calls] == [method]


def test_cdp_deny_tokens_ignores_explicit_session(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")

    result = _call(d, "Fetch.enable", session_id="page-session")

    assert "Fetch.enable is blocked" in result["error"]
    assert d.cdp.calls == []


def test_cdp_deny_tokens_error_names_scheme_not_full_url(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")

    result = _call(d, "Page.navigate", {"url": "file:///home/u/secret.txt"})

    assert result == {"error": "Page.navigate to file: URLs is blocked by BH_CDP_DENY=tokens (browser tokens are active)"}


def test_cdp_deny_tokens_attaches_to_web_page_and_drives_its_session(monkeypatch):
    other = {"targetId": "tab-2", "type": "page", "url": "https://bank.example.com/"}
    d = _deny_daemon(monkeypatch, "tokens", [other])

    attached = _call(d, "Target.attachToTarget", {"targetId": "tab-2", "flatten": True})
    evaluated = _call(d, "Runtime.evaluate", {"expression": "1"}, session_id="session-tab-2")

    assert attached == {"result": {"sessionId": "session-tab-2"}}
    assert evaluated == {"result": {}}
    assert [c[0] for c in d.cdp.calls] == ["Target.getTargetInfo", "Target.attachToTarget", "Runtime.evaluate"]


@pytest.mark.parametrize("target", [
    # Target.openDevTools result: DevTools frontend can send Fetch.enable itself.
    {"targetId": "dt", "type": "page", "url": "devtools://devtools/bundled/devtools_app.html"},
    {"targetId": "omni", "type": "browser_ui", "url": "chrome://omnibox-popup.top-chrome/"},
    {"targetId": "inspect", "type": "page", "url": "chrome://inspect/#devices"},
    {"targetId": "ext-sw", "type": "service_worker", "url": "chrome-extension://abcdefghijklmnop/bg.js"},
    {"targetId": "tab", "type": "tab", "url": "https://shop.example.com/"},
    {"targetId": "browser", "type": "browser", "url": ""},
])
def test_cdp_deny_tokens_refuses_attach_to_privileged_targets(monkeypatch, target):
    d = _deny_daemon(monkeypatch, "tokens", [target])

    result = _call(d, "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})

    assert "Target.attachToTarget" in result["error"] and "BH_CDP_DENY=tokens" in result["error"]
    assert [c[0] for c in d.cdp.calls] == ["Target.getTargetInfo"]


@pytest.mark.parametrize("params", [{}, {"targetId": ""}, {"targetId": ["dt"]}, {"targetId": "missing"}])
def test_cdp_deny_tokens_refuses_attach_without_a_live_target(monkeypatch, params):
    d = _deny_daemon(monkeypatch, "tokens")

    result = _call(d, "Target.attachToTarget", params)

    assert "error" in result
    assert "Target.attachToTarget" not in [c[0] for c in d.cdp.calls]


def test_cdp_deny_tokens_refuses_session_after_tab_lands_on_chrome_page(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")
    d._record_event("Target.targetInfoChanged", {"targetInfo": {**_PAGE, "url": "chrome://inspect/"}})

    evaluated = _call(d, "Runtime.evaluate", {"expression": "chrome.send('x')"})
    left = _call(d, "Page.navigate", {"url": "https://shop.example.com/"})

    assert "chrome: target is blocked" in evaluated["error"]
    assert left == {"result": {}}
    assert [c[0] for c in d.cdp.calls] == ["Page.navigate"]


def test_cdp_deny_tokens_refuses_sessions_it_did_not_attach(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")
    asyncio.run(d.handle({"meta": "set_session", "session_id": "foreign", "target_id": "x"}))
    d.cdp.calls.clear()

    explicit = _call(d, "Runtime.evaluate", {"expression": "1"}, session_id="smuggled")
    default = _call(d, "Runtime.evaluate", {"expression": "1"})

    assert "not attached through this daemon" in explicit["error"]
    assert "not attached through this daemon" in default["error"]
    assert d.cdp.calls == []


def test_cdp_deny_tokens_tracks_sessions_from_attach_events(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")
    d._record_event("Target.attachedToTarget", {
        "sessionId": "evt-session", "waitingForDebugger": False,
        "targetInfo": {"targetId": "dt", "type": "page", "url": "devtools://devtools/x"},
    })

    result = _call(d, "Runtime.evaluate", {"expression": "1"}, session_id="evt-session")

    assert "devtools: target is blocked" in result["error"]


def test_cdp_deny_tokens_lets_destroyed_target_hit_stale_session_recovery(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")
    d._record_event("Target.targetDestroyed", {"targetId": "page-target"})

    assert d._session_denied("page-session", "Runtime.evaluate") is None


def test_cdp_deny_tokens_upload_only_inside_upload_dir(monkeypatch, tmp_path):
    up = tmp_path / "uploads"
    up.mkdir()
    (up / "id.pdf").write_text("x")
    (up / "escape").symlink_to("/etc/passwd")
    monkeypatch.setenv("BH_UPLOAD_DIR", str(up))
    d = _deny_daemon(monkeypatch, "tokens")

    ok = _call(d, "DOM.setFileInputFiles", {"files": [str(up / "id.pdf")], "nodeId": 1})
    refused = [
        _call(d, "DOM.setFileInputFiles", {"files": files, "nodeId": 1})
        for files in ([str(up / ".." / "x")], [str(up / "escape")], ["id.pdf"], "/etc/passwd", [str(up / "id.pdf"), "/etc/passwd"])
    ]

    assert ok == {"result": {}}
    assert all("outside BH_UPLOAD_DIR" in r["error"] for r in refused)
    assert [c[0] for c in d.cdp.calls] == ["DOM.setFileInputFiles"]


def test_cdp_deny_tokens_download_only_inside_download_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_DOWNLOAD_DIR", str(tmp_path))
    d = _deny_daemon(monkeypatch, "tokens")

    ok = _call(d, "Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(tmp_path / "dl")})
    refused = _call(d, "Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(tmp_path.parent)})

    assert ok == {"result": {}}
    assert "outside BH_DOWNLOAD_DIR" in refused["error"]


def _drain(d):
    return asyncio.run(d.handle({"meta": "drain_events"}))["events"]


def test_cdp_deny_tokens_drops_wire_header_events_from_drain(monkeypatch):
    d = _deny_daemon(monkeypatch, "tokens")
    real = {"X-Card": "REAL4111", "Authorization": "Bearer real"}
    d._record_event("Network.requestWillBeSent", {"requestId": "1", "request": {"url": "https://shop.example.com/", "headers": {"X-Card": "DUMMY"}}}, "page-session")
    d._record_event("Network.requestWillBeSentExtraInfo", {"requestId": "1", "headers": real}, "page-session")
    d._record_event("Network.responseReceivedExtraInfo", {"requestId": "1", "headers": {}, "headersText": "X-Card: REAL4111"}, "page-session")
    d._record_event("Network.responseReceived", {"requestId": "1", "response": {"status": 200, "requestHeaders": real, "requestHeadersText": "X-Card: REAL4111"}}, "page-session")
    d._record_event("Network.requestWillBeSent", {"requestId": "2", "request": {"url": "https://shop.example.com/b"}, "redirectResponse": {"status": 302, "requestHeaders": real}}, "page-session")
    d._record_event("Fetch.requestPaused", {"requestId": "f1", "request": {"headers": real}}, "page-session")

    events = _drain(d)

    assert "REAL4111" not in json.dumps(events) and "Bearer real" not in json.dumps(events)
    assert [e["method"] for e in events] == ["Network.requestWillBeSent", "Network.responseReceived", "Network.requestWillBeSent"]
    assert events[1]["params"]["response"] == {"status": 200}


def test_cdp_deny_unset_keeps_extra_info_events(monkeypatch):
    d = _deny_daemon(monkeypatch, None)
    d._record_event("Network.requestWillBeSentExtraInfo", {"requestId": "1", "headers": {"X-Card": "REAL4111"}})

    assert [e["method"] for e in _drain(d)] == ["Network.requestWillBeSentExtraInfo"]


@pytest.mark.parametrize("value,expected", [(None, None), ("tokens", "tokens")])
def test_ping_reports_cdp_deny_mode(monkeypatch, value, expected):
    d = _deny_daemon(monkeypatch, value)

    assert asyncio.run(d.handle({"meta": "ping"}))["cdp_deny"] == expected


@pytest.mark.parametrize("value", ["", "  ", "Tokens", " TOKENS "])
def test_cdp_deny_mode_accepts_unset_or_tokens(monkeypatch, value):
    monkeypatch.setenv("BH_CDP_DENY", value)

    assert daemon.cdp_deny_mode() == ("tokens" if value.strip() else None)


@pytest.mark.parametrize("value", ["token", "1", "on", "fetch"])
def test_cdp_deny_unknown_value_fails_daemon_start(monkeypatch, value):
    monkeypatch.setenv("BH_CDP_DENY", value)

    with pytest.raises(ValueError, match="BH_CDP_DENY"):
        daemon.Daemon()


def test_cdp_deny_tokens_survives_respawn_without_env(monkeypatch, _isolated_deny_marker):
    """A later CLI call that respawns the daemon without BH_CDP_DENY keeps tokens mode."""
    monkeypatch.setenv("BH_CDP_DENY", "tokens")
    daemon.persist_cdp_deny_mode(daemon.Daemon().deny)
    monkeypatch.delenv("BH_CDP_DENY")

    respawned = daemon.Daemon()

    assert respawned.deny == "tokens"
    assert _isolated_deny_marker.read_text() == "tokens"


def test_cdp_deny_off_clears_sticky_mode(monkeypatch, _isolated_deny_marker):
    _isolated_deny_marker.write_text("tokens")
    monkeypatch.setenv("BH_CDP_DENY", "off")

    d = daemon.Daemon()
    daemon.persist_cdp_deny_mode(d.deny)
    monkeypatch.delenv("BH_CDP_DENY")

    assert d.deny is None
    assert not _isolated_deny_marker.exists()
    assert daemon.Daemon().deny is None


def test_cdp_deny_corrupt_marker_fails_closed(monkeypatch, _isolated_deny_marker):
    _isolated_deny_marker.write_text("garbage")
    monkeypatch.delenv("BH_CDP_DENY", raising=False)

    with pytest.raises(ValueError, match="garbage"):
        daemon.Daemon()


def test_cdp_deny_tokens_keeps_discovery_events_out_of_drain(monkeypatch):
    """Discovery is daemon-internal in tokens mode; it must not evict Network events."""
    d = _deny_daemon(monkeypatch, "tokens")
    d._record_event("Target.targetInfoChanged", {"targetInfo": {**_PAGE, "title": "x"}})
    d._record_event("Target.targetCreated", {"targetInfo": {"targetId": "t2", "type": "page", "url": "about:blank"}})

    assert _drain(d) == []
    assert d._targets["t2"]["url"] == "about:blank"
