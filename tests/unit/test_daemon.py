import asyncio
import urllib.error

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


def test_cdp_open_timeout_defaults_to_long_local_permission_window(monkeypatch):
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.delenv("BH_CDP_OPEN_TIMEOUT_SECONDS", raising=False)

    assert daemon._cdp_open_timeout_seconds() == daemon.LOCAL_CDP_OPEN_TIMEOUT_SECONDS


def test_cdp_open_timeout_uses_shorter_default_for_explicit_remote_endpoint(monkeypatch):
    monkeypatch.setenv("BU_CDP_WS", "ws://example.test/devtools/browser/1")
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.delenv("BH_CDP_OPEN_TIMEOUT_SECONDS", raising=False)

    assert daemon._cdp_open_timeout_seconds() == daemon.REMOTE_CDP_OPEN_TIMEOUT_SECONDS


def test_cdp_open_timeout_honors_env_override(monkeypatch):
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv("BH_CDP_OPEN_TIMEOUT_SECONDS", "42")

    assert daemon._cdp_open_timeout_seconds() == 42


def test_local_browser_mode_defaults_to_auto(monkeypatch):
    monkeypatch.delenv("BH_LOCAL_BROWSER_MODE", raising=False)

    assert daemon._local_browser_mode() == "auto"


def test_local_browser_mode_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("BH_LOCAL_BROWSER_MODE", "surprise")

    assert daemon._local_browser_mode() == "auto"


def test_default_profile_ws_fallback_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("BH_LOCAL_BROWSER_MODE", "auto")
    monkeypatch.delenv("BH_ALLOW_DEFAULT_PROFILE_REMOTE", raising=False)

    assert not daemon._use_default_profile_ws_fallback()

    monkeypatch.setenv("BH_ALLOW_DEFAULT_PROFILE_REMOTE", "1")

    assert daemon._use_default_profile_ws_fallback()


def test_dedicated_browser_ports_prefers_env_override(monkeypatch):
    monkeypatch.setenv("BH_DEDICATED_CHROME_PORT", "9444")

    assert daemon._dedicated_browser_ports()[0] == 9444


def test_get_ws_url_uses_dedicated_browser_when_requested(monkeypatch):
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv("BH_LOCAL_BROWSER_MODE", "dedicated")
    monkeypatch.setattr(daemon, "_dedicated_browser_ws_url", lambda: "ws://dedicated")

    assert daemon.get_ws_url() == "ws://dedicated"


def test_get_ws_url_uses_dedicated_browser_instead_of_default_profile_404(monkeypatch, tmp_path):
    profile = tmp_path / "Chrome"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/default-profile\n")

    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv("BH_LOCAL_BROWSER_MODE", "auto")
    monkeypatch.delenv("BH_ALLOW_DEFAULT_PROFILE_REMOTE", raising=False)
    monkeypatch.setattr(daemon, "PROFILES", [profile])
    monkeypatch.setattr(daemon, "_dedicated_browser_ws_url", lambda: "ws://dedicated")

    def fake_urlopen(url, timeout=1):
        raise urllib.error.HTTPError(url, 404, "not found", None, None)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", fake_urlopen)

    assert daemon.get_ws_url() == "ws://dedicated"


def test_get_ws_url_allows_default_profile_ws_when_opted_in(monkeypatch, tmp_path):
    profile = tmp_path / "Chrome"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/default-profile\n")

    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv("BH_LOCAL_BROWSER_MODE", "default")
    monkeypatch.setattr(daemon, "PROFILES", [profile])

    def fake_urlopen(url, timeout=1):
        raise urllib.error.HTTPError(url, 404, "not found", None, None)

    monkeypatch.setattr(daemon.urllib.request, "urlopen", fake_urlopen)

    assert daemon.get_ws_url() == "ws://127.0.0.1:9222/devtools/browser/default-profile"


def test_start_cdp_client_passes_open_timeout_to_websocket(monkeypatch):
    calls = []

    class FakeCDPClient:
        def __init__(self, url):
            self.url = url
            self.max_ws_frame_size = 12345
            self.additional_headers = None
            self.ws = None
            self._message_handler_task = None

        async def _handle_messages(self):
            return None

    async def fake_connect(url, **kwargs):
        calls.append((url, kwargs))
        return "fake-ws"

    monkeypatch.setattr(daemon, "CDPClient", FakeCDPClient)
    monkeypatch.setattr(daemon.websockets, "connect", fake_connect)

    client = asyncio.run(daemon._start_cdp_client("ws://127.0.0.1:9222/devtools/browser/1", open_timeout=120))

    assert client.ws == "fake-ws"
    assert calls == [
        (
            "ws://127.0.0.1:9222/devtools/browser/1",
            {"max_size": 12345, "open_timeout": 120},
        )
    ]


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
