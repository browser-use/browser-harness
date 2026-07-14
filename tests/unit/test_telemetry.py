from browser_harness import telemetry


def test_cli_telemetry_contains_only_operational_metrics(monkeypatch):
    sent = []
    sentinel = "secret-token@example.test"
    monkeypatch.setenv("BH_CLIENT", sentinel)
    monkeypatch.setenv("BH_CLIENT_VERSION", sentinel)
    monkeypatch.setenv("BROWSER_USE_AGENT_MODEL", sentinel)
    monkeypatch.setenv("BROWSER_USE_MODEL_PROVIDER", sentinel)
    monkeypatch.setattr(telemetry, "is_enabled", lambda: True)
    monkeypatch.setattr(telemetry, "_install_id", lambda: "test-install-id")
    monkeypatch.setattr(telemetry, "_send_detached", sent.append)

    telemetry.capture_cli_event(
        action="completed",
        command="script",
        browser="local",
        task_length=42,
        output_length=17,
        step_count=3,
        duration_seconds=1.5,
        exit_code=0,
    )

    properties = sent[0]["properties"]
    assert properties["task_length"] == 42
    assert properties["output_length"] == 17
    assert properties["step_count"] == 3
    assert {"client", "client_version", "error_message", "model", "model_provider", "output", "steps", "task"}.isdisjoint(properties)
    assert sentinel not in properties.values()
