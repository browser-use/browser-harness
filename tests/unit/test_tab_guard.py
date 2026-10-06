"""Tab guard: an unattended run may act only on tabs it opened (BH_TAB_GUARD=1)."""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

import pytest

from browser_harness import daemon, helpers


FOREIGN = {"targetId": "FOREIGN", "url": "https://mail.example.com/", "title": "Inbox"}
RUN_ID = "123e4567-e89b-42d3-a456-426614174000"
RUN_ID_2 = "123e4567-e89b-42d3-a456-426614174001"
RUN_ID_3 = "123e4567-e89b-42d3-a456-426614174002"
SRC_DIR = pathlib.Path(__file__).resolve().parents[2] / "src"


def _subprocess_env(**updates):
    """Give src-layout subprocesses the same import path as the test runner."""
    pythonpath = os.pathsep.join(
        path for path in (str(SRC_DIR), os.environ.get("PYTHONPATH", "")) if path
    )
    return {**os.environ, "PYTHONPATH": pythonpath, **updates}


def _fake_send(current=FOREIGN, created="MINE", session="SESSION-MINE", target_type="page"):
    def send(req, response_timeout=None):
        if req.get("meta") == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": 0}
        if req.get("meta") == "tab_guard_reset":
            return {"tab_guard": "ok", "tab_guard_run": req.get("tab_guard_run")}
        if req.get("meta") == "guard_context":
            target_id = req.get("target_id", current["targetId"])
            return {"target_id": target_id,
                    "session_id": session if target_id == current["targetId"] else None,
                    "url": current.get("url", ""), "tab_guard": "ok",
                    "tab_guard_epoch": 0, "document_generation": 0}
        if req.get("meta") == "current_tab":
            return {**current, "tab_guard": "ok"}
        method = req.get("method")
        if method == "Target.createBrowserContext":
            return {"result": {"browserContextId": "CONTEXT-MINE"}}
        if method == "Target.createTarget":
            return {"result": {"targetId": created}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": session}}
        if method == "Target.getTargetInfo":
            return {"result": {"targetInfo": {"type": target_type, "url": current.get("url", "")}}}
        return {"result": {}}
    return send


@pytest.fixture
def guard(tmp_path, monkeypatch):
    """Guard on, ownership isolated to tmp_path, daemon attached to a tab this
    run did not open."""
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    monkeypatch.setenv("BH_TAB_GUARD_RUN", RUN_ID)
    monkeypatch.delenv("BH_TAB_GUARD_LOG", raising=False)
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(helpers, "_send", _fake_send())
    helpers.tab_guard_reset()


@pytest.fixture
def owning(guard, monkeypatch):
    """As `guard`, but the run has opened a tab and the daemon is attached to it."""
    assert helpers.cdp("Target.createTarget", url="about:blank")["targetId"] == "MINE"
    helpers.cdp("Target.attachToTarget", targetId="MINE", flatten=True)
    monkeypatch.setattr(helpers, "_send", _fake_send(current={"targetId": "MINE", "url": "https://example.com/", "title": "t"}))


# --- refusals -------------------------------------------------------------

def test_refuses_navigating_a_tab_the_run_did_not_open(guard, capsys):
    with pytest.raises(helpers.TabGuardRefused):
        helpers.goto_url("https://example.com/")
    assert "[tab-guard] REFUSED Page.navigate FOREIGN https://example.com/" in capsys.readouterr().err


def test_send_normalizes_and_labels_daemon_guard_refusal(monkeypatch, tmp_path):
    class Connection:
        def settimeout(self, _timeout):
            pass
        def close(self):
            pass

    monkeypatch.setenv("BH_TAB_GUARD_LOG", str(tmp_path / "guard.log"))
    monkeypatch.setattr(helpers.ipc, "connect", lambda *a, **k: (Connection(), "token"))
    monkeypatch.setattr(helpers.ipc, "request", lambda *a, **k: {
        "tab_guard": "refused", "error": "tab guard authorization is stale or invalid",
    })
    with pytest.raises(helpers.TabGuardRefused) as exc:
        helpers._send({"method": "Runtime.evaluate"})
    assert exc.value.source == "daemon"
    assert "REFUSED (daemon) Runtime.evaluate" in str(exc.value)
    assert "REFUSED (daemon) Runtime.evaluate" in (tmp_path / "guard.log").read_text()


def test_refuses_closing_and_activating_someone_elses_tab(guard):
    for method in ("Target.closeTarget", "Target.activateTarget", "Target.attachToTarget"):
        with pytest.raises(helpers.TabGuardRefused):
            helpers.cdp(method, targetId="FOREIGN")


@pytest.mark.parametrize("call,label", [
    (lambda: helpers.js("location.href='https://example.com'"), "js navigation"),
    (lambda: helpers.js("document.querySelector('button').click()"), "js click"),
    (lambda: helpers.page_info(), "page_info"),
    (lambda: helpers.capture_screenshot(), "screenshot"),
    (lambda: helpers.type_text("hello"), "type_text"),
    (lambda: helpers.press_key("Enter"), "press_key"),
    (lambda: helpers.click_at_xy(10, 10), "click_at_xy"),
    (lambda: helpers.scroll(0, 0), "scroll"),
    (lambda: helpers.cdp("DOM.setFileInputFiles", files=["/etc/passwd"]), "DOM.setFileInputFiles"),
    (lambda: helpers.cdp("Page.setDocumentContent", html="<h1>x</h1>"), "Page.setDocumentContent"),
])
def test_refuses_every_session_scoped_call_on_a_foreign_tab(guard, call, label):
    """The reason this is an allowlist. A blocklist of "mutating" methods misses
    Runtime.evaluate, and js() is the ordinary fallback for a blocked click —
    so the guard would look present while being trivially bypassable."""
    with pytest.raises(helpers.TabGuardRefused):
        call()


def test_fails_closed_when_the_attached_tab_cannot_be_read(tmp_path, monkeypatch):
    """"Unknown" must not mean "permitted": treating an unreadable current tab
    as nothing-to-refuse turns any daemon hiccup into a bypass."""
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    monkeypatch.setenv("BH_TAB_GUARD_RUN", RUN_ID)
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(
        helpers, "_send",
        lambda req, **kwargs: ({"tab_guard": "ok", "tab_guard_epoch": 0}
                               if req.get("meta") == "guard_epoch" else
                               {"tab_guard": "ok", "tab_guard_run": req.get("tab_guard_run")}),
    )
    helpers.tab_guard_reset()

    def flaky(req, response_timeout=None):
        if req.get("meta") == "guard_context":
            raise RuntimeError("daemon unreachable")
        return {"result": {}}

    monkeypatch.setattr(helpers, "_send", flaky)
    with pytest.raises(helpers.TabGuardRefused) as exc:
        helpers.goto_url("https://example.com/")
    assert "failing closed" in str(exc.value)


# --- what must still work -------------------------------------------------

def test_allows_everything_on_a_tab_the_run_opened(owning):
    helpers.goto_url("https://example.com/page")
    helpers.js("document.title")
    helpers.type_text("hi")
    helpers.cdp("Target.closeTarget", targetId="MINE")


@pytest.mark.parametrize("method", [
    "Emulation.setEmulatedMedia", "Network.enable", "Page.bringToFront", "Page.reload",
])
def test_owned_page_scope_allowlist_remains_allowed(owning, method):
    helpers.cdp(method)


def test_allows_enumerating_tabs_without_attaching(guard):
    """Refusing reads on a foreign tab costs a run nothing, because
    Target.getTargets still answers "what else is open?"."""
    helpers.cdp("Target.getTargets")
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.getTargetInfo", targetId="FOREIGN")


@pytest.mark.parametrize("method,params", [
    ("Target.createTarget", {"url": "chrome://settings"}),
    ("Target.createTarget", {"url": "devtools://devtools/bundled/inspector.html"}),
    ("Target.createTarget", {"url": "browser://settings"}),
    ("Target.createTarget", {"url": "javascript:alert(1)"}),
    ("Target.createTarget", {"url": "file:///etc/passwd"}),
    ("Target.createTarget", {"url": "data:text/html,<h1>x</h1>"}),
    ("Target.createTarget", {"url": "ftp://example.com/file"}),
    ("Page.navigate", {"url": "chrome://settings"}),
    ("Page.navigate", {"url": "devtools://devtools/bundled/inspector.html"}),
    ("Page.navigate", {"url": "browser://settings"}),
    ("Page.navigate", {"url": "javascript:alert(1)"}),
    ("Page.navigate", {"url": "file:///etc/passwd"}),
    ("Page.navigate", {"url": "data:text/html,<h1>x</h1>"}),
    ("Page.navigate", {"url": "ftp://example.com/file"}),
])
def test_guard_rejects_privileged_urls_before_transport(owning, monkeypatch, method, params):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req))
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(method, **params)
    assert calls == []


@pytest.mark.parametrize("url", [
    "chrome://settings", "devtools://devtools/bundled/inspector.html",
    "browser://settings", "javascript:alert(1)", "file:///etc/passwd",
    "data:text/html,<h1>x</h1>", "ftp://example.com/file",
])
def test_nested_navigation_rejects_privileged_urls_before_transport(owning, monkeypatch, url):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req))
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="SESSION-MINE",
            message=json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}),
        )
    assert calls == []


