import importlib.util
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "tools" / "cdp-url-guard" / "check.py"
spec = importlib.util.spec_from_file_location("cdp_url_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
RULES = {name: pattern for name, pattern, _ in guard.RULES}


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ('return f"https://{parsed.netloc}/json/version"', True),
        ('return "%s://%s" % (parsed.scheme, parsed.netloc)', True),
        ('return "{}://{}".format(u.scheme, u.netloc)', True),
        ('log("%s://%s", scheme, host)', True),
        ('u = "wss://{}".format(cdp_host)', True),
        ('u = f"wss://{browser_host}/x"', True),
        ("u = 'ws://' + host + '/devtools'", True),
        ('u = "ws://" + u.netloc', True),
        ("const u = `wss://${cdpHost}/devtools`", True),
        ("const u = 'wss://' + browserHost", True),
        ('u = f"wss://{CDP_HOST}/x"', True),
        ("const u = 'wss://' + cdpHostName", True),
        ('u = "%(scheme)s://%(host)s/devtools" % parts', True),
        ('u = "wss://%(host)s" % {"host": h}', True),
        ('u = f"https://{GHOSTS}/x"', False),
        ('u = "https://ghost.example.com/" + y', False),
        ('return "https://example.com/%s" % path', False),
    ],
)
def test_host_read_rule_flags_each_format_style(line, flagged):
    assert bool(RULES["URL built from a host read"].search(line)) is flagged, line


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ('url = cdp_url + "/json/version"', True),
        ('cdp_url += "/json/version"', True),
        ('path = "/json/version"', False),
    ],
)
def test_json_path_rule_flags_each_join_style(line, flagged):
    assert bool(RULES["/json path joined to a URL"].search(line)) is flagged, line
