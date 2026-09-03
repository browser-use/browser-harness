from browser_harness import telemetry


def test_capture_cli_event_redacts_sensitive_task_output_and_steps(monkeypatch):
    """Regression test for #681.

    telemetry.py defines a real scrubber, _safe_properties(), that drops
    password/token/url/-named keys and truncates values. It is wired into
    capture() but NOT into capture_cli_event() -- the function that actually
    fires on every CLI invocation and builds its payload (task/output/steps/
    error_message) directly, unredacted. This must not leave the process.
    """
    monkeypatch.setattr(telemetry, "is_enabled", lambda: True)
    monkeypatch.setattr(telemetry, "_install_id", lambda *a, **k: "test-install-id")
    sent = {}
    monkeypatch.setattr(telemetry, "_send_detached", sent.update)

    telemetry.capture_cli_event(
        action="run",
        command="browser-harness",
        task="login(username='alice', password='hunter2')",
        output="Authorization: Bearer sk-live-abcdef123456",
        steps=[{"fn": "login", "args": {"password": "hunter2"}}],
        error_message="Traceback: /Users/alice/secret-project/script.py",
    )

    payload_text = str(sent)
    assert "hunter2" not in payload_text, "raw password leaked into telemetry payload"
    assert "sk-live-abcdef123456" not in payload_text, (
        "raw token leaked into telemetry payload"
    )
    assert "secret-project" not in payload_text, (
        "local path leaked into telemetry payload"
    )