def test_guard_rejects_interaction_with_privileged_current_target(owning, monkeypatch):
    calls = []
    fake = _fake_send(current={"targetId": "MINE", "url": "chrome://settings"})
    def send(req, **kwargs):
        calls.append(req)
        return fake(req, **kwargs)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Runtime.evaluate", expression="document.title")
    assert not any(req.get("method") for req in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_guard_rejects_explicit_owned_session_on_privileged_current_target(owning, monkeypatch, nested):
    calls = []
    fake = _fake_send(current={"targetId": "MINE", "url": "chrome://settings"})
    def send(req, **kwargs):
        calls.append(req)
        return fake(req, **kwargs)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        if nested:
            helpers.cdp(
                "Target.sendMessageToTarget",
                sessionId="SESSION-MINE",
                message=json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
            )
        else:
            helpers.cdp("Runtime.evaluate", session_id="SESSION-MINE", expression="document.title")
    assert not any(req.get("method") for req in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_guard_rejects_explicit_owned_session_mismatch_before_dispatch(owning, monkeypatch, nested):
    calls = []
    fake = _fake_send(current={"targetId": "MINE", "url": "https://current.example/"}, session="OTHER-SESSION")
    def send(req, **kwargs):
        calls.append(req)
        return fake(req, **kwargs)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        if nested:
            helpers.cdp(
                "Target.sendMessageToTarget",
                sessionId="SESSION-MINE",
                message=json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": "https://next.example/"}}),
            )
        else:
            helpers.cdp("Page.navigate", session_id="SESSION-MINE", url="https://next.example/")
    assert not any(req.get("method") for req in calls)


def test_refuses_non_page_targets_without_owned_ancestry(owning, monkeypatch):
    monkeypatch.setattr(helpers, "_send", _fake_send(
        current={"targetId": "MINE"}, target_type="iframe"))
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.attachToTarget", targetId="FOREIGN-IFRAME", flatten=True)


def test_allows_a_session_this_run_attached_and_refuses_one_it_did_not(owning):
    sid = helpers.cdp("Target.attachToTarget", targetId="MINE", flatten=True)["sessionId"]
    helpers.cdp("Runtime.evaluate", session_id=sid, expression="1")  # ours: fine
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Runtime.evaluate", session_id="SOMEONE-ELSES", expression="1")


def test_new_tab_does_not_reuse_a_blank_tab_the_run_does_not_own(guard):
    """Upstream new_tab() navigates the attached tab when it is blank. A blank
    tab is still someone's tab, so under the guard a fresh one is always made."""
    assert helpers._may_reuse_attached_tab() is False


def test_guarded_new_tab_skips_unowned_unmark_and_attaches_fresh_target(guard, monkeypatch):
    requests = []
    current = {"targetId": "FOREIGN", "url": "https://mail.example.com/", "title": "Inbox"}
    base = _fake_send(current=current)

    def send(req, **kwargs):
        requests.append(req)
        if req.get("meta") == "guard_context":
            target_id = req.get("target_id", current["targetId"])
            return {
                "target_id": target_id,
                "session_id": "SESSION-MINE" if target_id == current["targetId"] else None,
                "url": current.get("url", ""),
                "tab_guard": "ok",
                "tab_guard_epoch": 0,
                "document_generation": 0,
            }
        if req.get("meta") == "set_session":
            current.update({"targetId": "MINE", "url": "about:blank", "title": ""})
            return {"session_id": "SESSION-MINE", "url": "about:blank", "tab_guard": "ok"}
        return base(req, **kwargs)

    monkeypatch.setattr(helpers, "_send", send)
    assert helpers.new_tab("https://new.example/") == "MINE"
    methods = [req.get("method") for req in requests if req.get("method")]
    assert methods.index("Target.attachToTarget") < methods.index("Runtime.evaluate")
    assert not any(
        req.get("method") == "Runtime.evaluate"
        for req in requests[:methods.index("Target.attachToTarget")]
    )


def test_new_tab_may_still_reuse_a_blank_tab_the_run_opened(owning):
    assert helpers._may_reuse_attached_tab() is True


def test_guard_off_by_default_leaves_every_tab_reachable(tmp_path, monkeypatch):
    monkeypatch.delenv("BH_TAB_GUARD", raising=False)
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(helpers, "_send", _fake_send())
    helpers.goto_url("https://example.com/")
    helpers.js("document.title")
    assert helpers._may_reuse_attached_tab() is True


# --- ownership bookkeeping ------------------------------------------------

def test_ownership_is_scoped_to_the_run_id(guard, monkeypatch):
    monkeypatch.setenv("BH_TAB_GUARD_RUN", RUN_ID)
    helpers.cdp("Target.createTarget", url="about:blank")
    assert helpers._owned_ids() == {"MINE"}
    monkeypatch.setenv("BH_TAB_GUARD_RUN", RUN_ID_2)
    assert helpers._owned_ids() == set()
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.closeTarget", targetId="MINE")


def test_a_concurrent_run_cannot_consume_this_run_s_ownership(guard, monkeypatch):
    """Two harness users commonly share a daemon name (the default is
    "default"). A single shared state file let one overwrite the other's tabs,
    which refuses a run on its own tab mid-task."""
    helpers.cdp("Target.createTarget", url="about:blank")
    assert helpers._owned_ids() == {"MINE"}
    monkeypatch.setenv("BH_TAB_GUARD_RUN", "")   # a different (unguarded) user
    monkeypatch.delenv("BH_TAB_GUARD")
    helpers._own_tab("THEIRS")
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    monkeypatch.setenv("BH_TAB_GUARD_RUN", RUN_ID)
    assert helpers._owned_ids() == {"MINE"}


def test_ownership_crosses_a_process_boundary(guard, tmp_path):
    """One run is usually several harness invocations, so ownership must survive
    a real process exit — which an in-process assertion cannot demonstrate."""
    helpers.cdp("Target.createTarget", url="about:blank")
    script = (
        "import pathlib, json\n"
        "from browser_harness import helpers\n"
        f"helpers.ipc._TMP = pathlib.Path({str(tmp_path)!r})\n"
        "print(json.dumps(sorted(helpers._owned_ids())))\n"
    )
    env = _subprocess_env(BH_TAB_GUARD="1", BH_TAB_GUARD_RUN=RUN_ID)
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["MINE"]


def test_a_failed_ownership_write_is_reported_not_swallowed(guard, monkeypatch, capsys):
    """Silence here would present a disk problem as a guard bug: the run would
    be refused on tabs it did open, with nothing saying why."""
    monkeypatch.setattr(helpers, "_owned_path", lambda: pathlib.Path("/nonexistent-dir/owned.json"))
    helpers._own_tab("MINE")
    assert "[tab-guard] WARNING could not record ownership of MINE" in capsys.readouterr().err


def test_corrupt_ownership_state_reads_as_empty_rather_than_crashing(guard):
    helpers._owned_path().write_text("{not json")
    assert helpers._owned_ids() == set()
    helpers._owned_path().write_text('["legacy-list-form"]')
    assert helpers._owned_ids() == set()


# --- refusal reporting ----------------------------------------------------

def test_refusal_is_appended_to_BH_TAB_GUARD_LOG(guard, tmp_path, monkeypatch):
    """A supervisor counting refusals usually cannot see this process's stderr —
    it is a grandchild whose output is captured by whatever spawned it."""
    log = tmp_path / "run.log"
    monkeypatch.setenv("BH_TAB_GUARD_LOG", str(log))
    with pytest.raises(helpers.TabGuardRefused):
        helpers.goto_url("https://example.com/")
    assert "[tab-guard] REFUSED Page.navigate FOREIGN https://example.com/" in log.read_text()


def test_an_unwritable_log_does_not_swallow_the_refusal(guard, monkeypatch):
    monkeypatch.setenv("BH_TAB_GUARD_LOG", "/nonexistent-dir/run.log")
    with pytest.raises(helpers.TabGuardRefused):
        helpers.goto_url("https://example.com/")


@pytest.mark.parametrize("run_id", [None, "", " \t\n", "test-run", "job-42"])
def test_guard_requires_nonempty_run_before_any_dispatch(guard, monkeypatch, run_id):
    if run_id is None:
        monkeypatch.delenv("BH_TAB_GUARD_RUN")
    else:
        monkeypatch.setenv("BH_TAB_GUARD_RUN", run_id)
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kw: calls.append(req))
    for method in ("Target.createTarget", "Target.getTargets", "Runtime.evaluate"):
        with pytest.raises(helpers.TabGuardRefused, match="BH_TAB_GUARD_RUN"):
            helpers.cdp(method)
    assert calls == []


@pytest.mark.parametrize("first,second", [(RUN_ID, RUN_ID_2), (RUN_ID, RUN_ID_3)])
def test_distinct_valid_run_ids_cannot_share_ownership(guard, monkeypatch, first, second):
    monkeypatch.setenv("BH_TAB_GUARD_RUN", first)
    helpers._own_tab("MINE")
    first_path = helpers._owned_path()
    monkeypatch.setenv("BH_TAB_GUARD_RUN", second)
    assert helpers._owned_path() != first_path
    assert helpers._owned_ids() == set()


@pytest.mark.parametrize("run_id", [
    "test-run", "job-42", "12345678-1234-1234-1234-123456789abc",
    "123e4567-e89b-42d3-0456-426614174000",
])
def test_low_entropy_run_ids_are_rejected_before_ownership_path_access(guard, monkeypatch, run_id):
    monkeypatch.setenv("BH_TAB_GUARD_RUN", run_id)
    monkeypatch.setattr(helpers, "_owned_path", lambda: pytest.fail("invalid run IDs must not resolve a path"))
    with pytest.raises(helpers.TabGuardRefused, match="canonical UUID4"):
        helpers.cdp("Target.getTargets")


def test_daemon_names_are_part_of_ownership_key_even_in_custom_tmp(guard, monkeypatch):
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR", "custom")
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR_SHARED", False)
    helpers._own_tab("MINE")
    monkeypatch.setattr(helpers, "NAME", "another-daemon")
    assert helpers._owned_ids() == set()


def test_detach_checks_parameter_session_and_forgets_it(owning):
    helpers.cdp("Target.detachFromTarget", sessionId="SESSION-MINE")
    assert "SESSION-MINE" not in helpers._owned_sessions()
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Runtime.evaluate", session_id="SESSION-MINE", expression="1")


def test_create_and_attach_record_new_ownership(guard):
    assert helpers._owned_ids() == set()
    assert helpers._owned_sessions() == set()
    assert helpers.cdp("Target.createTarget")["targetId"] == "MINE"
    assert helpers._owned_ids() == {"MINE"}
    assert helpers.cdp("Target.attachToTarget", targetId="MINE")["sessionId"] == "SESSION-MINE"
    assert helpers._owned_sessions() == {"SESSION-MINE"}


def test_create_target_is_pinned_to_a_run_owned_browser_context(guard, monkeypatch):
    requests = []
    original = helpers._send

    def send(req, **kwargs):
        requests.append(req)
        return original(req, **kwargs)

    monkeypatch.setattr(helpers, "_send", send)
    result = helpers.cdp("Target.createTarget", url="about:blank")
    assert result["targetId"] == "MINE"
    assert helpers._owned_contexts() == {"CONTEXT-MINE"}
    create = next(req for req in requests if req.get("method") == "Target.createTarget")
    assert create["params"]["browserContextId"] == "CONTEXT-MINE"


def test_first_create_target_does_not_resolve_the_foreign_current_session(guard, monkeypatch):
    requests = []

    def send(req, **kwargs):
        requests.append(req)
        if req.get("meta") == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": 0}
        if req.get("meta") == "guard_context":
            pytest.fail("global createTarget bootstrap must not inspect the current tab")
        if req.get("method") == "Target.createBrowserContext":
            return {"result": {"browserContextId": "CONTEXT-MINE"}}
        if req.get("method") == "Target.createTarget":
            return {"result": {"targetId": "MINE"}}
        raise AssertionError(req)

    monkeypatch.setattr(helpers, "_send", send)
    assert helpers.cdp("Target.createTarget", url="about:blank")["targetId"] == "MINE"
    assert helpers._owned_ids() == {"MINE"}
    assert helpers._owned_contexts() == {"CONTEXT-MINE"}
    assert all(req.get("tab_guard_session_id") is None for req in requests
               if req.get("method") in {"Target.createBrowserContext", "Target.createTarget"})


@pytest.mark.parametrize("context_id", ["FOREIGN-CONTEXT", None])
def test_create_target_rejects_a_foreign_or_default_context_before_dispatch(
    owning, monkeypatch, context_id
):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req) or {"result": {}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.createTarget", url="about:blank", browserContextId=context_id)
    assert calls == []


def test_nested_create_target_cannot_bypass_context_ownership(owning, monkeypatch):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req) or {"result": {}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="SESSION-MINE",
            message=json.dumps({
                "id": 1,
                "method": "Target.createTarget",
                "params": {"url": "about:blank", "browserContextId": "FOREIGN-CONTEXT"},
            }),
        )
    assert calls == []


def test_removal_is_noop_only_when_value_is_absent(guard):
    helpers._own_tab("MINE")
    helpers._remember("tabs", "MINE", remove=True)
    assert helpers._owned_ids() == set()
    helpers._remember("tabs", "MINE", remove=True)
    assert helpers._owned_ids() == set()


def test_addition_is_noop_only_when_value_is_present(guard):
    helpers._own_tab("MINE")
    helpers._own_tab("MINE")
    assert helpers._owned_ids() == {"MINE"}


@pytest.mark.parametrize("params", [
    {}, {"sessionId": "FOREIGN"}, {"targetId": "MINE"},
    {"sessionId": "FOREIGN", "targetId": "MINE"},
])
@pytest.mark.parametrize("method", ["Target.detachFromTarget", "Target.sendMessageToTarget"])
def test_routing_params_cannot_borrow_current_or_explicit_session(owning, params, method):
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(method, session_id="SESSION-MINE", **params)


def test_send_message_to_owned_session_works(owning):
    helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE",
                message=json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1"}}))


@pytest.mark.parametrize("nested", [False, True])
def test_guarded_dispatch_carries_run_session_target_epoch_and_generation(owning, monkeypatch, nested):
    calls = []

    def send(req, **kwargs):
        calls.append(req)
        if req.get("meta") == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": 7, "tab_guard_run": RUN_ID}
        if req.get("meta") == "guard_context":
            return {
                "target_id": "MINE", "session_id": "SESSION-MINE",
                "url": "https://example.com/", "tab_guard": "ok",
                "tab_guard_epoch": 7, "document_generation": 3,
            }
        return {"result": {}}

    monkeypatch.setattr(helpers, "_send", send)
    if nested:
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="SESSION-MINE",
            message=json.dumps({"id": 11, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
        )
    else:
        helpers.cdp("Runtime.evaluate", session_id="SESSION-MINE", expression="1")
    dispatched = next(req for req in calls if req.get("method"))
    assert dispatched["tab_guard_run"] == RUN_ID
    assert dispatched["tab_guard_target_id"] == "MINE"
    assert dispatched["tab_guard_session_id"] == "SESSION-MINE"
    assert dispatched["tab_guard_epoch"] == 7
    assert dispatched["tab_guard_document_generation"] == 3


def test_nested_message_cannot_route_to_foreign_target(owning):
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE",
                    message=json.dumps({"id": 1, "method": "Target.attachToTarget", "params": {"targetId": "FOREIGN"}}))


@pytest.mark.parametrize("method", [
    "Target.exposeDevToolsProtocol",
    "ServiceWorker.enable",
    "Storage.trackIndexedDBForOrigin",
    "Network.getAllCookies",
    "Network.clearBrowserCookies",
    "Network.clearBrowserCache",
    "Network.getCookies",
    "Network.setCookies",
    "Storage.getCookies",
    "Storage.clearDataForOrigin",
    "Browser.getVersion",
    "SystemInfo.getProcessInfo",
])
def test_guard_refuses_browser_and_context_wide_methods_before_dispatch(owning, monkeypatch, method):
    calls = []
    original = helpers._send
    def send(req, **kwargs):
        calls.append(req)
        return original(req, **kwargs)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(method, targetId="MINE")
    assert calls == []


@pytest.mark.parametrize("method", [
    "Network.getAllCookies", "Network.clearBrowserCookies",
    "ServiceWorker.enable", "Storage.trackIndexedDBForOrigin",
    "Target.exposeDevToolsProtocol",
])
def test_nested_message_applies_browser_scope_policy_before_dispatch(owning, monkeypatch, method):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req) or {"result": {}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="SESSION-MINE",
            message=json.dumps({"id": 1, "method": method, "params": {}}),
        )
    assert calls == []


def test_create_isolated_world_is_not_guarded_page_scope(owning, monkeypatch):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req) or {"result": {}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Page.createIsolatedWorld", frameId="frame", grantUniveralAccess=True)
    assert calls == []


def test_nested_create_isolated_world_is_not_guarded_page_scope(owning, monkeypatch):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req) or {"result": {}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="SESSION-MINE",
            message=json.dumps({
                "id": 1,
                "method": "Page.createIsolatedWorld",
                "params": {"frameId": "frame", "grantUniveralAccess": True},
            }),
        )
    assert calls == []


def test_nested_owned_page_method_remains_allowed(owning):
    helpers.cdp(
        "Target.sendMessageToTarget",
        sessionId="SESSION-MINE",
        message=json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
    )


def test_owned_iframe_session_fails_closed_without_target_mapping(owning, monkeypatch):
    calls = []
    base = _fake_send(current={"targetId": "MINE", "url": "https://example.com/"}, target_type="iframe")
    def send(req, **kw):
        calls.append(req)
        if req.get("method") == "Page.getFrameTree":
            assert req["session_id"] == "SESSION-MINE"
            return {"result": {"frameTree": {"frame": {"id": "MINE"}, "childFrames": [
                {"frame": {"id": "CHILD"}, "childFrames": [{"frame": {"id": "IFRAME"}}]}]}}}
        if req.get("method") == "Target.attachToTarget":
            return {"result": {"sessionId": "IFRAME-SESSION"}}
        return base(req, **kw)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        helpers.js("42", target_id="IFRAME")
    assert not any(req.get("method") == "Runtime.evaluate" for req in calls)


@pytest.mark.parametrize("target_type", ["iframe", "worker", "service_worker", "browser", None])
def test_enumerating_non_page_target_does_not_grant_ownership(guard, monkeypatch, target_type):
    calls = []
    base = _fake_send(target_type=target_type)
    def send(req, **kw):
        calls.append(req)
        return base(req, **kw)
    monkeypatch.setattr(helpers, "_send", send)
    helpers.cdp("Target.getTargets")
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.attachToTarget", targetId="FOREIGN-CHILD")
    assert not any(r.get("method") == "Target.attachToTarget" for r in calls)
    assert helpers._owned_sessions() == set()


