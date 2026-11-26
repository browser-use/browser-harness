"""The persistent browser config: which browser, which startup tab, tab marker."""
import asyncio
import json

import pytest

from browser_harness import admin, daemon
from browser_harness import config as browser_config


class _FakeBrowser:
    """The fake browser the daemon tests use, with one page the person owns."""

    def __init__(self, *pages):
        self.calls = []
        self.pages = dict(pages) or {"person-tab": "https://mail.example/"}
        self.n = 0

    def info(self, tid):
        return {"targetId": tid, "type": "page", "url": self.pages[tid], "title": tid}

    async def send_raw(self, method, params=None, session_id=None):
        params = params or {}
        self.calls.append((method, params, session_id))
        if method == "Target.createTarget":
            self.n += 1
            tid = f"tab-{self.n}"
            self.pages[tid] = params["url"]
            return {"targetId": tid}
        if method == "Target.attachToTarget":
            self.n += 1
            return {"sessionId": f"s{self.n}"}
        return {}


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BH_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_missing_config_reads_as_defaults(config_dir):
    settings = browser_config.browser_settings()

    assert settings == {"preferred_browser": None, "startup_tab": "new", "tab_marker": None}


def test_damaged_config_never_breaks_the_daemon(config_dir):
    (config_dir / "config.json").write_text("{not json")

    assert browser_config.browser_settings()["startup_tab"] == "new"


def test_write_merges_and_keeps_other_sections(config_dir):
    (config_dir / "config.json").write_text(json.dumps({"other": {"keep": 1}}))

    browser_config.write({"preferred_browser": "brave"})

    data = json.loads((config_dir / "config.json").read_text())
    assert data["browser"]["preferred_browser"] == "brave"
    assert data["other"] == {"keep": 1}


def test_clear_removes_a_key(config_dir):
    browser_config.write({"preferred_browser": "brave", "startup_tab": "first_page"})
    browser_config.write({"preferred_browser": None})

    settings = browser_config.browser_settings()
    assert settings["preferred_browser"] is None
    assert settings["startup_tab"] == "first_page"


def test_invalid_values_are_ignored_not_fatal(config_dir):
    (config_dir / "config.json").write_text(
        json.dumps({"browser": {"startup_tab": "whatever", "tab_marker": "yes", "preferred_browser": 7}})
    )

    settings = browser_config.browser_settings()

    assert settings["startup_tab"] == "new"
    assert settings["tab_marker"] is None
    assert settings["preferred_browser"] is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("preferred_browser=brave", ("preferred_browser", "brave")),
        ("tab_marker=false", ("tab_marker", False)),
        ("tab_marker=true", ("tab_marker", True)),
        ("startup_tab=first_page", ("startup_tab", "first_page")),
        ("startup_tab=new", ("startup_tab", "new")),
    ],
)
def test_parse_assignment_types_values(text, expected):
    assert browser_config.parse_assignment(text) == expected


def test_parse_assignment_rejects_an_unknown_startup_tab():
    with pytest.raises(ValueError, match="startup_tab"):
        browser_config.parse_assignment("startup_tab=whatever")


def test_config_cli_set_and_show(config_dir, capsys):
    assert browser_config.run_config_cli(["set", "preferred_browser=brave"]) == 0
    assert browser_config.run_config_cli(["show"]) == 0

    out = capsys.readouterr().out
    assert "preferred_browser  brave" in out


def test_config_cli_rejects_an_unknown_key(config_dir, capsys):
    assert browser_config.run_config_cli(["set", "nonsense=1"]) == 2
    assert "unknown key" in capsys.readouterr().err


def test_browser_key_names_the_browsers_the_harness_knows():
    keys = daemon.known_browser_keys()

    for expected in ("chrome", "brave", "edge", "chromium", "brave-origin"):
        assert expected in keys


@pytest.mark.parametrize(
    ("tail", "key"),
    [
        ("Google/Chrome", "chrome"),
        ("Google/Chrome Canary", "chrome-canary"),
        ("BraveSoftware/Brave-Browser", "brave"),
        ("BraveSoftware/Brave-Origin", "brave-origin"),
        ("Microsoft Edge", "edge"),
        ("Google/Chrome SxS", "chrome-canary"),
    ],
)
def test_browser_key_for_profile_reads_the_profile_dir_tail(tail, key):
    from pathlib import Path

    assert daemon.browser_key_for_profile(Path("/home/u") / tail) == key


def test_preferred_profile_resolves_a_browser_name(monkeypatch, tmp_path):
    brave = tmp_path / "BraveSoftware/Brave-Browser"
    brave.mkdir(parents=True)
    chrome = tmp_path / "Google/Chrome"
    chrome.mkdir(parents=True)
    monkeypatch.setattr(daemon, "PROFILES", [chrome, brave])

    assert daemon.preferred_profile("brave") == brave


def test_preferred_profile_of_an_unknown_browser_is_none(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "PROFILES", [tmp_path])

    assert daemon.preferred_profile("nonexistent-browser") is None


