import asyncio
import json
import time
from pathlib import Path

import pytest

from browser_harness import daemon, sedu_login


ADAPTER = sedu_login.ADAPTER
SENTINEL_USER = b"sentinel-user"
SENTINEL_PASSWORD = b"sentinel-password"
RESULT_FIXTURE = Path(__file__).parents[1] / "fixtures" / "sedu-v1-results.jsonl"


def test_versioned_result_fixture_is_captured_from_exact_producer_bytes():
    states = ("active", "reauth_required", "human_challenge", "locked", "failed", "timeout")
    produced = b"".join(
        json.dumps(sedu_login._result(state)).encode("ascii") + b"\n"
        for state in states
    )
    assert produced == RESULT_FIXTURE.read_bytes()


class FakeCDP:
    def __init__(self, form=None, snapshots=None, navigate=None):
        self.calls = []
        self.form = form or {
            "href": sedu_login.FORM_ACTION,
            "title": "login",
            "body": "",
            "ready": "complete",
            "user": True,
            "password": True,
            "submit": True,
            "action": sedu_login.FORM_ACTION,
            "method": "post",
        }
        self.snapshots = list(snapshots or [{
            "href": "https://s-edu.cloud/npms/",
            "title": "S-EDU",
            "body": "",
            "ready": "complete",
            "protected": [True, True, True],
            "identity": 2,
        }])
        self.snapshot_calls = 0
        self.navigate = {"loaderId": "loader-1"} if navigate is None else navigate

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params or {}, session_id))
        if method == "Page.navigate":
            return self.navigate
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {
                "loaderId": "loader-1", "url": self.form.get("href", ""),
            }}}
        if method == "Runtime.evaluate":
            expression = (params or {}).get("expression")
            if expression == sedu_login._VALIDATE_FORM:
                return {"result": {"value": self.form}}
            if expression == sedu_login._DOCUMENT:
                return {"result": {"objectId": "document-1"}}
            self.snapshot_calls += 1
            if self.snapshot_calls == 1:
                return {"result": {"value": {
                    "href": self.form["href"], "title": self.form.get("title", ""),
                    "body": self.form.get("body", ""), "ready": self.form["ready"],
                    "protected": [False, False, False], "identity": 1,
                }}}
            return {"result": {"value": self.snapshots.pop(0)}}
        if method == "Runtime.callFunctionOn":
            return {"result": {"value": True}}
        raise AssertionError(method)


def make_daemon(cdp=None):
    d = daemon.Daemon()
    d.cdp = cdp or FakeCDP()
    d.target_id = "target-1"
    d.session = "session-1"
    d._session_generation = 3
    return d


async def begin_and_submit(d, payload=None):
    begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
    assert begun["status"] == "awaiting_secret"
    result = await d.accept_login_secret(
        begun["transaction_id"],
        payload or sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD),
        owner="owner",
    )
    if result.get("status") == "success":
        assert await d.acknowledge_login_handoff(
            begun["transaction_id"], "owner"
        ) == {"status": "handoff_complete"}
    return result