def test_implicit_dispatch_is_pinned_to_validated_session(owning, monkeypatch):
    calls = []
    def send(req, **kw):
        calls.append(req)
        if req.get("meta") == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": 0, "tab_guard_run": RUN_ID}
        if req.get("meta") == "guard_context":
            # Another run switches the daemon immediately after this snapshot.
            return {"target_id": "MINE", "session_id": "SESSION-MINE", "url": "https://example.com/",
                    "tab_guard": "ok", "tab_guard_epoch": 0, "document_generation": 0}
        assert req["session_id"] == "SESSION-MINE"
        return {"result": {}}
    monkeypatch.setattr(helpers, "_send", send)
    helpers.cdp("Page.navigate", url="https://example.com")
    assert calls[-1]["session_id"] == "SESSION-MINE"


@pytest.mark.parametrize("context", [
    None, [], {}, {"target_id": []}, {"target_id": "MINE"},
    {"target_id": "MINE", "session_id": []}, {"target_id": "MINE", "session_id": ""},
    {"target_id": "MINE", "session_id": "FOREIGN"},
    {"target_id": "FOREIGN", "session_id": "SESSION-MINE"},
])
def test_implicit_dispatch_fails_closed_on_unowned_or_incomplete_context(owning, monkeypatch, context):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kw: calls.append(req) or context)
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Runtime.evaluate", expression="1")
    assert all("method" not in req for req in calls)


def test_guard_off_performs_no_ownership_io(guard, monkeypatch, capsys):
    monkeypatch.delenv("BH_TAB_GUARD")
    def unexpected():
        pytest.fail("unguarded requests must not touch ownership files")
    monkeypatch.setattr(helpers, "_owned_path", unexpected)
    for _ in range(3):
        helpers.cdp("Target.createTarget")
        helpers.cdp("Target.attachToTarget", targetId="FOREIGN")
        helpers.cdp("Target.detachFromTarget", sessionId="SESSION-MINE")
    assert capsys.readouterr().err == ""


def test_removal_guard_off_does_not_resolve_ownership_path(guard, monkeypatch):
    monkeypatch.delenv("BH_TAB_GUARD")
    monkeypatch.setattr(helpers, "_owned_path", lambda: pytest.fail("path must not be resolved"))
    helpers._remember("tabs", "MINE", remove=True)


def test_ownership_update_lock_covers_cross_process_read_modify_replace(guard, tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR", str(tmp_path))
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR_SHARED", False)
    monkeypatch.setattr(helpers.ipc, "_RUNTIME", runtime)
    helpers.tab_guard_reset()
    helpers._own_tab("BASE")
    path = helpers._owned_path()
    script = (
        "from browser_harness import helpers\n"
        "print('started', flush=True)\n"
        "helpers._own_tab('CHILD')\n"
        "print('done', flush=True)\n"
    )
    env = _subprocess_env(
        BH_TAB_GUARD="1",
        BH_TAB_GUARD_RUN=RUN_ID,
        BH_TMP_DIR=str(tmp_path),
        BH_RUNTIME_DIR=str(runtime),
    )
    with helpers._ownership_lock(path):
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=str(pathlib.Path.cwd()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout.readline().strip() == "started"
        assert process.poll() is None
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    assert "done" in stdout
    assert helpers._owned_ids() == {"BASE", "CHILD"}


def test_reset_uses_the_same_ownership_lock(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(helpers.ipc, "_TMP", tmp_path)
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR", str(tmp_path))
    monkeypatch.setattr(helpers.ipc, "BH_TMP_DIR_SHARED", False)
    helpers._own_tab("MINE")
    path = helpers._owned_path()
    script = (
        "from browser_harness import helpers\n"
        "helpers._send = lambda req, **kw: {'tab_guard': 'ok', 'tab_guard_run': req.get('tab_guard_run'), 'tab_guard_epoch': 0}\n"
        "helpers.tab_guard_reset()\n"
        "print('done', flush=True)\n"
    )
    env = _subprocess_env(
        BH_TAB_GUARD="1",
        BH_TAB_GUARD_RUN=RUN_ID,
        BH_TMP_DIR=str(tmp_path),
        BH_RUNTIME_DIR=str(helpers.ipc._RUNTIME),
    )
    with helpers._ownership_lock(path):
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=str(pathlib.Path.cwd()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.poll() is None
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    assert stdout.strip() == "done"
    assert not path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_guarded_ownership_is_private_on_creation_and_update(guard):
    helpers._own_tab("MINE")
    assert helpers._owned_path().stat().st_mode & 0o777 == 0o600
    helpers._own_tab("SECOND")
    assert helpers._owned_path().stat().st_mode & 0o777 == 0o600


def test_enabling_guard_does_not_inherit_unguarded_tabs(guard, monkeypatch):
    monkeypatch.delenv("BH_TAB_GUARD")
    helpers.cdp("Target.createTarget")
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    assert helpers._owned_ids() == set()


@pytest.fixture
def daemon_bridge(owning, monkeypatch):
    """Exercise helpers against the actual daemon handler, without a browser."""
    d = daemon.Daemon()
    d.target_id, d.session = "MINE", "SESSION-MINE"
    d._session_targets["SESSION-MINE"] = "MINE"
    d._guard_policy_active = True
    d._guarded_run_id = RUN_ID
    d._guarded_sessions = {"SESSION-MINE"}
    d._guarded_targets = {"MINE"}
    d._document_state["SESSION-MINE"] = {
        "target_id": "MINE", "generation": 0,
        "url": "https://owned.example/", "document_url": "https://owned.example/",
        "frame_id": "FRAME-MINE", "loader_id": "LOADER-MINE", "allowed": True,
    }
    calls = []
    target_urls = {"MINE": "https://owned.example/"}
    class CDP:
        async def send_raw(self, method, params=None, session_id=None):
            calls.append((method, params, session_id))
            if method == "Target.getTargetInfo":
                target = params["targetId"]
                return {"targetInfo": {"type": "iframe" if target.startswith("IFRAME") else "page",
                                       "targetId": target, "url": target_urls.get(target, "https://owned.example/"),
                                       "title": "Owned"}}
            if method == "Page.getFrameTree":
                return {"frameTree": {"frame": {
                    "id": "IFRAME-FRAME" if session_id == "IFRAME-SESSION" else "FRAME-MINE",
                    "loaderId": "LOADER-IFRAME" if session_id == "IFRAME-SESSION" else "LOADER-MINE",
                    "url": target_urls.get("IFRAME-TARGET" if session_id == "IFRAME-SESSION" else "MINE",
                                            "https://owned.example/"),
                }}}
            if method == "Page.navigate":
                url = params["url"]
                target_urls["MINE"] = url
                d._record_event("Page.frameNavigated", {"frame": {
                    "id": "FRAME-MINE", "loaderId": "LOADER-NEXT", "url": url,
                }}, session_id)
                return {"frameId": "FRAME-MINE", "loaderId": "LOADER-NEXT"}
            if method == "Runtime.evaluate":
                return {"result": {"value": '{"url":"https://owned.example/"}'}}
            if method == "Target.attachToTarget":
                target = params["targetId"]
                return {"sessionId": "IFRAME-SESSION" if target == "IFRAME-TARGET" else "SESSION-MINE"}
            return {}
    d.cdp = CDP()
    def send(req, **kwargs):
        result = asyncio.run(d.handle(req))
        if result.get("tab_guard") == "refused":
            raise helpers.TabGuardRefused(
                f"[tab-guard] REFUSED (daemon): {result.get('error', 'guarded request refused')}",
                source="daemon",
            )
        if "error" in result:
            raise RuntimeError(result["error"])
        return result
    monkeypatch.setattr(helpers, "_send", send)
    return d, calls


@pytest.mark.parametrize("call", [
    helpers.current_tab, helpers.page_info, helpers.wait_for_network_idle,
    lambda: helpers._read_meta("connection_status"),
])
def test_metadata_helpers_refuse_foreign_current_tab(daemon_bridge, call):
    d, calls = daemon_bridge
    d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
    d._record_event("Page.javascriptDialogOpening", {"message": "private dialog"}, "FOREIGN-SESSION")
    with pytest.raises(helpers.TabGuardRefused):
        call()
    assert calls == []


def test_metadata_helpers_still_read_owned_page_and_dialog(daemon_bridge):
    d, _ = daemon_bridge
    assert helpers.current_tab()["targetId"] == "MINE"
    assert helpers.page_info()["url"] == "https://owned.example/"
    d._record_event("Page.javascriptDialogOpening", {
        "message": "owned", "url": "https://owned.example/", "frameId": "FRAME-MINE"}, "SESSION-MINE")
    assert d.dialog == {"message": "owned", "url": "https://owned.example/",
                        "frameId": "FRAME-MINE"}
    assert helpers.page_info() == {"dialog": {
        "message": "owned", "url": "https://owned.example/", "frameId": "FRAME-MINE"}}


def test_metadata_ignores_revoked_stale_entries_when_active_session_is_owned(daemon_bridge):
    helpers._remember("sessions", "REVOKED-SESSION")
    helpers._remember("tabs", "DESTROYED-TARGET")
    assert helpers.current_tab()["targetId"] == "MINE"


def test_guarded_navigation_allows_its_own_document_transition(daemon_bridge):
    d, calls = daemon_bridge
    result = helpers.cdp("Page.navigate", url="https://destination.example/")
    assert result["frameId"] == "FRAME-MINE"
    assert d._document_state["SESSION-MINE"]["document_url"] == "https://destination.example/"
    assert any(method == "Page.navigate" for method, _, _ in calls)


def test_nested_navigation_retains_only_its_valid_completion(daemon_bridge):
    d, _ = daemon_bridge
    original = d.cdp.send_raw
    async def legacy(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": d._document_state["SESSION-MINE"]["document_url"]}}
        if method == "Target.sendMessageToTarget":
            nested = json.loads(params["message"])
            url = nested["params"]["url"]
            if "#" in url:
                d._record_event("Page.navigatedWithinDocument", {
                    "frameId": "FRAME-MINE", "url": url,
                }, "SESSION-MINE")
            else:
                d._record_event("Page.frameNavigated", {"frame": {
                    "id": "FRAME-MINE", "loaderId": "LOADER-NEXT", "url": url,
                }}, "SESSION-MINE")
            d._record_event("Target.receivedMessageFromTarget", {
                "sessionId": "SESSION-MINE",
                "message": json.dumps({"id": nested["id"], "result": {"frameId": "FRAME-MINE"}}),
            })
            return {}
        return await original(method, params, session_id)
    d.cdp.send_raw = legacy
    helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE", message=json.dumps({
        "id": 902, "method": "Page.navigate", "params": {"url": "https://nested-destination.example/"},
    }))
    events = helpers.drain_events()
    reply = next(event for event in events if event["method"] == "Target.receivedMessageFromTarget")
    payload = json.loads(reply["params"]["message"])
    assert payload["id"] == 902
    assert payload["result"]["frameId"] == "FRAME-MINE"
    helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE", message=json.dumps({
        "id": 903, "method": "Page.navigate",
        "params": {"url": "https://nested-destination.example/#section"},
    }))
    events = helpers.drain_events()
    reply = next(event for event in events if event["method"] == "Target.receivedMessageFromTarget")
    payload = json.loads(reply["params"]["message"])
    assert payload["id"] == 903
    assert not d._legacy_commands


def test_guarded_iframe_ancestry_is_proved_by_daemon_before_attach(daemon_bridge):
    d, calls = daemon_bridge
    original = d.cdp.send_raw
    async def page_tree(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo" and params["targetId"] == "IFRAME-TARGET":
            return {"targetInfo": {"type": "iframe", "targetId": "IFRAME-TARGET",
                                   "url": "https://frame.example/"}}
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "FRAME-MINE", "url": "https://owned.example/"},
                "childFrames": [{"frame": {"id": "IFRAME-TARGET", "url": "https://frame.example/"}}]}}
        if method == "Target.attachToTarget":
            return {"sessionId": "IFRAME-SESSION"}
        return await original(method, params, session_id)
    d.cdp.send_raw = page_tree
    context = helpers._guard_context_request()
    assert context.get("tab_guard") == "ok", context
    assert helpers._is_owned_iframe("IFRAME-TARGET")
    assert "IFRAME-TARGET" in d._guarded_targets
    assert helpers.cdp("Target.attachToTarget", targetId="IFRAME-TARGET", flatten=True)["sessionId"] == "IFRAME-SESSION"
    assert "IFRAME-SESSION" in d._guarded_sessions
    assert any(method == "Page.getFrameTree" and sid == "SESSION-MINE"
               for method, _, sid in calls)


def test_reset_during_attach_frame_seed_revokes_and_detaches_session(daemon_bridge):
    d, calls = daemon_bridge
    original = d.cdp.send_raw
    async def reset_while_seeding(method, params=None, session_id=None):
        if method == "Target.attachToTarget":
            return {"sessionId": "SESSION-NEW"}
        if method == "Page.getFrameTree" and session_id == "SESSION-NEW":
            await d._tab_guard_reset({"tab_guard_run": RUN_ID, "tab_guard_epoch": 0})
            return {"frameTree": {"frame": {"id": "FRAME-MINE",
                                              "loaderId": "LOADER-MINE",
                                              "url": "https://owned.example/"}}}
        return await original(method, params, session_id)
    d.cdp.send_raw = reset_while_seeding
    with pytest.raises(helpers.TabGuardRefused, match="revoked during attach"):
        helpers.cdp("Target.attachToTarget", targetId="MINE", flatten=True)
    assert "SESSION-NEW" not in d._guarded_sessions
    assert any(method == "Target.detachFromTarget"
               and params == {"sessionId": "SESSION-NEW"}
               for method, params, _ in calls)


def test_detach_during_final_attach_validation_does_not_return_session(daemon_bridge):
    d, calls = daemon_bridge
    original = d.cdp.send_raw
    seeded = False
    async def detach_during_validation(method, params=None, session_id=None):
        nonlocal seeded
        if method == "Target.attachToTarget":
            return {"sessionId": "SESSION-NEW"}
        if method == "Page.getFrameTree" and session_id == "SESSION-NEW":
            seeded = True
            return {"frameTree": {"frame": {"id": "FRAME-MINE",
                                              "loaderId": "LOADER-MINE",
                                              "url": "https://owned.example/"}}}
        if method == "Target.getTargetInfo" and seeded:
            d._record_event("Target.detachedFromTarget", {
                "sessionId": "SESSION-NEW", "targetId": "MINE",
            })
        return await original(method, params, session_id)
    d.cdp.send_raw = detach_during_validation
    with pytest.raises(helpers.TabGuardRefused, match="revoked during attach"):
        helpers.cdp("Target.attachToTarget", targetId="MINE", flatten=True)
    assert "SESSION-NEW" not in d._guarded_sessions
    assert "SESSION-NEW" not in helpers._owned_sessions()
    assert any(method == "Target.detachFromTarget"
               and params == {"sessionId": "SESSION-NEW"}
               for method, params, _ in calls)


