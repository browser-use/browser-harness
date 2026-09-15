import asyncio
import json

import pytest

from browser_harness import daemon, fixed_login

USER = b"adapter-sentinel-user"
PASSWORD = b"adapter-sentinel-password"


class FakeCDP:
    def __init__(self, site, *, form=None, after=None):
        self.site = site
        self.calls = []
        self.validate, self.fill, self.submit, self.snapshot = fixed_login._expressions(site)
        self.form = form or {
            "href": site.login_url, "title": "login", "body": "", "ready": "complete",
            "user": True, "password": True, "submit": True, "bound": True,
            "action": site.login_url if site is fixed_login.GITLAB else "", "method": "post" if site is fixed_login.GITLAB else "",
        }
        self.after = after or {"href": site.origin + "/dashboard", "title": "", "body": "",
                               "ready": "complete", "protected": True, "identity": 2}
        self.snapshot_count = 0

    async def send_raw(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append((method, params, session_id))
        if method == "Page.navigate": return {"loaderId": "loader"}
        if method == "Page.getFrameTree": return {"frameTree": {"frame": {"loaderId": "loader"}}}
        if method == "Runtime.evaluate":
            if params.get("expression") == self.validate: return {"result": {"value": self.form}}
            if params.get("expression") == "document": return {"result": {"objectId": "doc"}}
            self.snapshot_count += 1
            if self.snapshot_count == 1:
                return {"result": {"value": {"href": self.form["href"], "title": "", "body": "",
                                               "ready": "complete", "protected": False, "identity": 1}}}
            return {"result": {"value": self.after}}
        if method == "Runtime.callFunctionOn": return {"result": {"value": True}}
        raise AssertionError(method)


def make_daemon(cdp):
    value = daemon.Daemon()
    value.cdp, value.target_id, value.session, value._session_generation = cdp, "target", "session", 1
    return value


async def execute(site, cdp):
    value = make_daemon(cdp)
    begun = await value.handle({"meta": "login_begin", "adapter": site.adapter}, owner="owner")
    result = await value.accept_login_secret(
        begun["transaction_id"], fixed_login.encode_payload(USER, PASSWORD), "owner")
    if result.get("status") == "success":
        assert await value.acknowledge_login_handoff(begun["transaction_id"], "owner") == {"status": "handoff_complete"}
    return result, value


@pytest.mark.parametrize("site", [fixed_login.GITLAB, fixed_login.PROXMOX])
def test_fixed_adapter_success_bound_session_and_no_secret_in_result(monkeypatch, site):
    monkeypatch.setattr(daemon, "NAME", "fixed-test")
    cdp = FakeCDP(site)
    result, _ = asyncio.run(execute(site, cdp))
    assert result == {"status": "success", "state": "active"}
    assert cdp.calls[0][1] == {"url": site.login_url}
    assert all(call[2] == "session" for call in cdp.calls)
    assert USER.decode() not in json.dumps(result) and PASSWORD.decode() not in json.dumps(result)
    assert USER.decode() not in " ".join(call[1].get("expression", "") for call in cdp.calls)


@pytest.mark.parametrize("site", [fixed_login.GITLAB, fixed_login.PROXMOX])
@pytest.mark.parametrize("fault", ["origin", "form", "mfa"])
def test_origin_form_and_mfa_fail_before_fill(monkeypatch, site, fault):
    monkeypatch.setattr(daemon, "NAME", "fixed-test")
    form = FakeCDP(site).form.copy()
    if fault == "origin": form["href"] = "https://evil.invalid/login"
    elif fault == "form": form["bound"] = False
    else: form["body"] = "MFA verification code"
    cdp = FakeCDP(site, form=form)
    result, _ = asyncio.run(execute(site, cdp))
    expected = "human_challenge" if fault == "mfa" else "failed"
    assert result == {"status": "failed", "state": expected}
    assert not any(method == "Runtime.callFunctionOn" for method, _params, _sid in cdp.calls)


def test_gitlab_requires_exact_post_action(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "fixed-test")
    form = FakeCDP(fixed_login.GITLAB).form.copy(); form["action"] = "https://evil.invalid/steal"
    result, _ = asyncio.run(execute(fixed_login.GITLAB, FakeCDP(fixed_login.GITLAB, form=form)))
    assert result == {"status": "failed", "state": "failed"}


def test_proxmox_success_requires_visible_login_overlay_absent_and_named_user_control():
    _validate, _fill, _submit, snapshot = fixed_login._expressions(fixed_login.PROXMOX)
    assert "Proxmox VE Login" in snapshot and "#userinfo" in snapshot
    assert "offsetWidth||e.offsetHeight||e.getClientRects().length" in snapshot
    assert "Logout" not in snapshot
    assert "treepanel-" not in snapshot and "content-" not in snapshot


def test_gitlab_contract_is_fixed_to_observed_single_step_local_form():
    validate, _fill, submit, snapshot = fixed_login._expressions(fixed_login.GITLAB)
    assert fixed_login.GITLAB.login_url == "https://gitlab.local-properties.org/users/sign_in"
    assert "#user_login" in validate and "#user_password" in validate
    assert "Sign in" in validate and "Sign in" in submit
    assert "csrf-token" in snapshot and "user-menu-toggle" in snapshot and "/-/profile" in snapshot


def test_event_sentinel_is_quarantined_and_concurrent_session_denied(monkeypatch):
    monkeypatch.setattr(daemon, "NAME", "fixed-test")
    class LeakingCDP(FakeCDP):
        async def send_raw(self, method, params=None, session_id=None):
            if method == "Runtime.callFunctionOn":
                self.daemon._record_event("Runtime.consoleAPICalled", {"value": PASSWORD.decode()}, session_id)
            return await super().send_raw(method, params, session_id)
    cdp = LeakingCDP(fixed_login.GITLAB); value = make_daemon(cdp); cdp.daemon = value
    async def case():
        begun = await value.handle({"meta": "login_begin", "adapter": fixed_login.GITLAB.adapter}, owner="owner")
        assert await value.handle({"meta": "login_begin", "adapter": fixed_login.PROXMOX.adapter}, owner="other") == {"error": "login_transaction_active"}
        result = await value.accept_login_secret(begun["transaction_id"], fixed_login.encode_payload(USER, PASSWORD), "owner")
        assert result == {"status": "success", "state": "active"}
        assert await value.acknowledge_login_handoff(begun["transaction_id"], "owner") == {"status": "handoff_complete"}
        return await value.handle({"meta": "drain_events"}, owner="owner")
    assert PASSWORD.decode() not in json.dumps(asyncio.run(case()))
