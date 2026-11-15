import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    assert calls[0][0] == (["osascript"],)
    assert "Allow remote debugging?" in calls[0][1]["input"]
    assert "AXPress" in calls[0][1]["input"]
    assert "AXHeading" in calls[0][1]["input"]
    assert "hasApprovalTitle" in calls[0][1]["input"]
    assert "activate" not in calls[0][1]["input"]


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


def test_mac_approve_guards_sheet_name_before_heading_fallback():
    matching = macos._APPLESCRIPT.split("set isTargetSheet to false", 1)[1]
    name_check, fallback = matching.split("if not isTargetSheet then", 1)

    assert name_check.strip().startswith("try")
    assert name_check.strip().endswith("end try")
    assert "name of s as text" in name_check
    assert fallback.strip().startswith("set isTargetSheet to my hasApprovalTitle(s)")


@pytest.mark.skipif(not shutil.which("osascript"), reason="requires macOS osascript")
@pytest.mark.parametrize(
    ("sheet_name", "heading_matches", "expected"),
    [
        ('"Allow remote debugging?"', "false", "true"),
        ('"Other sheet"', "true", "true"),
        ("missing value", "true", "true"),
        ("missing value", "false", "false"),
        ('"Other sheet"', "false", "false"),
    ],
)
def test_mac_approve_sheet_matching(sheet_name, heading_matches, expected):
    matching = macos._APPLESCRIPT.split("set isTargetSheet to false", 1)[1]
    matching = "set isTargetSheet to false" + matching.split("if isTargetSheet then", 1)[0]
    script = f'''on hasApprovalTitle(nodeRef)
    return {heading_matches}
end hasApprovalTitle
set s to {{name: {sheet_name}}}
{matching}
return isTargetSheet
'''

    result = subprocess.run(
        ["osascript"], input=script, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.skipif(not shutil.which("osacompile"), reason="requires macOS osacompile")
def test_mac_approve_applescript_syntax_valid(tmp_path):
    res = subprocess.run(
        ["osacompile", "-o", str(tmp_path / "approve.scpt")],
        input=macos._APPLESCRIPT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