def test_preferred_profile_accepts_a_path(monkeypatch, tmp_path):
    profile = tmp_path / "some-profile"
    profile.mkdir()

    assert daemon.preferred_profile(str(profile)) == profile


def test_a_preferred_browser_never_falls_through_to_another_one(monkeypatch, tmp_path, config_dir):
    """A config that names a browser this machine does not have is an error, not a
    silent attach to whatever else is running."""
    brave = tmp_path / "BraveSoftware/Brave-Browser"
    brave.mkdir(parents=True)
    (brave / "DevToolsActivePort").write_text("9222\n/devtools/browser/brave\n")
    monkeypatch.setattr(daemon, "PROFILES", [brave])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    browser_config.write({"preferred_browser": "chrome"})

    with pytest.raises(RuntimeError, match="preferred-browser-not-found"):
        daemon.get_ws_url()


def test_a_preferred_browser_is_the_only_one_considered(monkeypatch, tmp_path, config_dir):
    brave = tmp_path / "BraveSoftware/Brave-Browser"
    brave.mkdir(parents=True)
    (brave / "DevToolsActivePort").write_text("9333\n/devtools/browser/brave\n")
    monkeypatch.setattr(daemon, "PROFILES", [brave])
    monkeypatch.delenv("BU_CDP_WS", raising=False)
    monkeypatch.delenv("BU_CDP_URL", raising=False)
    browser_config.write({"preferred_browser": "brave"})

    def urlopen(url, **kwargs):
        assert url == "http://127.0.0.1:9333/json/version"
        return type("Response", (), {"read": lambda self: b'{"webSocketDebuggerUrl": "ws://127.0.0.1:9333/devtools/browser/brave"}'})()

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)

    assert daemon.get_ws_url() == "ws://127.0.0.1:9333/devtools/browser/brave"


def test_the_environment_still_wins_over_the_config(monkeypatch, tmp_path, config_dir):
    monkeypatch.setenv("BU_CDP_WS", "ws://127.0.0.1:1/devtools/browser/env")
    browser_config.write({"preferred_browser": "brave"})

    assert daemon.get_ws_url() == "ws://127.0.0.1:1/devtools/browser/env"


def test_tab_marker_config_disables_the_marker(monkeypatch, config_dir):
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    browser_config.write({"tab_marker": False})

    assert daemon.tab_marker_enabled() is False


def test_the_environment_wins_over_the_tab_marker_config(monkeypatch, config_dir):
    monkeypatch.setenv("BH_TAB_MARKER", "1")
    browser_config.write({"tab_marker": False})

    assert daemon.tab_marker_enabled() is True


def test_startup_tab_new_never_adopts_the_persons_tab(monkeypatch, config_dir):
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    browser_config.write({"startup_tab": "new"})
    d = daemon.Daemon()
    d.cdp = _FakeBrowser()
    d.info = {"person-tab": d.cdp.info("person-tab")}

    tid = asyncio.run(d._current("a", d.owner("a")))

    assert tid == "tab-1"
    assert [p for m, p, _s in d.cdp.calls if m == "Target.createTarget"] == [
        {"url": "about:blank", "background": True}
    ]


def test_startup_tab_first_page_adopts_the_first_real_page(monkeypatch, config_dir):
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    browser_config.write({"startup_tab": "first_page"})
    d = daemon.Daemon()
    d.cdp = _FakeBrowser()
    d.info = {"person-tab": d.cdp.info("person-tab")}

    tid = asyncio.run(d._current("a", d.owner("a")))

    assert tid == "person-tab"
    assert [m for m, _p, _s in d.cdp.calls if m == "Target.createTarget"] == []


def test_startup_tab_first_page_never_takes_a_tab_another_owner_holds(monkeypatch, config_dir):
    monkeypatch.delenv("BH_TAB_MARKER", raising=False)
    browser_config.write({"startup_tab": "first_page"})
    d = daemon.Daemon()
    d.cdp = _FakeBrowser()
    d.info = {"person-tab": d.cdp.info("person-tab")}
    d.owner("someone-else")
    d.tab_owner["person-tab"] = "someone-else"

    tid = asyncio.run(d._current("a", d.owner("a")))

    assert tid == "tab-1"


def test_doctor_reports_the_resolved_browser_config(monkeypatch, config_dir, capsys):
    browser_config.write({"preferred_browser": "brave", "startup_tab": "first_page"})
    monkeypatch.setattr(admin, "_chrome_running", lambda: True)
    monkeypatch.setattr(admin, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(admin, "browser_connections", list)
    monkeypatch.setattr(admin, "_version", lambda: "0.0.0")
    monkeypatch.setattr(admin, "_install_mode", lambda: "pip")
    monkeypatch.setattr(admin, "_latest_release_tag", lambda: None)
    monkeypatch.setattr(admin, "auth", type("A", (), {"auth_status": staticmethod(lambda: {"status": "none", "source": None})}))

    admin.run_doctor()

    out = capsys.readouterr().out
    assert "startup tab        first_page" in out
    assert "preferred browser  brave" in out
