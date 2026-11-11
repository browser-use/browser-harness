"""solve_captcha(): helpers.py polling a real Daemon whose CDP is a fake Browser Use Cloud solver."""
import asyncio
import threading
import time

import pytest

from browser_harness import daemon, helpers

STARTED, FINISHED, CHANGED = (f"BrowserUse.captchaSolver{e}" for e in ("Started", "Finished", "StateChanged"))
DEMO = "https://www.google.com/recaptcha/api2/demo"


class _SolverCDP:
    """BrowserUse.get/setCaptchaSolverEnabled with a cloud browser's StateChanged events, or Chrome's -32601."""

    def __init__(self, d, enabled=True, available=True):
        self.d, self.enabled, self.available, self.sets = d, enabled, available, []

    async def send_raw(self, method, params=None, session_id=None):
        if not self.available:
            raise RuntimeError(f"{{'code': -32601, 'message': \"'{method}' wasn't found\"}}")
        if method == "BrowserUse.getCaptchaSolverEnabled":
            return {"enabled": self.enabled}
        self.enabled = params["enabled"]
        self.sets.append(self.enabled)
        self.d._record_event(CHANGED, {"enabled": self.enabled})
        return {"enabled": self.enabled}


@pytest.fixture
def solver(monkeypatch):
    """A daemon on its own loop thread; helpers._send goes to it as over IPC."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    d = daemon.Daemon()
    d.cdp = _SolverCDP(d)

    def send(req, response_timeout=5.0):
        r = asyncio.run_coroutine_threadsafe(d.handle(req), loop).result(response_timeout)
        if "error" in r:
            raise RuntimeError(r["error"])
        return r

    def event(method, target="T1", **params):
        asyncio.run_coroutine_threadsafe(_record(d, method, {"targetId": target, **params}), loop).result(1)

    monkeypatch.setattr(helpers, "_send", send)
    d.event = event
    yield d
    loop.call_soon_threadsafe(loop.stop)


async def _record(d, method, params):
    d._record_event(method, params)
    await asyncio.sleep(0.01)  # let a switch-off task run


def _in_thread(**kwargs):
    out = {}
    t = threading.Thread(target=lambda: out.update(helpers.solve_captcha(**kwargs)))
    t.start()
    return t, out


def _until(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < end, "condition not met"
        time.sleep(0.01)


def test_local_browser_reports_solver_unavailable(solver):
    solver.cdp.available = False
    r = helpers.solve_captcha()
    assert r["solved"] is False
    assert r["detail"] == "solver unavailable: this browser has no captcha solver (Browser Use Cloud browsers do)"


def test_no_solve_started_leaves_an_enabled_solver_on(solver):
    r = helpers.solve_captcha(start_timeout=0.3)
    assert (r["solved"], r["detail"]) == (False, "no captcha solve started within 0.3 s")
    assert solver.cdp.sets == [] and solver.cdp.enabled is True


def test_solve_that_finished_before_the_call_is_returned_once(solver):
    solver.event(STARTED, vendor="recaptcha", url=DEMO)
    solver.event(FINISHED, vendor="recaptcha", url=DEMO, success=True)
    r = helpers.solve_captcha(start_timeout=0.3)
    assert {k: r[k] for k in ("solved", "detail", "vendor", "url")} == {
        "solved": True, "detail": "solved", "vendor": "recaptcha", "url": DEMO,
    }
    assert helpers.solve_captcha(start_timeout=0.3)["detail"] == "no captcha solve started within 0.3 s"


def test_waits_for_a_running_solve(solver):
    solver.event(STARTED, vendor="cloudflare")
    t, out = _in_thread(start_timeout=0.3, timeout=5)
    time.sleep(0.6)  # past start_timeout: a running solve waits for the overall timeout
    solver.event(FINISHED, vendor="cloudflare", success=True)
    t.join(3)
    assert (out["solved"], out["detail"], out["vendor"]) == (True, "solved", "cloudflare")


def test_failure_on_any_page_wins(solver):
    solver.event(STARTED, "A"), solver.event(STARTED, "B", url="https://b.test/")
    solver.event(FINISHED, "B", url="https://b.test/", success=False)
    solver.event(FINISHED, "A", url="https://a.test/", success=True)
    r = helpers.solve_captcha()
    assert (r["solved"], r["detail"], r["url"]) == (False, "the solver failed", "https://b.test/")


def test_solve_with_no_finish_ends_as_lost(solver, monkeypatch):
    monkeypatch.setattr(daemon, "CAPTCHA_LOST_S", 0.3)
    solver.event(STARTED, vendor="datadome")
    r = helpers.solve_captcha(timeout=5)
    assert (r["solved"], r["detail"], r["vendor"]) == (False, "no result from the solver after 150 s", "datadome")


def test_switches_a_disabled_solver_on_and_back_off(solver):
    solver.cdp.enabled = False
    t, out = _in_thread(timeout=5)
    _until(lambda: solver.cdp.sets == [True])
    solver.event(STARTED), solver.event(FINISHED, success=True)
    t.join(3)
    assert out["detail"] == "solved"
    _until(lambda: solver.cdp.sets == [True, False])


def test_no_solve_started_switches_its_own_enable_back_off(solver):
    solver.cdp.enabled = False
    assert helpers.solve_captcha(start_timeout=0.3)["detail"] == "no captcha solve started within 0.3 s"
    _until(lambda: solver.cdp.sets == [True, False])


def test_still_solving_keeps_the_solver_on_until_the_finish(solver):
    solver.cdp.enabled = False
    t, out = _in_thread(timeout=0.5)
    _until(lambda: solver.cdp.sets == [True])
    solver.event(STARTED, vendor="hcaptcha")
    t.join(3)
    assert (out["solved"], out["detail"], out["vendor"], out["next"]) == (
        False, "still solving", "hcaptcha", "call solve_captcha() again",
    )
    assert solver.cdp.enabled is True
    solver.event(FINISHED, success=True)  # no caller waiting: the finish still turns it off
    _until(lambda: solver.cdp.enabled is False)
    assert helpers.solve_captcha()["detail"] == "solved"


def test_someone_else_switching_it_off_drops_ownership(solver):
    solver.cdp.enabled = False
    t, out = _in_thread(timeout=5)
    _until(lambda: solver.cdp.sets == [True])
    solver.event(STARTED)
    solver.event(CHANGED, enabled=False)  # another client turned it off, then on again
    solver.event(FINISHED, success=True)
    t.join(3)
    assert out["detail"] == "solved"
    assert solver.cdp.sets == [True]  # not switched off on their behalf


def test_concurrent_callers_share_one_result(solver):
    solver.event(STARTED)
    (t1, a), (t2, b) = _in_thread(timeout=5), _in_thread(timeout=5)
    time.sleep(0.3)
    solver.event(FINISHED, success=True)
    t1.join(3), t2.join(3)
    assert a["detail"] == b["detail"] == "solved"