def test_guarded_metadata_and_switch_reject_privileged_current_url(daemon_bridge, monkeypatch):
    d, calls = daemon_bridge
    original = d.cdp.send_raw

    async def privileged(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            calls.append((method, params, session_id))
            return {"targetInfo": {"type": "page", "targetId": "MINE", "url": "chrome://settings"}}
        return await original(method, params, session_id)

    d.cdp.send_raw = privileged
    with pytest.raises(helpers.TabGuardRefused):
        helpers.current_tab()
    calls.clear()
    with pytest.raises(helpers.TabGuardRefused):
        helpers._read_meta("set_session", target_id="MINE", session_id="SESSION-MINE")
    assert not any(method.endswith(".enable") for method, _params, _sid in calls)


def test_foreign_dialog_does_not_leak_when_current_tab_is_owned(daemon_bridge):
    d, _ = daemon_bridge
    d._record_event("Page.javascriptDialogOpening", {"message": "private"}, "FOREIGN-SESSION")
    assert helpers.page_info() == {"url": "https://owned.example/"}


def test_foreign_dialog_close_cannot_clear_owned_dialog(daemon_bridge):
    d, _ = daemon_bridge
    d._record_event("Page.javascriptDialogOpening", {
        "message": "owned", "url": "https://owned.example/", "frameId": "FRAME-MINE"}, "SESSION-MINE")
    assert d.dialog == {"message": "owned", "url": "https://owned.example/",
                        "frameId": "FRAME-MINE"}
    d._record_event("Page.javascriptDialogClosed", {}, "FOREIGN-SESSION")
    assert helpers.page_info() == {"dialog": {
        "message": "owned", "url": "https://owned.example/", "frameId": "FRAME-MINE"}}


def test_event_drain_filters_owned_sessions_and_preserves_foreign_events(daemon_bridge):
    d, _ = daemon_bridge
    for sid in ("SESSION-MINE", "FOREIGN-SESSION", None):
        d._record_event(
            "Network.requestWillBeSent",
            {"secret": sid, "requestId": f"request-{sid}",
             "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
             "frameId": "FRAME-MINE"},
            sid,
        )
    # Even with a foreign current page, reading this run's own events is safe.
    d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
    assert [e["session_id"] for e in helpers.drain_events()] == ["SESSION-MINE"]
    assert list(d.events) == []
    assert helpers.drain_events() == []


@pytest.mark.parametrize("method,params", [
    ("Target.detachedFromTarget", {"sessionId": "SESSION-MINE", "targetId": "MINE"}),
    ("Target.targetDestroyed", {"targetId": "MINE"}),
])
def test_browser_lifecycle_revokes_ownership_and_discards_queued_events(
    daemon_bridge, monkeypatch, method, params
):
    d, _ = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    d._record_event("Network.requestWillBeSent", {
        "requestId": "request-before-destroy", "documentURL": "https://owned.example/",
        "loaderId": "LOADER-MINE", "frameId": "FRAME-MINE",
    }, "SESSION-MINE")
    d.events.append({"method": "unprovenanced"})
    d._event_provenance.append(None)
    assert len(d.events) == len(d._event_provenance) == 2

    d._record_event(method, params)

    assert not d.events
    assert not d._event_provenance
    assert "SESSION-MINE" not in d._guarded_sessions
    assert "SESSION-MINE" not in d._session_targets
    assert "SESSION-MINE" not in d._document_state
    if method == "Target.targetDestroyed":
        assert "MINE" not in d._guarded_targets
    else:
        assert "MINE" in d._guarded_targets
    with pytest.raises(helpers.TabGuardRefused):
        helpers.drain_events()


def test_unowned_browser_lifecycle_event_does_not_revoke_owned_target(daemon_bridge):
    d, _ = daemon_bridge
    d._record_event("Target.targetDestroyed", {"targetId": "FOREIGN"})
    assert d._guarded_sessions == {"SESSION-MINE"}
    assert d._guarded_targets == {"MINE"}


@pytest.mark.parametrize("method", ["Page.loadEventFired", "Page.domContentEventFired"])
def test_guarded_timestamp_page_events_use_owned_document_provenance(
    daemon_bridge, monkeypatch, method
):
    d, _ = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    params = {"timestamp": 123.456}

    async def record_events():
        d._record_event(method, params, "SESSION-MINE")
        d._record_event(method, params, "FOREIGN-SESSION")

    asyncio.run(record_events())

    events = helpers.drain_events()
    assert [(event["method"], event["params"]) for event in events] == [(method, params)]
    assert events[0]["session_id"] == "SESSION-MINE"


def test_event_drain_hides_owned_session_after_privileged_navigation(daemon_bridge, monkeypatch):
    d, _ = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    d._record_event("Page.frameNavigated", {"frame": {"url": "chrome://settings"}}, "SESSION-MINE")
    d._record_event("Page.loadEventFired", {}, "SESSION-MINE")
    assert helpers.drain_events() == []
    assert list(d.events) == []


@pytest.mark.parametrize("intermediate_drain", [False, True])
def test_event_provenance_drops_privileged_document_payloads_across_navigation(
    daemon_bridge, monkeypatch, intermediate_drain
):
    d, _ = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    d._record_event(
        "Network.requestWillBeSent",
        {"secret": "allowed-before", "requestId": "before",
         "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
         "frameId": "FRAME-MINE"},
        "SESSION-MINE",
    )
    d._record_event(
        "Page.frameNavigated", {"frame": {"id": "FRAME-PRIV", "loaderId": "LOADER-PRIV",
                                             "url": "chrome://settings"}}, "SESSION-MINE"
    )
    d._record_event(
        "Network.requestWillBeSent",
        {"secret": "privileged", "requestId": "privileged",
         "documentURL": "chrome://settings", "loaderId": "LOADER-PRIV",
         "frameId": "FRAME-PRIV"},
        "SESSION-MINE",
    )
    before = helpers.drain_events() if intermediate_drain else []
    d._record_event(
        "Page.frameNavigated", {"frame": {"id": "FRAME-ALLOWED", "loaderId": "LOADER-ALLOWED",
                                             "url": "https://allowed.example/"}}, "SESSION-MINE"
    )
    d._record_event(
        "Network.requestWillBeSent",
        {"secret": "allowed-after", "requestId": "after",
         "documentURL": "https://allowed.example/", "loaderId": "LOADER-ALLOWED",
         "frameId": "FRAME-ALLOWED"},
        "SESSION-MINE",
    )
    after = helpers.drain_events()
    payload = json.dumps(before + after)
    assert "privileged" not in payload
    assert "allowed-before" in payload
    assert "allowed-after" in payload


def test_subframe_navigation_does_not_replace_top_document_provenance(daemon_bridge):
    d, _ = daemon_bridge
    before = dict(d._document_state["SESSION-MINE"])
    d._record_event(
        "Page.frameNavigated",
        {"frame": {"id": "child-frame", "parentId": "root-frame", "url": "https://frame.example/"}},
        "SESSION-MINE",
    )
    assert d._document_state["SESSION-MINE"] == before
    d._record_event(
        "Network.requestWillBeSent",
        {"requestId": "after-subframe", "secret": "owned-page-event",
         "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
         "frameId": "FRAME-MINE"},
        "SESSION-MINE",
    )
    events = helpers.drain_events()
    assert any(event.get("params", {}).get("secret") == "owned-page-event" for event in events)


def test_same_document_navigation_updates_url_without_advancing_generation(daemon_bridge):
    d, calls = daemon_bridge
    new_url = "https://owned.example/#section"
    original = d.cdp.send_raw

    async def current_url(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            calls.append((method, params, session_id))
            return {"targetInfo": {"type": "page", "targetId": "MINE", "url": new_url}}
        if method == "Runtime.evaluate":
            calls.append((method, params, session_id))
            return {"result": {"value": "continued"}}
        return await original(method, params, session_id)

    d.cdp.send_raw = current_url
    d._record_event("Page.navigatedWithinDocument", {
        "frameId": "FRAME-MINE", "url": new_url,
    }, "SESSION-MINE")

    state = d._document_state["SESSION-MINE"]
    assert state["generation"] == 0
    assert state["url"] == new_url
    assert state["document_url"] == new_url
    assert state["allowed"] is True
    assert helpers.cdp("Runtime.evaluate", session_id="SESSION-MINE", expression="1") == {
        "result": {"value": "continued"},
    }
    assert any(call[0] == "Runtime.evaluate" for call in calls)


def test_same_document_navigation_to_unauthorized_url_fails_closed(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"})
    d._record_event("Page.navigatedWithinDocument", {
        "frameId": "FRAME-MINE", "url": "chrome://settings",
    }, "SESSION-MINE")

    state = d._document_state["SESSION-MINE"]
    assert state["generation"] == 0
    assert state["url"] == "chrome://settings"
    assert state["document_url"] == "chrome://settings"
    assert state["allowed"] is False
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


@pytest.mark.parametrize("legacy", [False, True])
def test_network_supplemental_events_require_same_document_authorized_request(
    daemon_bridge, legacy
):
    d, _ = daemon_bridge

    def record(method, params, outer_session="SESSION-MINE"):
        if legacy:
            d._record_event(
                "Target.receivedMessageFromTarget",
                {"sessionId": "SESSION-MINE", "message": json.dumps({
                    "method": method, "params": params,
                })},
                outer_session,
            )
        else:
            d._record_event(method, params, outer_session)

    record("Network.requestWillBeSentExtraInfo", {"requestId": "unresolved"})
    record("Network.loadingFinished", {"requestId": "unresolved"})
    record("Network.requestWillBeSent", {
        "requestId": "mismatched-document", "documentURL": "https://other.example/",
        "loaderId": "LOADER-MINE", "frameId": "FRAME-MINE", "secret": "mismatched",
    })
    record("Network.loadingFinished", {"requestId": "mismatched-document"})
    for field in ("loaderId", "frameId"):
        params = {
            "requestId": f"mismatched-{field}", "documentURL": "https://owned.example/",
            "loaderId": "LOADER-MINE", "frameId": "FRAME-MINE", "secret": field,
        }
        params[field] = f"WRONG-{field}"
        record("Network.requestWillBeSent", params)
        record("Network.loadingFinished", {"requestId": params["requestId"]})
    record("Network.requestWillBeSent", {
        "requestId": "request-1", "secret": "authorized",
        "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
        "frameId": "FRAME-MINE",
    })
    record("Network.requestWillBeSentExtraInfo", {"requestId": "request-1"})
    record("Network.responseReceivedExtraInfo", {"requestId": "request-1"})
    record("Network.loadingFinished", {"requestId": "request-1"})
    record("Network.loadingFinished", {"requestId": "request-2"})
    d._record_event(
        "Page.frameNavigated",
        {"frame": {"id": "FRAME-PRIV", "loaderId": "LOADER-PRIV", "url": "chrome://settings"}},
        "SESSION-MINE",
    )
    record("Network.loadingFinished", {"requestId": "request-1"})

    events = helpers.drain_events()
    encoded = json.dumps(events)
    assert "authorized" in encoded
    if legacy:
        assert all(event["method"] == "Target.receivedMessageFromTarget" for event in events)
        inner_methods = [
            json.loads(event["params"]["message"])["method"] for event in events
        ]
        assert inner_methods.count("Network.loadingFinished") == 1
    else:
        assert sum(event["method"] == "Network.loadingFinished" for event in events) == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_network_supplemental_event_keeps_its_original_authorization_across_navigation(
    daemon_bridge, legacy
):
    d, _ = daemon_bridge

    def record(method, params):
        if legacy:
            d._record_event(
                "Target.receivedMessageFromTarget",
                {"sessionId": "SESSION-MINE", "message": json.dumps({
                    "method": method, "params": params,
                })},
                "FOREIGN-OUTER-CARRIER",
            )
        else:
            d._record_event(method, params, "SESSION-MINE")

    record("Network.requestWillBeSent", {
        "requestId": "delayed", "secret": "start",
        "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
        "frameId": "FRAME-MINE",
    })
    record("Page.frameNavigated", {
        "frame": {"id": "FRAME-PRIV", "loaderId": "LOADER-PRIV", "url": "chrome://settings"}
    })
    record("Page.frameNavigated", {
        "frame": {"id": "FRAME-ALLOWED", "loaderId": "LOADER-ALLOWED",
                   "url": "https://allowed-again.example/"}
    })
    record("Network.loadingFinished", {"requestId": "delayed"})
    events = helpers.drain_events()
    assert "start" in json.dumps(events)
    if legacy:
        assert any(
            event["method"] == "Target.receivedMessageFromTarget"
            and json.loads(event["params"]["message"]).get("method") == "Network.loadingFinished"
            for event in events
        )
    else:
        assert any(event["method"] == "Network.loadingFinished" for event in events)


@pytest.mark.parametrize("legacy", [False, True])
def test_denied_request_stays_denied_after_return_to_allowed_document(daemon_bridge, legacy):
    d, _ = daemon_bridge

    def record(method, params):
        if legacy:
            d._record_event(
                "Target.receivedMessageFromTarget",
                {"sessionId": "SESSION-MINE", "message": json.dumps({
                    "method": method, "params": params,
                })},
                "FOREIGN-OUTER-CARRIER",
            )
        else:
            d._record_event(method, params, "SESSION-MINE")

    record("Page.frameNavigated", {
        "frame": {"id": "FRAME-PRIV", "loaderId": "LOADER-PRIV", "url": "chrome://settings"},
    })
    record("Network.requestWillBeSent", {
        "requestId": "denied-request", "documentURL": "chrome://settings",
        "loaderId": "LOADER-PRIV", "frameId": "FRAME-PRIV", "secret": "denied",
    })
    record("Page.frameNavigated", {
        "frame": {"id": "FRAME-ALLOWED", "loaderId": "LOADER-ALLOWED",
                   "url": "https://allowed-again.example/"},
    })
    record("Network.requestWillBeSent", {
        "requestId": "denied-request", "documentURL": "https://allowed-again.example/",
        "loaderId": "LOADER-ALLOWED", "frameId": "FRAME-ALLOWED", "secret": "revived",
    })
    record("Network.responseReceivedExtraInfo", {"requestId": "denied-request"})
    record("Network.loadingFinished", {"requestId": "denied-request"})

    events = helpers.drain_events()
    encoded = json.dumps(events)
    assert "revived" in encoded
    secrets = []
    for event in events:
        params = event.get("params", {})
        if event.get("method") == "Target.receivedMessageFromTarget":
            params = json.loads(params["message"]).get("params", {})
        if isinstance(params, dict) and "secret" in params:
            secrets.append(params["secret"])
    assert "denied" not in secrets
    assert not any(
        event.get("method") == "Network.loadingFinished"
        or (event.get("method") == "Target.receivedMessageFromTarget"
            and json.loads(event["params"]["message"]).get("method") == "Network.loadingFinished")
        for event in events
    )


@pytest.mark.parametrize("legacy", [False, True])
def test_unclassified_stream_and_console_events_require_provenance(daemon_bridge, legacy):
    d, _ = daemon_bridge

    def record(method, params):
        if legacy:
            d._record_event(
                "Target.receivedMessageFromTarget",
                {"sessionId": "SESSION-MINE", "message": json.dumps({
                    "method": method, "params": params,
                })},
                "FOREIGN-OUTER-CARRIER",
            )
        else:
            d._record_event(method, params, "SESSION-MINE")

    record("Network.eventSourceMessageReceived", {"requestId": "missing", "data": "secret-stream"})
    record("Runtime.consoleAPICalled", {"executionContextId": 999, "args": [{"value": "secret-console"}]})
    record("Network.unknownEvent", {"secret": "unknown"})
    record("Network.requestWillBeSent", {
        "requestId": "stream-request", "documentURL": "https://owned.example/",
        "loaderId": "LOADER-MINE", "frameId": "FRAME-MINE",
    })
    record("Network.eventSourceMessageReceived", {
        "requestId": "stream-request", "data": "owned-stream",
    })
    record("Runtime.executionContextCreated", {
        "context": {
            "id": 7,
            "uniqueId": "unique-context-7",
            "origin": "https://owned.example",
            "auxData": {"frameId": "FRAME-MINE"},
        },
    })
    record("Runtime.consoleAPICalled", {"executionContextId": 7, "args": [{"value": "owned-console"}]})
    assert ("SESSION-MINE", "MINE", "7") in d._execution_contexts
    assert ("SESSION-MINE", "MINE", "unique-context-7") not in d._execution_contexts
    record("Runtime.executionContextDestroyed", {"executionContextId": 7})
    assert ("SESSION-MINE", "MINE", "7") not in d._execution_contexts
    record("Page.frameNavigated", {
        "frame": {"id": "FRAME-NEXT", "loaderId": "LOADER-NEXT",
                   "url": "https://next.example/"},
    })
    record("Runtime.consoleAPICalled", {
        "executionContextId": 7, "args": [{"value": "stale-console"}],
    })
    events = helpers.drain_events()
    encoded = json.dumps(events)
    assert "secret-stream" not in encoded
    assert "secret-console" not in encoded
    assert "unknown" not in encoded
    assert "owned-stream" in encoded
    assert "owned-console" in encoded
    assert "stale-console" not in encoded


def test_event_drain_hides_owned_session_without_target_proof(daemon_bridge):
    d, _ = daemon_bridge
    d._session_targets.pop("SESSION-MINE")
    d._record_event(
        "Network.requestWillBeSent",
        {"secret": "owned", "requestId": "owned",
         "documentURL": "https://owned.example/", "loaderId": "LOADER-MINE",
         "frameId": "FRAME-MINE"},
        "SESSION-MINE",
    )
    assert helpers.drain_events() == []
    assert list(d.events) == []


def test_legacy_target_reply_uses_params_session_id_for_guarded_event_filter(daemon_bridge):
    d, _ = daemon_bridge
    d._legacy_commands[("SESSION-MINE", 1)] = {
        "run_id": RUN_ID, "epoch": d._authorization_epoch, "generation": 0,
        "target_id": "MINE",
        "caller_id": 1,
        "document_url": "https://owned.example/", "session_id": "SESSION-MINE",
    }
    owned = {"method": "Target.receivedMessageFromTarget",
             "params": {"sessionId": "SESSION-MINE", "message": json.dumps({"id": 1, "result": {}})},
             "session_id": None}
    foreign = {"method": "Target.receivedMessageFromTarget",
               "params": {"sessionId": "FOREIGN-SESSION", "message": json.dumps({"id": 2, "result": {}})},
               "session_id": None}
    d._record_event(owned["method"], owned["params"], owned["session_id"])
    d._record_event(foreign["method"], foreign["params"], foreign["session_id"])
    assert helpers.drain_events() == [owned]
    assert list(d.events) == []


def _guarded_dispatch_request(d, method, params, *, command_session=None):
    session = command_session or "SESSION-MINE"
    state = d._document_state[session]
    return {
        "method": method,
        "params": params,
        "session_id": None if method.startswith("Target.") else session,
        "tab_guard": {"tabs": [d._session_targets[session]], "sessions": [session]},
        "tab_guard_run": d._guarded_run_id,
        "tab_guard_epoch": d._authorization_epoch,
        "tab_guard_target_id": d._session_targets[session],
        "tab_guard_session_id": session,
        "tab_guard_document_generation": state["generation"],
        "tab_guard_url": state["document_url"],
    }


@pytest.mark.parametrize("nested", [False, True])
def test_daemon_rejects_dispatch_snapshots_stale_after_navigation(daemon_bridge, nested):
    d, calls = daemon_bridge
    if nested:
        request = _guarded_dispatch_request(d, "Target.sendMessageToTarget", {
            "sessionId": "SESSION-MINE",
            "message": json.dumps({"id": 901, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
        })
    else:
        request = _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"})
    d._record_event("Page.frameNavigated", {"frame": {
        "id": "FRAME-NEXT", "loaderId": "LOADER-NEXT", "url": "https://next.example/",
    }}, "SESSION-MINE")
    response = asyncio.run(d.handle(request))
    assert "stale" in response["error"]
    assert not any(call[0] == ("Target.sendMessageToTarget" if nested else "Runtime.evaluate")
                   for call in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_dispatch_rejects_stale_url_snapshot_after_same_document_navigation(daemon_bridge, nested):
    d, calls = daemon_bridge
    method = "Target.sendMessageToTarget" if nested else "Runtime.evaluate"
    params = ({
        "sessionId": "SESSION-MINE",
        "message": json.dumps({"id": 919, "method": "Runtime.evaluate",
                                "params": {"expression": "1"}}),
    } if nested else {"expression": "1"})
    request = _guarded_dispatch_request(d, method, params)
    d._record_event("Page.navigatedWithinDocument", {
        "frameId": "FRAME-MINE", "url": "https://owned.example/#next",
    }, "SESSION-MINE")

    response = asyncio.run(d.handle(request))

    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == method for call in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_daemon_last_state_check_rejects_navigation_race_before_transport(daemon_bridge, nested):
    d, calls = daemon_bridge
    request = (_guarded_dispatch_request(d, "Target.sendMessageToTarget", {
        "sessionId": "SESSION-MINE",
        "message": json.dumps({"id": 905, "method": "Runtime.evaluate",
                                "params": {"expression": "1"}}),
    }) if nested else _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"}))
    original = d._validate_dispatch_identity

    async def validate_then_navigate(*args, **kwargs):
        identity = await original(*args, **kwargs)
        if identity is not None:
            d._record_event("Page.frameNavigated", {"frame": {
                "id": "FRAME-RACE", "loaderId": "LOADER-RACE", "url": "https://race.example/",
            }}, "SESSION-MINE")
        return identity

    d._validate_dispatch_identity = validate_then_navigate
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == ("Target.sendMessageToTarget" if nested else "Runtime.evaluate")
                   for call in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_daemon_last_state_check_rejects_reset_race_before_transport(daemon_bridge, nested):
    d, calls = daemon_bridge
    request = (_guarded_dispatch_request(d, "Target.sendMessageToTarget", {
        "sessionId": "SESSION-MINE",
        "message": json.dumps({"id": 906, "method": "Runtime.evaluate",
                                "params": {"expression": "1"}}),
    }) if nested else _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"}))
    original = d._validate_dispatch_identity

    async def validate_then_revoke(*args, **kwargs):
        identity = await original(*args, **kwargs)
        if identity is not None:
            d._authorization_epoch += 1
            d._guarded_run_id = None
        return identity

    d._validate_dispatch_identity = validate_then_revoke
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == ("Target.sendMessageToTarget" if nested else "Runtime.evaluate")
                   for call in calls)


def test_daemon_rejects_foreign_detach_session_before_transport(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.detachFromTarget", {"sessionId": "FOREIGN-SESSION"})
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == "Target.detachFromTarget" for call in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_daemon_scope_policy_rejects_context_wide_dispatch_before_transport(daemon_bridge, nested):
    d, calls = daemon_bridge
    if nested:
        request = _guarded_dispatch_request(d, "Target.sendMessageToTarget", {
            "sessionId": "SESSION-MINE",
            "message": json.dumps({"id": 907, "method": "Storage.getCookies", "params": {}}),
        })
        forbidden = "Target.sendMessageToTarget"
    else:
        request = _guarded_dispatch_request(d, "Storage.getCookies", {})
        forbidden = "Storage.getCookies"
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == forbidden for call in calls)


def test_active_guard_rejects_dispatch_with_identity_omitted(daemon_bridge):
    d, calls = daemon_bridge
    response = asyncio.run(d.handle({
        "method": "Runtime.evaluate", "params": {"expression": "1"},
        "session_id": "SESSION-MINE",
    }))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_dispatch_rejects_live_target_url_changed_since_snapshot(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"})
    original = d.cdp.send_raw

    async def changed_url(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            calls.append((method, params, session_id))
            return {"targetInfo": {"targetId": "MINE", "url": "https://new.example/"}}
        return await original(method, params, session_id)

    d.cdp.send_raw = changed_url
    response = asyncio.run(d.handle(request))
    assert "stale" in response["error"]
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_guard_reset_suppresses_inflight_dispatch_result(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"})
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_send(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"targetId": "MINE", "url": "https://owned.example/"}}
        entered.set()
        await release.wait()
        return {"result": {"value": "private result"}}

    d.cdp.send_raw = blocked_send

    async def run():
        pending = asyncio.create_task(d.handle(request))
        await entered.wait()
        reset = await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                "tab_guard_epoch": d._authorization_epoch})
        release.set()
        return reset, await pending

    reset, result = asyncio.run(run())
    assert reset["tab_guard"] == "ok"
    assert result == {"tab_guard": "refused", "error": "tab guard authorization was revoked during dispatch"}
    assert "private result" not in json.dumps(result)


@pytest.mark.parametrize("change", ["reset", "navigation", "membership", "mapping", "live_url"])
def test_dispatch_result_is_suppressed_if_authorization_changes_during_final_metadata(
    daemon_bridge, change
):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Runtime.evaluate", {"expression": "1"})
    entered, release = asyncio.Event(), asyncio.Event()
    info_calls = 0

    async def blocked_send(method, params=None, session_id=None):
        nonlocal info_calls
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            info_calls += 1
            if info_calls == 2:
                entered.set()
                await release.wait()
            url = d._document_state.get("SESSION-MINE", {}).get("document_url", "https://owned.example/")
            if change == "live_url" and info_calls == 2:
                url = "https://replacement.example/"
            return {"targetInfo": {"targetId": "MINE", "url": url}}
        return {"value": "private-after-await"}

    d.cdp.send_raw = blocked_send

    async def run():
        pending = asyncio.create_task(d.handle(request))
        await entered.wait()
        if change == "reset":
            await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                            "tab_guard_epoch": d._authorization_epoch})
        elif change == "navigation":
            d._document_state["SESSION-MINE"].update({
                "generation": 1, "document_url": "https://next.example/",
                "url": "https://next.example/",
            })
        elif change == "membership":
            d._guarded_sessions.discard("SESSION-MINE")
        elif change == "mapping":
            d._session_targets["SESSION-MINE"] = "OTHER-TARGET"
        release.set()
        return await pending

    result = asyncio.run(run())
    assert result == {"tab_guard": "refused", "error": "tab guard authorization was revoked during dispatch"}
    assert "private-after-await" not in json.dumps(result)


def test_guarded_metadata_is_suppressed_if_reset_occurs_during_target_lookup(daemon_bridge):
    d, _ = daemon_bridge
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_info(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            entered.set()
            await release.wait()
        return {"targetInfo": {
            "targetId": "MINE", "url": "https://owned.example/", "title": "Owned",
        }}

    d.cdp.send_raw = blocked_info

    async def run():
        pending = asyncio.create_task(d.handle({
            "meta": "current_tab", "tab_guard": {"tabs": ["MINE"], "sessions": ["SESSION-MINE"]},
            "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
        }))
        await entered.wait()
        await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                        "tab_guard_epoch": d._authorization_epoch})
        release.set()
        return await pending

    assert asyncio.run(run()) == {"tab_guard": "refused", "target_id": "MINE"}


def test_pre_reset_set_session_cannot_register_with_stale_epoch(daemon_bridge):
    d, calls = daemon_bridge
    stale_request = {
        "meta": "set_session", "session_id": "SESSION-MINE", "target_id": "MINE",
        "tab_guard": {"tabs": ["MINE"], "sessions": ["SESSION-MINE"]},
        "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
    }
    reset = asyncio.run(d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                  "tab_guard_epoch": d._authorization_epoch}))
    calls.clear()

    result = asyncio.run(d.handle(stale_request))

    assert reset["tab_guard"] == "ok"
    assert result == {"tab_guard": "refused", "target_id": "MINE"}
    assert calls == []


def test_guard_context_reply_is_discarded_after_reset_during_target_lookup(daemon_bridge):
    d, _ = daemon_bridge
    entered, release = asyncio.Event(), asyncio.Event()
    original_send = d.cdp.send_raw

    async def blocked_info(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            entered.set()
            await release.wait()
        return await original_send(method, params, session_id)

    d.cdp.send_raw = blocked_info

    async def run():
        pending = asyncio.create_task(d.handle({
            "meta": "guard_context", "session_id": "SESSION-MINE",
            "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
        }))
        await entered.wait()
        await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                        "tab_guard_epoch": d._authorization_epoch})
        release.set()
        return await pending

    context = asyncio.run(run())
    assert context["tab_guard"] == "refused"
    assert context["target_id"] is None


def test_set_session_reply_is_discarded_after_reset_during_domain_setup(daemon_bridge, monkeypatch):
    d, _ = daemon_bridge
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_enables(_session):
        entered.set()
        await release.wait()

    monkeypatch.setattr(d, "_enable_default_domains", blocked_enables)
    request = {
        "meta": "set_session", "session_id": "SESSION-MINE", "target_id": "MINE",
        "tab_guard": {"tabs": ["MINE"], "sessions": ["SESSION-MINE"]},
        "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
    }

    async def run():
        pending = asyncio.create_task(d.handle(request))
        await entered.wait()
        reset = await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                "tab_guard_epoch": d._authorization_epoch})
        release.set()
        return reset, await pending

    reset, result = asyncio.run(run())
    assert reset["tab_guard"] == "ok"
    assert result["tab_guard"] == "refused"


