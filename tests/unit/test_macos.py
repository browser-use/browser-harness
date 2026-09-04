from pathlib import Path
from types import SimpleNamespace

from browser_harness import macos


def _enable_chrome_toggle(monkeypatch):
    chrome_root = Path("/tmp/Google Chrome")
    monkeypatch.setattr(macos, "_google_chrome_root", lambda: chrome_root)
    monkeypatch.setattr(
        macos,
        "remote_debugging_toggle_profiles",
        lambda: [chrome_root],
    )


def _no_ready_daemon(monkeypatch):
    monkeypatch.setattr(macos, "daemon_browser_ready", lambda: False)


def test_mac_approve_requires_the_persistent_chrome_checkbox(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    monkeypatch.setattr(macos, "_google_chrome_root", lambda: Path("/tmp/Google Chrome"))
    monkeypatch.setattr(macos, "remote_debugging_toggle_profiles", lambda: [Path("/tmp/Edge")])

    status, detail = macos.approve_remote_debugging()

    assert status == "setup-required"
    assert "chrome://inspect/#remote-debugging" in detail


def test_mac_approve_runs_osascript_only_after_checkbox_is_enabled(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    calls = []
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or SimpleNamespace(returncode=0, stdout="ready\n", stderr=""),
    )

    status, detail = macos.approve_remote_debugging()

    assert (status, detail) == ("ready", None)
    argv = calls[0][0][0]
    assert argv[:2] == ["osascript", "-"]
    assert "AXPress" in calls[0][1]["input"]
    assert "activate" not in calls[0][1]["input"]


def _argv_tables(argv):
    title_count = int(argv[2])
    return argv[3 : 3 + title_count], argv[3 + title_count :]


def test_mac_approve_passes_chromes_localized_sheet_strings(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    monkeypatch.delenv("BH_ALLOW_SHEET_TITLES", raising=False)
    monkeypatch.delenv("BH_ALLOW_LABELS", raising=False)
    calls = []
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or SimpleNamespace(returncode=0, stdout="ready\n", stderr=""),
    )

    macos.approve_remote_debugging()

    titles, labels = _argv_tables(calls[0][0][0])
    assert "Allow remote debugging?" in titles
    assert "リモート デバッグを許可しますか？" in titles
    assert "Allow" in labels
    assert "許可する" in labels
    assert "Cancel" not in labels
    assert "Turn off in settings" not in labels
    # The literals no longer live in the script; the script reads argv.
    assert "Allow remote debugging?" not in calls[0][1]["input"]
    assert "on run argv" in calls[0][1]["input"]


def test_mac_approve_extends_tables_from_env(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    monkeypatch.setenv("BH_ALLOW_SHEET_TITLES", "Fernwartung erlauben? , Ander titel")
    monkeypatch.setenv("BH_ALLOW_LABELS", "Ja,Oui")
    calls = []
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or SimpleNamespace(returncode=0, stdout="ready\n", stderr=""),
    )

    macos.approve_remote_debugging()

    titles, labels = _argv_tables(calls[0][0][0])
    assert titles[-2:] == ["Fernwartung erlauben?", "Ander titel"]
    assert "Allow remote debugging?" in titles
    assert labels[-2:] == ["Ja", "Oui"]
    assert "Allow" in labels


def test_mac_approve_maps_localized_accessibility_error_code_to_guidance(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    japanese_denial = (
        "System Events でエラーが起きました: osascript には補助アクセスが許可されていません。(-25211)"
    )
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=japanese_denial),
    )

    status, detail = macos.approve_remote_debugging()

    assert status == "accessibility-required"
    assert "Accessibility" in detail


def test_mac_approve_returns_not_found_without_a_prompt(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="not-found\n", stderr=""),
    )

    status, detail = macos.approve_remote_debugging()

    assert status == "not-found"
    assert "retry the browser command" in detail


def test_mac_approve_returns_ready_without_running_osascript(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(macos, "daemon_browser_ready", lambda: True)
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert macos.approve_remote_debugging() == ("ready", None)


def test_mac_approve_detects_user_accepting_while_it_checks(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _enable_chrome_toggle(monkeypatch)
    readiness = iter([False, True])
    monkeypatch.setattr(macos, "daemon_browser_ready", lambda: next(readiness))
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="not-found\n", stderr=""),
    )

    assert macos.approve_remote_debugging() == ("ready", None)


def test_mac_approve_cli_treats_ready_as_success(monkeypatch, capsys):
    monkeypatch.setattr(macos, "approve_remote_debugging", lambda: ("ready", None))

    assert macos.run_cli([]) == 0
    assert capsys.readouterr().out == "ready\n"


def test_mac_approve_maps_pending_accessibility_consent_to_guidance(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Darwin")
    _no_ready_daemon(monkeypatch)
    _enable_chrome_toggle(monkeypatch)
    monkeypatch.setattr(
        macos.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            macos.subprocess.TimeoutExpired(["osascript"], 5)
        ),
    )

    status, detail = macos.approve_remote_debugging()

    assert status == "accessibility-required"
    assert "Accessibility" in detail


def test_mac_approve_is_unavailable_off_macos(monkeypatch):
    monkeypatch.setattr(macos.platform, "system", lambda: "Linux")

    assert macos.approve_remote_debugging() == (
        "unsupported",
        "mac-approve is only available on macOS",
    )
