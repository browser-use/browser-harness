import asyncio

import pytest

from browser_harness import daemon


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


def test_shutdown_leaves_dedicated_tab_open(monkeypatch):
    """The real serve shutdown path never closes a working or user tab."""
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

    assert d.cdp.closed == []
    assert d.dedicated_target_id == "daemon-tab"
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