def test_set_session_latches_policy_before_target_lookup_and_keeps_it_after_reset(
        daemon_bridge, monkeypatch):
    d, calls = daemon_bridge
    d._guard_policy_active = False
    target_lookup_entered, release_lookup = asyncio.Event(), asyncio.Event()
    setup_entered, release_setup = asyncio.Event(), asyncio.Event()

    async def blocked_info(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            target_lookup_entered.set()
            await release_lookup.wait()
            return {"targetInfo": {"targetId": "MINE", "url": "https://owned.example/"}}
        return {}

    async def blocked_enables(_session):
        setup_entered.set()
        await release_setup.wait()

    d.cdp.send_raw = blocked_info
    monkeypatch.setattr(d, "_enable_default_domains", blocked_enables)
    request = {
        "meta": "set_session", "session_id": "SESSION-MINE", "target_id": "MINE",
        "tab_guard": {"tabs": ["MINE"], "sessions": ["SESSION-MINE"]},
        "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
    }

    async def run():
        pending = asyncio.create_task(d.handle(request))
        await target_lookup_entered.wait()
        assert d._guard_policy_active is True
        metadata = await d.handle({"meta": "connection_status"})
        unguarded_cdp = await d.handle({"method": "Runtime.evaluate", "params": {"expression": "1"}})
        release_lookup.set()
        await setup_entered.wait()
        reset = await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                "tab_guard_epoch": d._authorization_epoch})
        release_setup.set()
        return metadata, unguarded_cdp, reset, await pending

    metadata, unguarded_cdp, reset, result = asyncio.run(run())

    assert metadata == {"tab_guard": "refused"}
    assert unguarded_cdp == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert reset["tab_guard"] == "ok"
    assert result["tab_guard"] == "refused"
    assert d._guard_policy_active is True
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_guarded_bootstrap_latches_policy_before_transport_yields(daemon_bridge):
    d, calls = daemon_bridge
    d._guard_policy_active = False
    d._guarded_run_id = None
    concurrent_results = []

    async def observe_during_create(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        concurrent_results.append(await d.handle({"meta": "connection_status"}))
        concurrent_results.append(await d.handle({
            "method": "Runtime.evaluate", "params": {"expression": "1"},
        }))
        return {"browserContextId": "CTX"}

    d.cdp.send_raw = observe_during_create
    request = {
        "method": "Target.createBrowserContext", "params": {}, "session_id": None,
        "tab_guard": {"tabs": [], "sessions": [], "contexts": []},
        "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
    }

    result = asyncio.run(d.handle(request))

    assert concurrent_results == [
        {"tab_guard": "refused"},
        {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"},
    ]
    assert result == {"result": {"browserContextId": "CTX"}}
    reset = asyncio.run(d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                  "tab_guard_epoch": d._authorization_epoch}))
    assert reset["tab_guard"] == "ok"
    assert d._guard_policy_active is True
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_guard_enabled_daemon_rejects_guardless_dispatch_and_metadata_before_bootstrap(
    monkeypatch,
):
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    d = daemon.Daemon()
    calls = []

    class CDP:
        async def send_raw(self, method, params=None, session_id=None):
            calls.append((method, params, session_id))
            return {"result": {"value": "foreign"}}

    d.cdp = CDP()

    async def run():
        dispatch = await d.handle({
            "method": "Runtime.evaluate", "params": {"expression": "1"},
            "session_id": "FOREIGN-SESSION",
        })
        metadata = await d.handle({"meta": "connection_status"})
        return dispatch, metadata

    dispatch, metadata = asyncio.run(run())

    assert d._guard_policy_active is True
    assert dispatch == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert metadata == {"tab_guard": "refused"}
    assert calls == []


