import asyncio

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
