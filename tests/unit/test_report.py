import io
import json
import sys
from unittest.mock import patch

import pytest

from browser_harness import report, run, telemetry

REAL_SEND_DETACHED = telemetry._send_detached

SWITCHES = (
    "BH_TELEMETRY",
    "BROWSER_HARNESS_TELEMETRY",
    "ANONYMIZED_TELEMETRY",
    "BROWSER_USE_OFFLINE",
    "BROWSER_USE_ZDR",
    "BU_MODEL_CODE",
    "BU_NAME",
    "BROWSER_USE_TELEMETRY_INTERNAL",
)


@pytest.fixture(autouse=True)
def sent(monkeypatch, tmp_path):
    """Isolated config/runtime dirs, every switch unset, and the network sender replaced by a list."""
    for name in SWITCHES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("BH_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(report, "_process_sent", {})
    events = []
    monkeypatch.setattr(telemetry, "_send_detached", lambda payload, host=None: events.append((payload, host)))
    return events


def _only(sent):
    assert len(sent) == 1, sent
    return sent[0][0]


def test_report_run_sends_library_judgement_to_the_library_project(sent):
    assert report.report_run(False, "login wall", ["captcha after 3 searches"], bot_block=True) == report.SENT_RUN

    payload, host = sent[0]
    assert host == "https://eu.i.posthog.com"
    assert payload["api_key"] == report.LIBRARY_POSTHOG_KEY != telemetry.POSTHOG_KEY
    assert payload["event"] == "library_judgement"
    assert payload["distinct_id"] == telemetry._install_id()
    props = dict(payload["properties"])
    assert {props.pop(k) for k in ("$lib", "$lib_version", "$process_person_profile")} >= {"browser-harness", False}
    props.pop("version")
    assert props == {
        "surface": "harness-cli",
        "judge_source": "self",
        "run_id": None,
        "model": None,
        "success": False,
        "failure_reason": "login wall",
        "description": "",
        "prompt_injection_detected": False,
        "bot_block_or_captcha_detected": True,
        "gotchas": ["captcha after 3 searches"],
        "hosts": [],
        "cost_usd": None,
        "texts_withheld": False,
        "is_internal": False,
        "schema_version": 1,
    }


def test_texts_are_scrubbed_and_capped(sent, monkeypatch):
    monkeypatch.setenv("MY_SERVICE_TOKEN", "s3cr3t-value-123456")
    gotchas = [
        "mail jane.doe@example.com failed",
        "key sk-abcdefghijklmnop leaked, password=hunter22 too",
        "https://user:pw@shop.example.com:8443/reset-password/abc123def456ghi?sid=1#x redirected",
        "saved to /Users/jane/Downloads/a.pdf, card 4111 1111 1111 1111",
        "env said s3cr3t-value-123456",
        "sixth is dropped",
    ]
    report.report_run(True, "x" * 1000, gotchas, description="ok")

    props = _only(sent)["properties"]
    assert props["failure_reason"] == "x" * 300
    assert props["gotchas"] == [
        "mail <email> failed",
        "key <credential> leaked, password=<credential> too",
        "https://<credential>@shop.example.com/reset-password/<token> redirected",
        "saved to /Users/<user>/Downloads/a.pdf, card <number>",
        "env said <credential>",
    ]


def test_tunnel_and_preview_hosts_go_as_their_provider(sent):
    report.report_run(
        True,
        gotchas=[
            "https://Calm-Fox.trycloudflare.com:443/admin opened",
            "https://myproj-git-feature-acme.vercel.app/login is a preview",
            "https://Shop.Example.com/cart and https://myapp.vercel.app stay",
        ],
    )
    assert _only(sent)["properties"]["gotchas"] == [
        "https://*.trycloudflare.com/admin opened",
        "https://*.vercel.app/login is a preview",
        "https://shop.example.com/cart and https://myapp.vercel.app stay",
    ]


def test_internal_runs_are_marked(sent, monkeypatch):
    monkeypatch.setenv("BROWSER_USE_TELEMETRY_INTERNAL", "1")
    report.report_run(True)
    assert _only(sent)["properties"]["is_internal"] is True


def test_a_single_gotcha_string_is_one_gotcha(sent):
    report.report_run(True, gotchas="slow search box")
    assert _only(sent)["properties"]["gotchas"] == ["slow search box"]


def test_success_must_be_a_bool(sent):
    assert report.report_run("false").startswith("Error:")
    assert sent == []


@pytest.mark.parametrize(
    "env",
    [
        {"BH_TELEMETRY": "0"},
        {"BROWSER_HARNESS_TELEMETRY": "off"},
        {"ANONYMIZED_TELEMETRY": "false"},
        # browser-use reads these as off too: only 1, t... or y... keeps usage stats on
        {"ANONYMIZED_TELEMETRY": "False "},
        {"ANONYMIZED_TELEMETRY": "n"},
        {"ANONYMIZED_TELEMETRY": ""},
    ],
)
def test_model_reports_send_nothing_with_telemetry_off(sent, monkeypatch, env):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert report.report_run(True) == report.OFF
    assert report.report_issue("goto_url hangs") == report.OFF
    assert sent == []


def test_telemetry_disable_config_also_stops_model_reports(sent):
    telemetry.set_enabled(False)
    assert report.report_run(True) == report.OFF
    assert sent == []


@pytest.mark.parametrize("value", ["1", "true", "Yes", "y", "on"])
def test_offline_sends_nothing_at_all(sent, monkeypatch, value):
    monkeypatch.setenv("BROWSER_USE_OFFLINE", value)
    assert report.report_run(True) == report.OFFLINE
    assert report.report_issue("x") == report.OFFLINE
    with patch.object(sys, "stdin", io.StringIO("")):
        assert report.run_feedback_cli(["it broke"]) == 1
    assert sent == []


def test_zdr_withholds_texts_and_keeps_booleans(sent, monkeypatch):
    monkeypatch.setenv("BROWSER_USE_ZDR", "1")
    report.report_run(False, "secret reason", ["a gotcha"], bot_block=True, description="what happened")
    props = _only(sent)["properties"]
    assert (props["failure_reason"], props["description"], props["gotchas"]) == (None, "", [])
    assert props["texts_withheld"] is True
    assert props["success"] is False and props["bot_block_or_captcha_detected"] is True


def test_report_run_is_capped_per_daemon_name_per_hour(sent, monkeypatch):
    assert [report.report_run(True) for _ in range(4)][-1] == report.CAPPED
    assert len(sent) == 3
    report._process_sent.clear()  # the next CLI call is a new process: the file still holds the count
    assert report.report_run(True) == report.CAPPED
    monkeypatch.setenv("BU_NAME", "other")
    assert report.report_run(True) == report.SENT_RUN
    assert report.report_issue("separate cap") == report.SENT_ISSUE
    assert len(sent) == 5


def test_cap_window_expires(sent, monkeypatch):
    for _ in range(3):
        report.report_run(True)
    later = report.time.time() + report.WINDOW_S + 1
    monkeypatch.setattr(report.time, "time", lambda: later)
    report._process_sent.clear()
    assert report.report_run(True) == report.SENT_RUN


def test_report_issue_sends_library_feedback(sent):
    assert report.report_issue("fill_input ignores clear_first, see ~/x and bob@corp.com", "nope") == report.SENT_ISSUE
    props = dict(_only(sent)["properties"])
    for key in ("$lib", "$lib_version", "$process_person_profile", "version"):
        props.pop(key)
    assert props == {
        "source": "harness-cli",
        "message": "fill_input ignores clear_first, see ~/x and <email>",
        "category": "other",
        "is_internal": False,
        "model": None,
        "run_id": None,
        "step": None,
        "last_error_type": None,
    }


def test_user_cli_feedback_sends_with_telemetry_off_under_a_process_id(sent, monkeypatch, capsys):
    install_id = telemetry._install_id()
    monkeypatch.setenv("BH_TELEMETRY", "0")
    with patch.object(sys, "stdin", io.StringIO("")):
        assert report.run_feedback_cli(["docs", "are", "wrong", "--category", "docs"]) == 0
    payload = _only(sent)
    assert payload["distinct_id"] == report._PROCESS_ID != install_id
    assert payload["properties"]["message"] == "docs are wrong"
    assert payload["properties"]["category"] == "docs"
    assert "Thanks" in capsys.readouterr().out


def test_cli_feedback_from_model_code_sends_nothing(sent, monkeypatch):
    monkeypatch.setenv("BU_MODEL_CODE", "1")
    assert report.run_feedback_cli(["x"]) == 1
    assert sent == []


def test_cli_feedback_reads_stdin_and_rejects_empty(sent):
    with patch.object(sys, "stdin", io.StringIO("piped text")):
        assert report.run_feedback_cli([]) == 0
    with patch.object(sys, "stdin", io.StringIO("  ")):
        assert report.run_feedback_cli([]) == 2
    with patch.object(sys, "stdin", io.StringIO("")):
        assert report.run_feedback_cli(["x", "--category", "bogus"]) == 2
    assert len(sent) == 1


def test_browser_harness_feedback_subcommand(sent):
    with patch.object(sys, "argv", ["browser-harness", "feedback", "click_at_xy misses in iframes"]), \
         patch("browser_harness.run.telemetry.capture_cli_event") as cli_event, \
         pytest.raises(SystemExit) as exit_:
        run.main()
    assert exit_.value.code == 0
    assert _only(sent)["properties"]["source"] == "harness-cli"
    assert cli_event.call_args.kwargs["command"] == "feedback"


def test_report_helpers_are_not_traced_into_cli_event_steps(monkeypatch):
    monkeypatch.setitem(run.__dict__, "report_run", report.report_run)
    run._install_helper_trace()
    assert run.report_run is report.report_run
    assert getattr(run.page_info, "__bh_traced__", False)


def test_detached_sender_posts_to_the_library_host(monkeypatch):
    monkeypatch.setattr(telemetry, "_send_detached", REAL_SEND_DETACHED)  # Popen faked: no process, no network
    jobs = []

    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.stdin = io.BytesIO()
            self.stdin.close = lambda: jobs.append(json.loads(self.stdin.getvalue()))

    with patch.object(telemetry.subprocess, "Popen", FakePopen):
        report._send("library_feedback", {"message": "m"})
    assert jobs[0]["url"] == "https://eu.i.posthog.com/i/v0/e/"
    assert jobs[0]["payload"]["api_key"] == report.LIBRARY_POSTHOG_KEY