def test_unguarded_inflight_dispatch_result_is_suppressed_after_guarded_bootstrap(
    monkeypatch,
):
    monkeypatch.delenv("BH_TAB_GUARD", raising=False)
    d = daemon.Daemon()
    entered, release = asyncio.Event(), asyncio.Event()

    class CDP:
        async def send_raw(self, method, params=None, session_id=None):
            if method == "Runtime.evaluate":
                entered.set()
                await release.wait()
                return {"result": {"value": "private foreign result"}}
            if method == "Target.createBrowserContext":
                return {"browserContextId": "CTX-MINE"}
            raise AssertionError(f"unexpected CDP call: {method}")

    d.cdp = CDP()
    bootstrap = {
        "method": "Target.createBrowserContext", "params": {}, "session_id": None,
        "tab_guard": {"tabs": [], "sessions": [], "contexts": []},
        "tab_guard_run": RUN_ID, "tab_guard_epoch": d._authorization_epoch,
    }

    async def run():
        pending = asyncio.create_task(d.handle({
            "method": "Runtime.evaluate", "params": {"expression": "1"},
            "session_id": "FOREIGN-SESSION",
        }))
        await entered.wait()
        started = await d.handle(bootstrap)
        assert started == {"result": {"browserContextId": "CTX-MINE"}}
        release.set()
        return await pending

    result = asyncio.run(run())

    assert result == {"tab_guard": "refused", "error": "tab guard authorization was revoked during dispatch"}
    assert "private foreign result" not in json.dumps(result)


@pytest.mark.parametrize("payload", [
    "{bad json", json.dumps({"id": 999, "result": {"secret": "unknown"}}),
    json.dumps({"id": 1, "result": {"secret": "malformed correlation"}}),
    json.dumps({"id": True, "result": {"secret": "boolean id"}}),
])
def test_legacy_replies_without_current_outstanding_authorization_are_dropped(daemon_bridge, payload):
    d, _ = daemon_bridge
    event = {"sessionId": "SESSION-MINE", "message": payload}
    d._record_event("Target.receivedMessageFromTarget", event, None)
    assert helpers.drain_events() == []


def test_legacy_reply_is_dropped_after_its_authorized_document_navigates(daemon_bridge):
    d, _ = daemon_bridge
    identity = {
        "run_id": RUN_ID, "epoch": d._authorization_epoch, "generation": 0,
        "document_url": "https://owned.example/", "session_id": "SESSION-MINE",
    }
    d._remember_legacy_command(identity, {"message": json.dumps({
        "id": 903, "method": "Runtime.evaluate", "params": {"expression": "1"},
    })})
    d._record_event("Page.frameNavigated", {"frame": {
        "id": "FRAME-NEXT", "loaderId": "LOADER-NEXT", "url": "https://next.example/",
    }}, "SESSION-MINE")
    d._record_event("Target.receivedMessageFromTarget", {
        "sessionId": "SESSION-MINE", "message": json.dumps({"id": 903, "result": {"secret": "late"}}),
    }, None)
    assert "late" not in json.dumps(helpers.drain_events())


def test_nested_legacy_dispatch_registers_exact_authorized_reply(daemon_bridge):
    d, calls = daemon_bridge
    helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE",
                message=json.dumps({"id": 904, "method": "Runtime.evaluate",
                                    "params": {"expression": "1"}}))
    wire_id = json.loads(next(
        params["message"] for method, params, _sid in calls
        if method == "Target.sendMessageToTarget"
    ))["id"]
    d._record_event("Target.receivedMessageFromTarget", {
        "sessionId": "SESSION-MINE",
        "message": json.dumps({"id": wire_id, "result": {"value": 1}}),
    }, None)
    events = helpers.drain_events()
    assert len(events) == 1
    assert json.loads(events[0]["params"]["message"]) == {"id": 904, "result": {"value": 1}}


def test_legacy_caller_id_cannot_be_reused_for_a_delayed_reply(daemon_bridge):
    d, calls = daemon_bridge
    def command():
        return helpers.cdp(
            "Target.sendMessageToTarget", sessionId="SESSION-MINE",
            message=json.dumps({"id": 905, "method": "Runtime.evaluate",
                                "params": {"expression": "1"}}),
        )
    command()
    first_wire = json.loads(calls[-2][1]["message"])["id"]
    assert isinstance(first_wire, int)
    d._record_event("Target.receivedMessageFromTarget", {
        "sessionId": "SESSION-MINE", "message": json.dumps({"id": first_wire, "result": {"value": 1}}),
    }, None)
    assert len(helpers.drain_events()) == 1
    command()
    second_wire = json.loads(calls[-2][1]["message"])["id"]
    assert first_wire != second_wire
    d._record_event("Target.receivedMessageFromTarget", {
        "sessionId": "SESSION-MINE", "message": json.dumps({"id": first_wire, "result": {"secret": "late"}}),
    }, None)
    assert "late" not in json.dumps(helpers.drain_events())
    d._record_event("Target.receivedMessageFromTarget", {
        "sessionId": "SESSION-MINE", "message": json.dumps({"id": second_wire, "result": {"value": 2}}),
    }, None)
    events = helpers.drain_events()
    assert len(events) == 1
    assert json.loads(events[0]["params"]["message"])["id"] == 905


def test_dialog_and_subframe_events_require_current_document_provenance(
    daemon_bridge, monkeypatch
):
    d, _ = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    d._record_event("Page.javascriptDialogOpening", {
        "message": "subframe dialog", "url": "https://frame.example/",
    }, "SESSION-MINE")
    d._record_event("Page.frameNavigated", {"frame": {
        "id": "CHILD", "parentId": "FRAME-MINE", "url": "https://frame.example/",
    }}, "SESSION-MINE")
    d._record_event("Page.loadEventFired", {"timestamp": 123.456}, "FOREIGN-SESSION")
    assert helpers.drain_events() == []
    assert d.dialog is None


@pytest.mark.parametrize("legacy", [False, True])
def test_dialog_requires_top_document_frame_even_when_session_is_owned(daemon_bridge, legacy):
    d, _ = daemon_bridge
    params = {"message": "subframe", "url": "https://owned.example/", "frameId": "CHILD"}
    if legacy:
        d._record_event("Target.receivedMessageFromTarget", {
            "sessionId": "SESSION-MINE",
            "message": json.dumps({"method": "Page.javascriptDialogOpening", "params": params}),
        }, "FOREIGN-OUTER-CARRIER")
    else:
        d._record_event("Page.javascriptDialogOpening", params, "SESSION-MINE")
    assert helpers.drain_events() == []
    assert d.dialog is None


def test_legacy_target_reply_ignores_outer_owned_carrier_and_malformed_nested_messages(daemon_bridge):
    d, _ = daemon_bridge
    events = [
        {"method": "Target.receivedMessageFromTarget",
         "params": {"sessionId": "FOREIGN-SESSION", "message": json.dumps({"id": 3})},
         "session_id": "SESSION-MINE"},
        {"method": "Target.receivedMessageFromTarget",
         "params": {"sessionId": "SESSION-MINE", "message": "not-json"},
         "session_id": "SESSION-MINE"},
        {"method": "Target.receivedMessageFromTarget",
         "params": {"message": json.dumps({"id": 4})},
         "session_id": "SESSION-MINE"},
    ]
    for event in events:
        d._record_event(event["method"], event["params"], event["session_id"])
    assert helpers.drain_events() == []
    assert list(d.events) == []


def test_legacy_privileged_navigation_payload_is_discarded(daemon_bridge):
    d, _ = daemon_bridge
    event = {
        "method": "Target.receivedMessageFromTarget",
        "params": {
            "sessionId": "SESSION-MINE",
            "message": json.dumps({
                "method": "Page.frameNavigated",
                "params": {"frame": {"url": "chrome://settings"}},
            }),
        },
        "session_id": "FOREIGN-OUTER-CARRIER",
    }
    d._record_event(event["method"], event["params"], event["session_id"])
    assert helpers.drain_events() == []


async def _send_raw_for_guard_reset(self, method, params=None, session_id=None):
    self.calls.append((method, params or {}, session_id))
    if method == "Target.getTargetInfo":
        return {"targetInfo": {"type": "page", "targetId": "MINE", "url": "https://owned.example/"}}
    return {}


