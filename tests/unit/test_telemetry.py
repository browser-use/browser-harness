from browser_harness import telemetry


def test_capture_cli_event_omits_user_content_but_keeps_usage_metadata(monkeypatch):
    monkeypatch.setattr(telemetry, "is_enabled", lambda: True)
    monkeypatch.setattr(telemetry, "_install_id", lambda *a, **k: "test-install-id")
    sent = {}
    monkeypatch.setattr(telemetry, "_send_detached", sent.update)

    task = "open the customer dashboard and summarize the latest run"
    telemetry.capture_cli_event(
        action="completed",
        command="browser-harness",
        task=task,
        browser="cdp",
        output="private page title and customer content",
        output_length=39,
        steps=[{"helper": "fill_input", "args": "private form value"}],
        step_count=1,
        duration_seconds=2.5,
        exit_code=0,
        error_message="private local traceback",
    )

    properties = sent["properties"]
    assert {"task", "output", "steps", "error_message"}.isdisjoint(properties)
    assert properties["task_length"] == len(task)
    assert properties["output_length"] == 39
    assert properties["step_count"] == 1
    assert properties["duration_seconds"] == 2.5
    assert properties["exit_code"] == 0
    assert properties["action"] == "completed"
    assert properties["command"] == "browser-harness"
    assert properties["browser"] == "cdp"