def test_sedu_exact_request_order_and_bound_session(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    cdp = FakeCDP()
    result = asyncio.run(begin_and_submit(make_daemon(cdp)))

    assert result == {"status": "success", "state": "active"}
    methods = [call[0] for call in cdp.calls]
    assert methods == [
        "Page.navigate", "Page.getFrameTree", "Runtime.evaluate", "Runtime.evaluate",
        "Runtime.callFunctionOn", "Runtime.evaluate", "Runtime.callFunctionOn",
        "Runtime.evaluate",
    ]
    assert cdp.calls[0][1] == {"url": sedu_login.INITIAL_LOGIN_URL}
    assert all(call[2] == "session-1" for call in cdp.calls)
    assert methods.count("Page.navigate") == 1
    assert not any(method in {"Page.reload", "Network.clearBrowserCache", "Network.clearBrowserCookies"}
                   for method in methods)
    assert all("status" not in json.dumps(params).casefold() for method, params, _ in cdp.calls
               if method == "Page.navigate")
    # Secrets are CDP arguments only; they never become executable JavaScript or a result.
    expressions = " ".join(str(call[1].get("expression", "")) for call in cdp.calls)
    assert "sentinel" not in expressions
    assert "sentinel" not in json.dumps(result)


def test_sensitive_network_post_data_is_suppressed_and_purged(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    class CredentialEventCDP(FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            if method == "Runtime.callFunctionOn" and (params or {}).get(
                    "functionDeclaration") == sedu_login._FILL_FUNCTION:
                # A malicious input listener leaks synchronously, before submit.
                self.daemon._record_event("Runtime.consoleAPICalled", {
                    "args": [{"value": "sentinel-user:sentinel-password"}],
                }, session_id)
                self.daemon._record_event("Log.entryAdded", {
                    "entry": {"text": "sentinel-password"},
                }, session_id)
            if method == "Runtime.callFunctionOn" and (params or {}).get(
                    "functionDeclaration") == sedu_login._SUBMIT_FUNCTION:
                async def deliver_event():
                    await asyncio.sleep(0)
                    self.daemon._record_event("Network.requestWillBeSent", {
                        "request": {"postData": "username=sentinel-user&password=sentinel-password"},
                    }, session_id)
                    self.daemon._record_event("DOM.attributeModified", {
                        "value": "sentinel-password",
                    }, session_id)

                callback = asyncio.create_task(deliver_event())
                await asyncio.sleep(0)
                await callback
            return await super().send_raw(method, params, session_id)

    cdp = CredentialEventCDP()
    d = make_daemon(cdp)
    d._record_event("Runtime.consoleAPICalled", {"value": "sentinel-before-fill"}, "session-1")
    d._record_event("Runtime.consoleAPICalled", {"value": "safe-other-session"}, "session-2")
    cdp.daemon = d
    assert asyncio.run(begin_and_submit(d)) == {"status": "success", "state": "active"}
    drained = asyncio.run(d.handle({"meta": "drain_events"}, owner="owner"))
    assert "sentinel" not in json.dumps(drained)
    assert drained == {"events": [{
        "method": "Runtime.consoleAPICalled",
        "params": {"value": "safe-other-session"},
        "session_id": "session-2",
    }]}


def test_success_waits_for_owner_ack_and_rejects_replay_or_wrong_owner(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    async def case():
        d = make_daemon()
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        tx_id = begun["transaction_id"]
        result = await d.accept_login_secret(
            tx_id, sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD), "owner"
        )
        assert result == {"status": "success", "state": "active"}
        assert d._login_transaction.phase == "awaiting_handoff"
        assert await d.handle({"method": "Runtime.evaluate", "params": {}}, owner="other") == {
            "error": "login_transaction_active",
        }
        assert await d.acknowledge_login_handoff(tx_id, "other") == {
            "error": "wrong_login_transaction",
        }
        assert await d.acknowledge_login_handoff("00" * 16, "owner") == {
            "error": "wrong_login_transaction",
        }
        assert await d.acknowledge_login_handoff(tx_id, "owner") == {
            "status": "handoff_complete",
        }
        assert await d.acknowledge_login_handoff(tx_id, "owner") == {
            "error": "no_login_transaction",
        }

    asyncio.run(case())


def test_cancel_wins_when_control_and_adapter_complete_together(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    async def case():
        d = make_daemon()
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        tx_id = begun["transaction_id"]
        async def completed_adapter(*_args):
            return {"status": "success", "state": "active"}
        monkeypatch.setattr(d, "accept_login_secret", completed_adapter)
        reader = asyncio.StreamReader()
        reader.feed_data(daemon.ipc.LOGIN_FRAME_HEADER.pack(
            daemon.ipc.LOGIN_ABORT_OPCODE, bytes.fromhex(tx_id), 0
        ))
        result = await daemon._run_login_adapter_owned(
            d, reader, "owner", tx_id, bytearray(b"x"), d._login_transaction.deadline
        )
        assert result == {"status": "aborted"}
        assert d._login_transaction is None

    asyncio.run(case())


def test_navigation_waits_for_redirected_complete_form_without_second_navigation(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    loading = FakeCDP().form.copy()
    loading.update(href=sedu_login.INITIAL_LOGIN_URL, ready="loading")

    class RedirectingCDP(FakeCDP):
        def __init__(self):
            super().__init__()
            self.forms = [loading, self.form]

        async def send_raw(self, method, params=None, session_id=None):
            if method == "Runtime.evaluate" and (params or {}).get(
                    "expression") == sedu_login._VALIDATE_FORM:
                self.form = self.forms.pop(0)
            return await super().send_raw(method, params, session_id)

    cdp = RedirectingCDP()
    assert asyncio.run(begin_and_submit(make_daemon(cdp))) == {
        "status": "success", "state": "active",
    }
    assert [method for method, _params, _session in cdp.calls].count("Page.navigate") == 1


def test_post_submit_loading_waits_and_every_call_uses_one_deadline(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    loading = {
        "href": sedu_login.FORM_ACTION, "title": "", "body": "",
        "ready": "loading", "protected": [False, False, False],
    }
    active = {
        "href": "https://s-edu.cloud/npms/", "title": "S-EDU", "body": "",
        "ready": "complete", "protected": [True, True, True],
    }
    cdp = FakeCDP(snapshots=[loading, active])
    deadlines = []
    original_call = sedu_login._call

    async def recording_call(d, tx, method, params, deadline=None):
        if params.get("expression") == sedu_login._SNAPSHOT or params.get(
                "functionDeclaration") == sedu_login._SUBMIT_FUNCTION:
            deadlines.append((method, deadline))
        return await original_call(d, tx, method, params, deadline)

    monkeypatch.setattr(sedu_login, "_call", recording_call)
    assert asyncio.run(begin_and_submit(make_daemon(cdp))) == {
        "status": "success", "state": "active",
    }
    protected_deadlines = [deadline for _method, deadline in deadlines]
    assert len(protected_deadlines) == 4
    assert len(set(protected_deadlines)) == 1
    assert protected_deadlines[0] is not None


def test_post_submit_transient_navigation_context_is_retried(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    class NavigatingCDP(FakeCDP):
        def __init__(self):
            super().__init__()
            self.transient = True

        async def send_raw(self, method, params=None, session_id=None):
            if (method == "Runtime.evaluate" and (params or {}).get("expression") == sedu_login._SNAPSHOT
                    and self.snapshot_calls == 1 and self.transient):
                self.transient = False
                self.calls.append((method, params or {}, session_id))
                raise RuntimeError("Execution context was destroyed, most likely because of a navigation")
            return await super().send_raw(method, params, session_id)

    cdp = NavigatingCDP()
    assert asyncio.run(begin_and_submit(make_daemon(cdp))) == {"status": "success", "state": "active"}
    assert sum(method == "Runtime.evaluate" and params.get("expression") == sedu_login._SNAPSHOT
               for method, params, _sid in cdp.calls) == 3


@pytest.mark.parametrize("form", [
    {"href": "http://s-edu.cloud/npms/accounts/login/", "ready": "complete",
     "user": True, "password": True, "submit": True,
     "action": sedu_login.FORM_ACTION, "method": "post", "title": "", "body": ""},
    {"href": "https://evil.example/npms/accounts/login/", "ready": "complete",
     "user": True, "password": True, "submit": True,
     "action": sedu_login.FORM_ACTION, "method": "post", "title": "", "body": ""},
    {"href": sedu_login.FORM_ACTION, "ready": "complete",
     "user": True, "password": True, "submit": True,
     "action": "https://evil.example/steal", "method": "post", "title": "", "body": ""},
    {"href": sedu_login.FORM_ACTION, "ready": "complete",
     "user": True, "password": True, "submit": True,
     "action": sedu_login.FORM_ACTION, "method": "get", "title": "", "body": ""},
])
def test_wrong_origin_path_or_form_fails_before_fill(monkeypatch, form):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    cdp = FakeCDP(form=form)
    assert asyncio.run(begin_and_submit(make_daemon(cdp))) == {"status": "failed", "state": "failed"}
    assert [call[0] for call in cdp.calls] == [
        "Page.navigate", "Page.getFrameTree", "Runtime.evaluate",
    ]


@pytest.mark.parametrize(("body", "expected"), [
    ("429 Too Many Requests", "locked"),
    ("보안문자 CAPTCHA", "human_challenge"),
])
def test_rate_limit_and_challenge_detected_before_fill(monkeypatch, body, expected):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    form = FakeCDP().form.copy()
    form["body"] = body
    cdp = FakeCDP(form=form)
    assert asyncio.run(begin_and_submit(make_daemon(cdp))) == {"status": "failed", "state": expected}
    assert [call[0] for call in cdp.calls] == [
        "Page.navigate", "Page.getFrameTree", "Runtime.evaluate",
    ]


def test_reauth_and_unproven_navigation_are_not_success(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    reauth = FakeCDP(snapshots=[{
        "href": sedu_login.FORM_ACTION, "title": "login", "body": "bad password",
        "ready": "complete", "protected": False, "identity": 2,
    }])
    assert asyncio.run(begin_and_submit(make_daemon(reauth))) == {
        "status": "failed", "state": "reauth_required",
    }

    unproven = FakeCDP(snapshots=[{
        "href": "https://s-edu.cloud/npms/", "title": "", "body": "",
        "ready": "complete", "protected": [True, False, False],
    }])
    assert asyncio.run(begin_and_submit(make_daemon(unproven))) == {
        "status": "failed", "state": "failed",
    }


def test_navigation_failure_and_timeout_are_bounded(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    failed = FakeCDP(navigate={"errorText": "net::ERR_FAILED"})
    assert asyncio.run(begin_and_submit(make_daemon(failed))) == {
        "status": "failed", "state": "failed",
    }

    class SlowCDP(FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            if method == "Page.navigate":
                await asyncio.sleep(1)
            return await super().send_raw(method, params, session_id)

    async def timeout_case():
        d = make_daemon(SlowCDP())
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        d._login_transaction.deadline = time.monotonic() + 0.01
        return await d.accept_login_secret(
            begun["transaction_id"], sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD), "owner"
        )

    assert asyncio.run(timeout_case()) == {"status": "failed", "state": "timeout"}


def test_wrong_target_session_generation_and_payload_never_reach_cdp(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    async def binding_case(field, value):
        cdp = FakeCDP()
        d = make_daemon(cdp)
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        setattr(d, field, value)
        result = await d.accept_login_secret(
            begun["transaction_id"], sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD), "owner"
        )
        return result, cdp.calls

    for field, value in (("target_id", "wrong"), ("session", "wrong"), ("_session_generation", 4)):
        result, calls = asyncio.run(binding_case(field, value))
        assert result == {"error": "stale_login_transaction"}
        assert calls == []

    cdp = FakeCDP()
    malformed = bytearray(b"sentinel-malformed")
    result = asyncio.run(begin_and_submit(make_daemon(cdp), malformed))
    assert result == {"status": "failed", "state": "failed"}
    assert cdp.calls == []
    assert not any(malformed)
    assert "sentinel" not in json.dumps(result)


def test_payload_total_boundary_includes_eight_byte_length_header():
    maximum = sedu_login.encode_payload(b"u", b"p" * (16 * 1024 - 9))
    assert len(maximum) == 16 * 1024
    assert sedu_login._parse_payload(maximum)[:2] == (
        "u", "p" * (16 * 1024 - 9),
    )
    with pytest.raises(ValueError):
        sedu_login.encode_payload(b"u", b"p" * (16 * 1024 - 8))
    with pytest.raises(ValueError):
        sedu_login.encode_payload(b"u" * (16 * 1024 - 8), b"p")


def test_unchanged_complete_pre_click_document_is_not_immediate_reauth(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    monkeypatch.setattr(sedu_login, "_POST_SUBMIT_SECONDS", 0.02)
    unchanged = {
        "href": sedu_login.FORM_ACTION, "title": "login", "body": "",
        "ready": "complete", "protected": [False, False, False], "identity": 1,
    }

    class UnchangedCDP(FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            if method == "Runtime.evaluate" and (params or {}).get("expression") == sedu_login._SNAPSHOT:
                return {"result": {"value": unchanged}}
            return await super().send_raw(method, params, session_id)

    assert asyncio.run(begin_and_submit(make_daemon(UnchangedCDP()))) == {
        "status": "failed", "state": "timeout",
    }


def test_owner_disconnect_cancels_blocked_cdp_before_later_mutation(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")

    async def case():
        entered = asyncio.Event()

        class BlockedCDP(FakeCDP):
            async def send_raw(self, method, params=None, session_id=None):
                self.calls.append((method, params or {}, session_id))
                if method == "Page.navigate":
                    entered.set()
                    await asyncio.Event().wait()
                raise AssertionError("mutation continued after cancelled navigation")

        d = make_daemon(BlockedCDP())
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        reader = asyncio.StreamReader()
        task = asyncio.create_task(daemon._run_login_adapter_owned(
            d, reader, "owner", begun["transaction_id"],
            bytearray(sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD)),
            d._login_transaction.deadline,
        ))
        await entered.wait()
        reader.feed_eof()
        assert await asyncio.wait_for(task, 0.5) is None
        assert [call[0] for call in d.cdp.calls] == ["Page.navigate"]
        assert d._login_transaction is None

    asyncio.run(case())


def test_uncooperative_cancel_resets_transport_before_handoff(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "sedu-test")
    monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
    monkeypatch.setattr(daemon, "LOGIN_CANCEL_DRAIN_TIMEOUT", 0.01)
    monkeypatch.setattr(daemon, "get_ws_url", lambda: "ws://replacement")

    async def case():
        entered = asyncio.Event()

        class UncooperativeCDP(FakeCDP):
            def __init__(self):
                super().__init__()
                self.closed = asyncio.Event()

            async def send_raw(self, method, params=None, session_id=None):
                self.calls.append((method, params or {}, session_id))
                if method != "Page.navigate":
                    raise AssertionError("late mutation after cancelled navigation")
                entered.set()
                while not self.closed.is_set():
                    try:
                        await self.closed.wait()
                    except asyncio.CancelledError:
                        continue
                return {"loaderId": "too-late"}

            async def stop(self):
                self.closed.set()

        class ReplacementCDP:
            def __init__(self):
                self.calls = []

            async def start(self):
                return None

            async def send_raw(self, method, params=None, session_id=None):
                self.calls.append((method, params or {}, session_id))
                if method == "Target.getTargets":
                    return {"targetInfos": [{
                        "targetId": "target-1", "type": "page", "url": "https://s-edu.cloud/npms/",
                    }]}
                if method == "Target.attachToTarget":
                    return {"sessionId": "replacement-session"}
                if method.endswith(".enable"):
                    return {}
                if method == "Runtime.evaluate":
                    return {"handoff": "safe"}
                raise AssertionError(method)

        old = UncooperativeCDP()
        replacement = ReplacementCDP()
        monkeypatch.setattr(daemon, "_new_cdp_client", lambda _url: replacement)
        d = make_daemon(old)
        begun = await d.handle({"meta": "login_begin", "adapter": ADAPTER}, owner="owner")
        reader = asyncio.StreamReader()
        adapter_owner = asyncio.create_task(daemon._run_login_adapter_owned(
            d, reader, "owner", begun["transaction_id"],
            bytearray(sedu_login.encode_payload(SENTINEL_USER, SENTINEL_PASSWORD)),
            d._login_transaction.deadline,
        ))
        await entered.wait()
        reader.feed_eof()
        assert await asyncio.wait_for(adapter_owner, 0.5) is None
        assert d._login_transaction is None
        assert d._execution_quarantined is False
        handoff = await d.handle({"method": "Runtime.evaluate", "params": {"expression": "safe"}})
        return d, old, replacement, handoff

    d, old, replacement, handoff = asyncio.run(case())
    assert [method for method, _params, _sid in old.calls] == ["Page.navigate"]
    assert handoff == {"result": {"handoff": "safe"}}
    assert d.cdp is replacement
    assert d.session == "replacement-session"