def test_guard_reset_revokes_queued_and_future_marker_work(monkeypatch):
    monkeypatch.setenv("BH_TAB_GUARD", "1")
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    d = daemon.Daemon()
    d.cdp = daemon_test_cdp = type("CDP", (), {
        "send_raw": _send_raw_for_guard_reset,
    })()
    daemon_test_cdp.calls = []
    d._guard_policy_active = True
    d._guarded_run_id = RUN_ID
    d._guarded_sessions = {"SESSION-MINE"}
    d._guarded_targets = {"MINE"}
    d._session_targets = {"SESSION-MINE": "MINE"}
    d._document_state["SESSION-MINE"] = {
        "target_id": "MINE", "generation": 0,
        "url": "https://owned.example/", "allowed": True,
    }
    d.session = "SESSION-MINE"
    d.target_id = "MINE"

    async def run():
        d._record_event("Page.loadEventFired", {}, "SESSION-MINE")
        response = await d.handle({"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                                   "tab_guard_epoch": d._authorization_epoch})
        d._record_event("Page.loadEventFired", {}, "SESSION-MINE")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return response

    response = asyncio.run(run())
    assert response == {"tab_guard": "ok", "tab_guard_run": RUN_ID}
    assert d._guard_policy_active is True
    assert d._guarded_sessions == set()
    assert d._guarded_targets == set()
    assert d.session is None
    assert d.target_id is None
    assert d._marker_tasks == set()
    assert not [call for call in daemon_test_cdp.calls if call[0] == "Runtime.evaluate"]


def test_reset_leaves_guard_enforcement_latched_for_omitted_fields(daemon_bridge):
    d, calls = daemon_bridge
    reset = asyncio.run(d.handle({
        "meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
        "tab_guard_epoch": d._authorization_epoch,
    }))
    assert reset["tab_guard"] == "ok"
    assert d._guard_policy_active is True
    calls.clear()
    for request in (
        {"method": "Runtime.evaluate", "params": {"expression": "1"}},
        {"meta": "current_tab"},
        {"meta": "connection_status"},
        {"meta": "drain_events"},
    ):
        response = asyncio.run(d.handle(request))
        assert response.get("tab_guard") == "refused"
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_shutdown_remains_available_after_guard_latches(daemon_bridge, monkeypatch):
    d, calls = daemon_bridge
    d.stop = asyncio.Event()
    reset = asyncio.run(d.handle({
        "meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
        "tab_guard_epoch": d._authorization_epoch,
    }))
    monkeypatch.setattr(daemon, "stop_remote", lambda strict=False: True)
    result = asyncio.run(d.handle({"meta": "shutdown"}))
    assert reset["tab_guard"] == "ok"
    assert result == {"ok": True}
    assert d.stop.is_set()
    assert not any(call[0] == "Runtime.evaluate" for call in calls)


def test_pending_detached_sessions_are_bounded_revoked_and_reset_pruned(daemon_bridge):
    d, _ = daemon_bridge
    for i in range(300):
        d._record_browser_lifecycle_event("Target.detachedFromTarget", {"sessionId": f"S{i}"})
    assert len(d._pending_detached_sessions) == 256
    assert d._pending_detached_sessions_overflowed is True
    assert "S0" not in d._pending_detached_sessions
    assert "S299" in d._pending_detached_sessions
    d._revoke_event_ownership({"S299"})
    assert "S299" not in d._pending_detached_sessions
    d._pending_detached_sessions["pending"] = None
    response = asyncio.run(d.handle({
        "meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
        "tab_guard_epoch": d._authorization_epoch,
    }))
    assert response["tab_guard"] == "ok"
    assert d._pending_detached_sessions == {}
    assert d._pending_detached_sessions_overflowed is False


def test_delayed_old_run_reset_cannot_revoke_newer_run(daemon_bridge):
    d, _ = daemon_bridge
    old_epoch = d._authorization_epoch
    old_reset = {"meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
                 "tab_guard_epoch": old_epoch}

    async def run():
        await d._session_state_lock.acquire()
        pending = asyncio.create_task(d.handle(old_reset))
        await asyncio.sleep(0)
        d._guarded_run_id = RUN_ID_2
        d._authorization_epoch += 1
        d._guard_policy_active = True
        d._guarded_sessions = {"SESSION-NEW"}
        d._guarded_targets = {"TARGET-NEW"}
        d._session_state_lock.release()
        return await pending

    response = asyncio.run(run())
    assert response["tab_guard"] == "refused"
    assert response["tab_guard_run"] == RUN_ID_2
    assert d._guarded_run_id == RUN_ID_2
    assert d._guarded_sessions == {"SESSION-NEW"}
    assert d._guarded_targets == {"TARGET-NEW"}


@pytest.mark.parametrize("method", [
    "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
])
@pytest.mark.parametrize("change", ["generation", "url", "allowed"])
def test_target_scoped_sessionless_dispatch_rejects_stale_document_snapshot(
        daemon_bridge, method, change):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, method, {"targetId": "MINE"})
    request["session_id"] = None
    if change == "generation":
        d._document_state["SESSION-MINE"]["generation"] += 1
    elif change == "url":
        d._document_state["SESSION-MINE"]["document_url"] = "https://next.example/"
    else:
        d._document_state["SESSION-MINE"]["allowed"] = False
    before = len(calls)
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == method for call in calls[before:])


@pytest.mark.parametrize("method", [
    "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
])
def test_target_scoped_dispatch_revalidates_document_after_target_lookup(daemon_bridge, method):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, method, {"targetId": "MINE"})
    request["session_id"] = None
    original = d._validate_dispatch_identity

    async def validate_then_navigate(*args, **kwargs):
        identity = await original(*args, **kwargs)
        if identity is not None:
            state = d._document_state["SESSION-MINE"]
            state["generation"] += 1
            state["document_url"] = "https://next.example/"
        return identity

    d._validate_dispatch_identity = validate_then_navigate
    before = len(calls)
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == method for call in calls[before:])


@pytest.mark.parametrize("method", [
    "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
])
def test_target_scoped_handler_allows_owned_current_document(daemon_bridge, method):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, method, {"targetId": "MINE"})
    request["session_id"] = None
    if method == "Target.attachToTarget":
        request["tab_guard_session_id"] = None
        request["tab_guard_document_generation"] = None
        # Exercise first attachment: the daemon knows this run created the
        # target, but no session mapping exists yet.
        d._session_targets.clear()
        d._guarded_sessions.clear()
        d._document_state.clear()
        request["tab_guard_url"] = "https://owned.example/"
        request["tab_guard"]["sessions"] = []
    response = asyncio.run(d.handle(request))
    assert "error" not in response
    assert any(call[0] == method for call in calls)
    if method == "Target.attachToTarget":
        assert response["result"]["sessionId"] == "SESSION-MINE"
        assert d._session_targets["SESSION-MINE"] == "MINE"


