import importlib.util
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "tools" / "cdp-url-guard" / "check.py"
spec = importlib.util.spec_from_file_location("cdp_url_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
HOST_READ = dict((name, pattern) for name, pattern, _ in guard.RULES)["URL built from a host read"]


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ('return f"https://{parsed.netloc}/json/version"', True),
        ('return "%s://%s" % (parsed.scheme, parsed.netloc)', True),
        ('return "{}://{}".format(u.scheme, u.netloc)', True),
        ('log("%s://%s", scheme, host)', True),
        ('return "https://example.com/%s" % path', False),
    ],
)
def test_host_read_rule_flags_each_format_style(line, flagged):
    assert bool(HOST_READ.search(line)) is flagged, line
