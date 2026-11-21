from browser_harness import telemetry


def test_capture_cli_event_does_not_send_user_content(monkeypatch):
    sent = []
    monkeypatch.setattr(telemetry, "is_enabled", lambda: True)
    monkeypatch.setattr(telemetry, "_install_id", lambda: "install-id")
    monkeypatch.setattr(telemetry, "_send_detached", sent.append)

    telemetry.capture_cli_event(
        action="run",
        command="browser-harness",
        task="fill_input('#password', 'hunter2')",
        browser="cdp",
        output="scraped private page contents",
        output_length=31,
        steps=[{"helper": "fill_input", "args": "'hunter2'"}],
        step_count=1,
        duration_seconds=1.5,
        exit_code=0,
        error_message="token=secret-value",
    )

    properties = sent[0]["properties"]
    assert properties["task_length"] == len("fill_input('#password', 'hunter2')")
    assert properties["output_length"] == 31
    assert properties["step_count"] == 1
    assert properties["duration_seconds"] == 1.5
    assert properties["exit_code"] == 0
    assert "task" not in properties
    assert "output" not in properties
    assert "steps" not in properties
    assert "error_message" not in properties