def test_detach_before_attach_response_rejects_late_session_registration(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()

    async def attach_response(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        return {"sessionId": "SESSION-LATE"}

    d.cdp.send_raw = attach_response
    d._record_event("Target.detachedFromTarget", {"sessionId": "SESSION-LATE", "targetId": "MINE"})

    response = asyncio.run(d.handle(request))

    assert response == {"tab_guard": "refused", "error": "Target.attachToTarget session was detached before registration"}
    assert "SESSION-LATE" not in d._session_targets
    assert "SESSION-LATE" not in d._guarded_sessions
    assert "SESSION-LATE" not in d._document_state
    assert "SESSION-LATE" in d._revoked_sessions


def test_pending_detach_overflow_detaches_repeated_refused_sessions_without_growth(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()

    attached = 0
    detached = []

    async def attach_response(method, params=None, session_id=None):
        nonlocal attached
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            attached += 1
            return {"sessionId": f"SESSION-EVICTED-{attached}"}
        if method == "Target.detachFromTarget":
            detached.append(params["sessionId"])
            return {}
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_response
    for i in range(257):
        d._record_browser_lifecycle_event(
            "Target.detachedFromTarget",
            {"sessionId": f"SESSION-{i}"},
        )

    assert len(d._pending_detached_sessions) == 256
    assert "SESSION-0" not in d._pending_detached_sessions
    assert d._pending_detached_sessions_overflowed is True

    revoked_before = set(d._revoked_sessions)
    for i in range(300):
        response = asyncio.run(d.handle(request))
        assert response == {
            "tab_guard": "refused",
            "error": "pending detach history overflow; refusing attach registration",
        }
        session = f"SESSION-EVICTED-{i + 1}"
        assert session not in d._session_targets
        assert session not in d._guarded_sessions
        assert session not in d._document_state

    assert detached == [f"SESSION-EVICTED-{i}" for i in range(1, 301)]
    assert d._revoked_sessions == revoked_before


def test_overflow_attach_skips_detach_for_session_already_in_detach_history(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()

    async def attach_response(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            return {"sessionId": "SESSION-256"}
        if method == "Target.detachFromTarget":
            raise AssertionError("a session already known detached must not be detached again")
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_response
    for i in range(257):
        d._record_browser_lifecycle_event("Target.detachedFromTarget", {"sessionId": f"SESSION-{i}"})

    response = asyncio.run(d.handle(request))

    assert response == {
        "tab_guard": "refused",
        "error": "Target.attachToTarget session was detached before registration",
    }
    assert "SESSION-256" in d._revoked_sessions
    assert "SESSION-256" not in d._session_targets
    assert not any(call[0] == "Target.detachFromTarget" for call in calls)


def test_concurrent_overflow_attaches_cannot_overbook_cleanup_capacity(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()
    attached = 0

    async def attach_response(method, params=None, session_id=None):
        nonlocal attached
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            attached += 1
            await asyncio.sleep(0)
            return {"sessionId": f"SESSION-OVERFLOW-{attached}"}
        if method == "Target.detachFromTarget":
            await asyncio.sleep(0)
            raise RuntimeError("detach unavailable")
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_response
    for i in range(257):
        d._record_browser_lifecycle_event("Target.detachedFromTarget", {"sessionId": f"OLD-{i}"})

    async def run_concurrent_requests():
        return await asyncio.gather(*(d.handle(request) for _ in range(100)))

    responses = asyncio.run(run_concurrent_requests())

    assert all(response["tab_guard"] == "refused" for response in responses)
    assert attached == 1
    assert d._overflow_cleanup_sessions == {"SESSION-OVERFLOW-1": None}


def test_cancelled_overflow_attach_releases_cleanup_lock_and_slot(daemon_bridge):
    d, _ = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()
    entered_attach = asyncio.Event()
    wait_for_cancel = asyncio.Event()

    async def pending_attach(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            entered_attach.set()
            await wait_for_cancel.wait()
            return {"sessionId": "SESSION-CANCELLED"}
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = pending_attach
    for i in range(257):
        d._record_browser_lifecycle_event("Target.detachedFromTarget", {"sessionId": f"OLD-{i}"})

    async def cancel_during_attach():
        task = asyncio.create_task(d.handle(request))
        await asyncio.wait_for(entered_attach.wait(), timeout=2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled attach unexpectedly completed")

    asyncio.run(cancel_during_attach())

    assert not d._overflow_attach_lock.locked()
    assert d._guarded_attach_slots._value == 256


def test_cancelled_overflow_detach_preserves_session_for_retry(daemon_bridge):
    d, _ = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()
    detach_started = asyncio.Event()
    wait_for_cancel = asyncio.Event()

    async def attach_then_wait_on_detach(method, params=None, session_id=None):
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            return {"sessionId": "SESSION-CANCELLED-DETACH"}
        if method == "Target.detachFromTarget":
            assert params["sessionId"] == "SESSION-CANCELLED-DETACH"
            detach_started.set()
            await wait_for_cancel.wait()
            return {}
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_then_wait_on_detach
    for i in range(257):
        d._record_browser_lifecycle_event("Target.detachedFromTarget", {"sessionId": f"OLD-{i}"})

    async def cancel_during_detach():
        task = asyncio.create_task(d.handle(request))
        await asyncio.wait_for(detach_started.wait(), timeout=2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled detach unexpectedly completed")

    asyncio.run(cancel_during_detach())

    assert d._overflow_cleanup_sessions == {"SESSION-CANCELLED-DETACH": None}
    assert not d._overflow_attach_lock.locked()
    assert d._guarded_attach_slots._value == 256


def test_reset_does_not_hold_session_state_lock_while_retrying_cdp_cleanup(daemon_bridge):
    d, _ = daemon_bridge
    d._overflow_cleanup_sessions["SESSION-SLOW-CLEANUP"] = None
    cleanup_started = asyncio.Event()
    finish_cleanup = asyncio.Event()

    async def slow_cleanup(method, params=None, session_id=None):
        assert method == "Target.detachFromTarget"
        cleanup_started.set()
        await finish_cleanup.wait()
        return {}

    d.cdp.send_raw = slow_cleanup

    async def run_reset_and_probe_lock():
        reset = asyncio.create_task(d.handle({
            "meta": "tab_guard_reset",
            "tab_guard_run": RUN_ID,
            "tab_guard_epoch": d._authorization_epoch,
        }))
        await asyncio.wait_for(cleanup_started.wait(), timeout=1)
        await asyncio.wait_for(d._session_state_lock.acquire(), timeout=0.1)
        d._session_state_lock.release()
        finish_cleanup.set()
        return await reset

    response = asyncio.run(run_reset_and_probe_lock())

    assert response["tab_guard"] == "ok"
    assert d._overflow_cleanup_sessions == {}


def test_midflight_detach_overflow_keeps_every_failed_attach_retryable(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()
    entered = 0
    all_attaches_entered = asyncio.Event()
    release_attaches = asyncio.Event()

    async def attach_response(method, params=None, session_id=None):
        nonlocal entered
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            entered += 1
            session_number = entered
            if session_number == 256:
                all_attaches_entered.set()
            await release_attaches.wait()
            return {"sessionId": f"SESSION-INFLIGHT-{session_number}"}
        if method == "Target.detachFromTarget":
            raise RuntimeError("detach unavailable")
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_response
    async def run_overflow_during_dispatch():
        requests = [asyncio.create_task(d.handle(request)) for _ in range(257)]
        await asyncio.wait_for(all_attaches_entered.wait(), timeout=2)
        for i in range(257):
            d._record_browser_lifecycle_event(
                "Target.detachedFromTarget", {"sessionId": f"NEW-{i}"}
            )
        release_attaches.set()
        return await asyncio.gather(*requests)

    responses = asyncio.run(run_overflow_during_dispatch())

    assert all(response["tab_guard"] == "refused" for response in responses)
    assert entered == 256
    assert len(d._overflow_cleanup_sessions) == 256
    assert all(f"SESSION-INFLIGHT-{i}" in d._overflow_cleanup_sessions
               for i in range(1, 257))


def test_failed_overflow_detach_is_retained_bounded_and_retried_on_reset(daemon_bridge):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, "Target.attachToTarget", {"targetId": "MINE"})
    request["session_id"] = None
    request["tab_guard_session_id"] = None
    request["tab_guard_document_generation"] = None
    request["tab_guard_url"] = "https://owned.example/"
    request["tab_guard"]["sessions"] = []
    d._session_targets.clear()
    d._guarded_sessions.clear()
    d._document_state.clear()

    detached = []
    fail_detach = True

    async def attach_response(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        if method == "Target.getTargetInfo":
            return {"targetInfo": {"type": "page", "targetId": "MINE",
                                   "url": "https://owned.example/", "title": "Owned"}}
        if method == "Target.attachToTarget":
            return {"sessionId": "SESSION-NEEDS-CLEANUP"}
        if method == "Target.detachFromTarget":
            detached.append(params["sessionId"])
            if fail_detach:
                raise RuntimeError("detach unavailable")
            return {}
        raise AssertionError(f"unexpected CDP method: {method}")

    d.cdp.send_raw = attach_response
    for i in range(257):
        d._record_browser_lifecycle_event(
            "Target.detachedFromTarget", {"sessionId": f"SESSION-{i}"}
        )

    response = asyncio.run(d.handle(request))
    assert response["tab_guard"] == "refused"
    assert d._overflow_cleanup_sessions == {"SESSION-NEEDS-CLEANUP": None}
    assert "SESSION-NEEDS-CLEANUP" not in d._session_targets

    attach_count = sum(call[0] == "Target.attachToTarget" for call in calls)
    for _ in range(300):
        response = asyncio.run(d.handle(request))
        assert response == {
            "tab_guard": "refused",
            "error": "pending overflow session cleanup; refusing attach registration",
        }
        assert len(d._overflow_cleanup_sessions) == 1
    assert sum(call[0] == "Target.attachToTarget" for call in calls) == attach_count

    fail_detach = False
    reset = asyncio.run(d.handle({
        "meta": "tab_guard_reset", "tab_guard_run": RUN_ID,
        "tab_guard_epoch": d._authorization_epoch,
    }))
    assert reset["tab_guard"] == "ok"
    assert detached.count("SESSION-NEEDS-CLEANUP") == 302
    assert d._overflow_cleanup_sessions == {}


@pytest.mark.parametrize("method", [
    "Target.closeTarget", "Target.activateTarget", "Target.attachToTarget",
])
@pytest.mark.parametrize("failure", ["foreign", "stale"])
def test_target_scoped_handler_refuses_foreign_or_stale_document(daemon_bridge, method, failure):
    d, calls = daemon_bridge
    request = _guarded_dispatch_request(d, method, {"targetId": "MINE"})
    request["session_id"] = None
    if failure == "foreign":
        request["params"]["targetId"] = "FOREIGN"
        request["tab_guard"]["tabs"] = ["FOREIGN"]
        request["tab_guard_target_id"] = "FOREIGN"
    else:
        d._document_state["SESSION-MINE"]["document_url"] = "https://next.example/"
    before = len(calls)
    response = asyncio.run(d.handle(request))
    assert response == {"tab_guard": "refused", "error": "tab guard authorization is stale or invalid"}
    assert not any(call[0] == method for call in calls[before:])


def test_context_wide_event_subscription_is_refused_and_foreign_events_stay_hidden(daemon_bridge):
    d, calls = daemon_bridge
    helpers.cdp("Network.enable")
    d._record_event("ServiceWorker.workerVersionUpdated", {"secret": "foreign"}, "FOREIGN-SESSION")
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("ServiceWorker.enable")
    assert helpers.drain_events() == []
    assert len(d.events) == 0
    assert ("Network.enable", {}, "SESSION-MINE") in calls


def test_older_daemon_cannot_silently_return_unguarded_metadata(owning, monkeypatch):
    monkeypatch.setattr(helpers, "_send", lambda req: {"dialog": {"message": "private"}})
    with pytest.raises(helpers.TabGuardRefused):
        helpers.page_info()


def test_metadata_snapshot_stays_owned_during_concurrent_switch(daemon_bridge):
    d, _ = daemon_bridge
    async def send_raw(method, params=None, session_id=None):
        assert params == {"targetId": "MINE"}
        d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
        await asyncio.sleep(0)
        return {"targetInfo": {"targetId": "MINE", "type": "page", "url": "https://owned.example/"}}
    d.cdp.send_raw = send_raw
    response = helpers._read_meta("connection_status")
    assert response["target_id"] == "MINE"
    assert response["session_id"] == "SESSION-MINE"


def test_pinned_request_never_uses_new_current_session_or_recovers_there(daemon_bridge, monkeypatch):
    d, calls = daemon_bridge
    original_send = helpers._send
    def switch_after_snapshot(req, **kwargs):
        response = original_send(req, **kwargs)
        if req.get("meta") == "guard_context":
            d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
        return response
    monkeypatch.setattr(helpers, "_send", switch_after_snapshot)
    helpers.cdp("Page.navigate", url="https://owned.example/")
    assert next(call for call in calls if call[0] == "Page.navigate")[2] == "SESSION-MINE"
    # A dropped pinned session must error, never replay against the new tab.
    d.target_id, d.session = "MINE", "SESSION-MINE"
    async def stale(method, params=None, session_id=None):
        calls.append((method, params, session_id))
        raise RuntimeError("Session with given id not found")
    d.cdp.send_raw = stale
    count = len(calls)
    with pytest.raises(helpers.TabGuardRefused, match="mapping"):
        helpers.cdp("Page.navigate", url="https://owned.example/")
    assert len(calls) == count + 1
    assert calls[-1][0] == "Target.getTargetInfo"


def test_guarded_switch_does_not_disable_foreign_session(daemon_bridge, monkeypatch):
    d, calls = daemon_bridge
    monkeypatch.setenv("BH_TAB_MARKER", "0")
    d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
    helpers._read_meta("set_session", target_id="MINE", session_id="SESSION-MINE")
    assert d.target_id == "MINE"
    assert all(sid in {None, "SESSION-MINE"} for _, _, sid in calls)
    assert not any(sid == "FOREIGN-SESSION" for _, _, sid in calls)


def test_guarded_switch_rejects_foreign_session(daemon_bridge):
    d, calls = daemon_bridge
    with pytest.raises(helpers.TabGuardRefused):
        helpers._read_meta("set_session", target_id="MINE", session_id="FOREIGN-SESSION")
    assert d.session == "SESSION-MINE"
    assert not any(sid == "FOREIGN-SESSION" for _, _, sid in calls)


@pytest.mark.parametrize("nested", [False, True])
def test_explicit_owned_iframe_session_resolves_its_mapped_target_before_dispatch(
    owning, monkeypatch, nested
):
    helpers._remember("tabs", "IFRAME-TARGET")
    helpers._remember("sessions", "IFRAME-SESSION")
    calls = []

    def send(req, **kwargs):
        calls.append(req)
        if req.get("meta") == "guard_epoch":
            return {"tab_guard": "ok", "tab_guard_epoch": 0, "tab_guard_run": RUN_ID}
        if req.get("meta") == "guard_context":
            assert req.get("session_id") == "IFRAME-SESSION"
            return {
                "target_id": "IFRAME-TARGET",
                "session_id": "IFRAME-SESSION",
                "url": "https://frame.example/",
                "tab_guard": "ok", "tab_guard_epoch": 0, "document_generation": 0,
            }
        return {"result": {}}

    monkeypatch.setattr(helpers, "_send", send)
    if nested:
        helpers.cdp(
            "Target.sendMessageToTarget",
            sessionId="IFRAME-SESSION",
            message=json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
        )
        dispatched = calls[-1]
        assert dispatched["params"]["sessionId"] == "IFRAME-SESSION"
    else:
        helpers.cdp("Runtime.evaluate", session_id="IFRAME-SESSION", expression="1")
        dispatched = calls[-1]
        assert dispatched["session_id"] == "IFRAME-SESSION"
    assert dispatched.get("method") in {"Runtime.evaluate", "Target.sendMessageToTarget"}


@pytest.mark.parametrize("nested", [False, True])
def test_guarded_direct_and_nested_dispatch_carry_full_snapshot(owning, monkeypatch, nested):
    requests = []
    send = helpers._send

    def capture(req, **kwargs):
        requests.append(req)
        return send(req, **kwargs)

    monkeypatch.setattr(helpers, "_send", capture)
    if nested:
        helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE",
                    message=json.dumps({"id": 902, "method": "Runtime.evaluate",
                                        "params": {"expression": "1"}}))
    else:
        helpers.cdp("Runtime.evaluate", session_id="SESSION-MINE", expression="1")
    dispatch = next(req for req in reversed(requests) if req.get("method"))
    assert dispatch["tab_guard_run"] == RUN_ID
    assert dispatch["tab_guard_epoch"] == 0
    assert dispatch["tab_guard_target_id"] == "MINE"
    assert dispatch["tab_guard_session_id"] == "SESSION-MINE"
    assert dispatch["tab_guard_document_generation"] == 0
    assert dispatch["tab_guard_url"] == "https://example.com/"


@pytest.mark.parametrize("nested", [False, True])
def test_explicit_session_with_unknown_mapped_target_fails_closed_before_dispatch(
    owning, monkeypatch, nested
):
    helpers._remember("sessions", "IFRAME-SESSION")
    calls = []

    def send(req, **kwargs):
        calls.append(req)
        if req.get("meta") == "guard_context":
            return {"target_id": "UNKNOWN-TARGET", "session_id": "IFRAME-SESSION", "url": "https://frame.example/"}
        return {"result": {}}

    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        if nested:
            helpers.cdp(
                "Target.sendMessageToTarget",
                sessionId="IFRAME-SESSION",
                message=json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "1"}}),
            )
        else:
            helpers.cdp("Runtime.evaluate", session_id="IFRAME-SESSION", expression="1")
    assert not any(req.get("method") for req in calls)


def test_old_daemon_refused_before_session_switch(owning, monkeypatch):
    requests = []
    def old_daemon(req):
        requests.append(req)
        return {"session_id": "SESSION-MINE"}
    monkeypatch.setattr(helpers, "_send", old_daemon)
    with pytest.raises(helpers.TabGuardRefused, match="reloaded"):
        helpers._read_meta("set_session", target_id="MINE", session_id="SESSION-MINE")
    assert [req["meta"] for req in requests] == ["guard_epoch"]


@pytest.mark.parametrize("meta", ["current_tab", "pending_dialog", "session", "drain_events"])
def test_metadata_connection_failure_is_a_guard_refusal(owning, monkeypatch, meta):
    def disconnected(req):
        raise RuntimeError("cdp_disconnected")
    monkeypatch.setattr(helpers, "_send", disconnected)
    with pytest.raises(helpers.TabGuardRefused, match="failing closed"):
        helpers._read_meta(meta)


@pytest.mark.parametrize("failure", ["disconnected", "missing-tree", "foreign-frame"])
def test_iframe_proof_failure_never_dispatches_attach(owning, monkeypatch, failure):
    calls = []
    base = _fake_send(current={"targetId": "MINE"}, target_type="iframe")
    def send(req, **kwargs):
        calls.append(req)
        if req.get("method") == "Page.getFrameTree":
            if failure == "disconnected":
                raise RuntimeError("cdp_disconnected")
            if failure == "missing-tree":
                return {"result": {}}
            return {"result": {"frameTree": {"frame": {"id": "MINE"},
                "childFrames": [{"frame": {"id": "OTHER-IFRAME"}}]}}}
        return base(req, **kwargs)
    monkeypatch.setattr(helpers, "_send", send)
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.attachToTarget", targetId="FOREIGN-IFRAME")
    assert not any(r.get("method") == "Target.attachToTarget" for r in calls)


@pytest.mark.parametrize("message", [
    "{bad json", "null", "[]", "{}", '{"method": 3}',
    '{"method":"Runtime.evaluate","sessionId":"FOREIGN"}',
    '{"method":"Target.sendMessageToTarget","params":{"sessionId":"FOREIGN"}}',
])
def test_message_routing_envelope_cannot_escape_owned_session(owning, monkeypatch, message):
    calls = []
    monkeypatch.setattr(helpers, "_send", lambda req, **kwargs: calls.append(req))
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.sendMessageToTarget", sessionId="SESSION-MINE", message=message)
    assert calls == []


def test_unknown_target_routing_method_fails_closed(owning):
    with pytest.raises(helpers.TabGuardRefused):
        helpers.cdp("Target.autoAttachRelated", targetId="FOREIGN")


def test_failed_atomic_write_preserves_record_and_removes_temporary(owning, monkeypatch, capsys):
    path = helpers._owned_path()
    before = path.read_bytes()
    def fail_replace(src, dst):
        raise OSError("replace failed")
    monkeypatch.setattr(helpers.os, "replace", fail_replace)
    helpers._own_tab("SECOND")
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == sorted(
        [path.name, path.name + ".lock"]
    )
    assert "WARNING" in capsys.readouterr().err


def test_run_reset_removes_its_record(owning):
    path = helpers._owned_path()
    helpers.tab_guard_reset()
    assert not path.exists()
    assert helpers._owned_ids() == set()
    assert helpers._owned_sessions() == set()


def test_run_reset_propagates_lock_failure(guard, monkeypatch):
    def fail(_path):
        raise OSError("lock failed")
    monkeypatch.setattr(helpers, "_ownership_lock", fail)
    with pytest.raises(OSError, match="lock failed"):
        helpers.tab_guard_reset()


def test_run_reset_propagates_unlink_failure(guard, monkeypatch):
    class FailingPath:
        def unlink(self):
            raise PermissionError("unlink failed")

    class NoopLock:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(helpers, "_owned_path", lambda: FailingPath())
    monkeypatch.setattr(helpers, "_ownership_lock", lambda _path: NoopLock())
    with pytest.raises(PermissionError, match="unlink failed"):
        helpers.tab_guard_reset()


@pytest.mark.parametrize("tool", ["browser_page_info", "browser_current_tab"])
def test_mcp_metadata_tools_cannot_return_foreign_dialog_or_page(daemon_bridge, monkeypatch, tool):
    pytest.importorskip("mcp")
    from mcp_types import CallToolRequestParams
    import mcp_server

    d, calls = daemon_bridge
    d.target_id, d.session = "FOREIGN", "FOREIGN-SESSION"
    d._record_event("Page.javascriptDialogOpening", {"message": "private dialog"}, "FOREIGN-SESSION")
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: None)
    result = asyncio.run(mcp_server.SERVER._handle_call_tool(
        None, CallToolRequestParams(name=tool, arguments={})))
    assert result.is_error is True
    assert "[tab-guard] REFUSED" in result.content[0].text
    assert "private dialog" not in result.content[0].text
    assert calls == []
