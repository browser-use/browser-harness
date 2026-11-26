"""rotate_proxy() against a real Browser Use Cloud browser (bills a few minutes; skipped without auth).

The same live browser gets a new exit IP: same tabs, cookies kept, the page sees the new IP. rotate_proxy() runs with
the API key unavailable, so it must go over the browser's own CDP connection (BrowserUse.setProxy)."""
import json
import os

import pytest

from browser_harness import admin, auth, helpers

pytestmark = pytest.mark.skipif(
    auth.auth_status()["status"] != "authenticated", reason="needs Browser Use Cloud auth"
)


def _json_body(url):
    helpers.goto_url(url)
    helpers.wait_for_load()
    raw = helpers.js("document.body.innerText")
    return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])


def _no_key():
    raise AssertionError("rotate_proxy must not need the API key")


def test_rotate_proxy_keeps_the_browser_and_its_session(monkeypatch):
    monkeypatch.setenv("BH_OPEN_LIVE_URL", "0")
    name = f"rotate{os.getpid()}"
    monkeypatch.setattr(helpers, "NAME", name)
    browser = admin.start_remote_daemon(name, timeout=5)
    key = admin.auth.get_browser_use_api_key
    try:
        helpers.new_tab("https://httpbin.org/cookies/set?session=kept")
        helpers.wait_for_load()
        tabs = sorted(t["targetId"] for t in helpers.list_tabs())
        ip0 = _json_body("https://api.ipify.org?format=json")["ip"]

        admin.auth.get_browser_use_api_key = _no_key
        try:
            r = admin.rotate_proxy(name=name)
            print("rotate", {k: r.get(k) for k in ("mode", "country")})
            assert r["mode"] == "managed" and r["exitIp"]
            ip1 = _json_body("https://api.ipify.org?format=json")["ip"]
            assert ip1 == r["exitIp"] and ip1 != ip0

            r = admin.rotate_proxy("de", name=name)
            geo = _json_body("https://ipinfo.io/json")
            assert r["country"] == "de" and geo["country"] == "DE" and geo["ip"] == r["exitIp"]
        finally:
            admin.auth.get_browser_use_api_key = key

        assert _json_body("https://httpbin.org/cookies")["cookies"] == {"session": "kept"}
        assert sorted(t["targetId"] for t in helpers.list_tabs()) == tabs
        assert admin._browser_use(f"/browsers/{browser['id']}", "GET")["status"] == "active"
    finally:
        admin.stop_remote_daemon(name)
