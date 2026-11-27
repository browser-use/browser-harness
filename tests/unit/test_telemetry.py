import json
import subprocess
from unittest.mock import MagicMock

import pytest

from browser_harness import telemetry

REAL_POST_DETACHED = telemetry.post_detached  # conftest swaps it for a no-op; here Popen is faked instead


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path))
    for name in telemetry.DISABLE_ENVS:
        monkeypatch.delenv(name, raising=False)
    popen = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: popen.append(a) or MagicMock())
    monkeypatch.setattr(telemetry, "post_detached", REAL_POST_DETACHED)
    yield popen
    telemetry.set_sink()


def test_sink_receives_cli_event_under_its_install_id_instead_of_posthog(_isolated):
    sent = []
    telemetry.set_sink(sent.append, install_id=lambda create: "dev-1" if create else None)
    telemetry.capture_cli_event(action="run", command="exec", exit_code=0)
    assert len(sent) == 1
    assert sent[0]["event"] == "cli_event"
    assert sent[0]["distinct_id"] == "dev-1"
    assert sent[0]["properties"]["command"] == "exec"
    assert not telemetry._config_path().exists()  # no harness install id was created
    assert _isolated == []  # the detached PostHog sender never ran


def test_sink_enabled_gate_is_anded_with_harness_opt_outs(monkeypatch):
    sent = []
    telemetry.set_sink(sent.append, enabled=lambda: False)
    assert telemetry.is_enabled() is False
    telemetry.capture("x")
    assert sent == []

    telemetry.set_sink(sent.append, enabled=lambda: True)
    monkeypatch.setenv("BH_TELEMETRY", "0")
    assert telemetry.is_enabled() is False  # the harness opt-out still wins
    monkeypatch.delenv("BH_TELEMETRY")
    telemetry.capture("x")
    assert [p["event"] for p in sent] == ["x"]


def test_sink_status_post_processes_status_and_telemetry_cli(capsys):
    telemetry.set_sink(install_id=lambda create: "dev-1", status=lambda out: {**out, "enabled": False, "by": "sink"})
    out = telemetry.status()
    assert out["enabled"] is False and out["by"] == "sink" and out["install_id"] == "dev-1"
    assert telemetry.run_telemetry_cli(["disable"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["disabled_by_config"] is True and printed["by"] == "sink"


def test_set_sink_without_arguments_restores_the_default_sender(_isolated):
    telemetry.set_sink(lambda payload: None)
    telemetry.set_sink()
    telemetry.capture("x")
    assert len(_isolated) == 1  # the detached PostHog sender ran again


CDP_URLS = [
    ("ws://127.0.0.1:49321/devtools/browser/abc", "local"),
    ("http://localhost:49321", "local"),
    ("http://[::1]:49321", "local"),
    ("127.0.0.2:49321", "local"),
    ("http://0.0.0.0:49321", "local"),
    ("wss://0123abcd-session.cdp.browser-use.com/devtools/browser/uuid", "cloud"),
    ("wss://chrome-box.corp-internal.example:49321/devtools/browser/abc", "remote"),
    ("http://10.20.30.40:49321", "remote"),
    ("my-box.tailnet-x.ts.net:49321", "remote"),
]


@pytest.mark.parametrize("env", ["BU_CDP_WS", "BU_CDP_URL"])
@pytest.mark.parametrize("url,kind", CDP_URLS)
def test_cli_event_sends_the_cdp_kind_never_its_host_ip_or_port(monkeypatch, env, url, kind):
    jobs = []

    class FakePopen:  # the detached sender's stdin is the request it would POST: nothing is spawned or sent
        def __init__(self, *args, **kwargs):
            self.stdin = MagicMock()
            self.stdin.write = lambda data: jobs.append(json.loads(data))

    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    monkeypatch.setenv(env, url)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    telemetry.capture_cli_event(action="run", command="exec", browser="cdp", exit_code=0)
    props = jobs[0]["payload"]["properties"]
    assert props["cdp_kind"] == kind and "cdp_url" not in props
    sent = json.dumps(jobs[0]["payload"])
    for part in ("127.0.0", "0.0.0.0", "localhost", "::1", "0123abcd", "browser-use.com", "chrome-box", "corp-internal",
                 "10.20.30.40", "tailnet-x", "49321"):
        assert part not in sent


def test_cli_event_has_no_cdp_kind_without_a_cdp_endpoint(monkeypatch):
    sent = []
    telemetry.set_sink(sent.append)
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    telemetry.capture_cli_event(action="run", command="exec", browser="local", exit_code=0)
    assert sent[0]["properties"]["cdp_kind"] is None
