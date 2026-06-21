from pathlib import Path
import pytest

from browser_harness import context, helpers


class _FakeConn:
    def close(self):
        pass


def test_send_uses_active_binding_runtime_dir(monkeypatch, tmp_path):
    calls = []
    binding = context.BrowserBinding(
        browser_id="br_test",
        bu_name="bh_test",
        runtime_dir=tmp_path / "r",
        tmp_dir=tmp_path / "t",
        manager_mode=True,
    )
    old = context.get_active_binding()
    context.activate_binding(binding)
    try:
        monkeypatch.setattr(
            helpers.ipc,
            "connect",
            lambda name, timeout=1.0, runtime_dir=None: calls.append((name, runtime_dir)) or (_FakeConn(), None),
        )
        monkeypatch.setattr(helpers.ipc, "request", lambda conn, token, req: {"ok": True})

        assert helpers._send({"meta": "ping"}) == {"ok": True}
    finally:
        if old is not None:
            context.activate_binding(old)
        else:
            context.clear_active_binding()

    assert calls == [("bh_test", tmp_path / "r")]


def test_capture_screenshot_defaults_to_binding_artifact_dir(monkeypatch, tmp_path, fake_png):
    binding = context.BrowserBinding(
        browser_id="br_test",
        bu_name="bh_test",
        runtime_dir=tmp_path / "r",
        tmp_dir=tmp_path / "t",
        artifact_dir=tmp_path / "artifacts",
        manager_mode=True,
    )
    old = context.get_active_binding()
    context.activate_binding(binding)
    try:
        monkeypatch.setattr(helpers, "cdp", lambda method, **kwargs: {"data": fake_png(20, 10)})
        path = helpers.capture_screenshot()
    finally:
        if old is not None:
            context.activate_binding(old)
        else:
            context.clear_active_binding()

    assert Path(path) == tmp_path / "artifacts" / "shot.png"
    assert Path(path).exists()


def test_agent_identity_uses_codex_thread_fallback(monkeypatch):
    monkeypatch.delenv("BH_RUN_ID", raising=False)
    monkeypatch.delenv("BH_AGENT_ID", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-123")
    monkeypatch.delenv("CODEX_AGENT_ID", raising=False)
    monkeypatch.delenv("CODEX_SUBAGENT_ID", raising=False)

    ident = context.agent_identity()

    assert ident.run_id == "thread-123"
    assert ident.agent_id == "main"
    assert ident.degraded is False


def test_require_active_binding_explains_browser_selector():
    old = context.get_active_binding()
    context.clear_active_binding()
    try:
        with pytest.raises(RuntimeError, match='call browser\\("<id>"\\)'):
            context.require_active_binding()
    finally:
        if old is not None:
            context.activate_binding(old)
        else:
            context.clear_active_binding()
