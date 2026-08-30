import json
import os
import subprocess

import pytest

from browser_harness import _tab_marker


def _evaluate(expression, title, applications=1):
    script = '''
globalThis.document = {title: process.env.TITLE};
const results = [];
for (let index = 0; index < Number(process.env.APPLICATIONS); index++) {
  eval(process.env.EXPRESSION);
  results.push(document.title);
}
console.log(JSON.stringify(results));
'''
    environment = {
        **os.environ,
        "APPLICATIONS": str(applications),
        "EXPRESSION": expression,
        "TITLE": title,
    }
    result = subprocess.run(
        ["bun", "-e", script],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_marker_uses_exact_daemon_name():
    assert _tab_marker.marker("research-7f3a") == "🐴 [research-7f3a]"
    assert _tab_marker.marker_suffix("research-7f3a") == " | 🐴 [research-7f3a]"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Example Domain", "Example Domain | 🐴 [research-7f3a]"),
        ("", " | 🐴 [research-7f3a]"),
        (" | 🐴 [research-7f3a]", " | 🐴 [research-7f3a]"),
        ("Example | 🐴 [other]", "Example | 🐴 [research-7f3a]"),
    ],
)
def test_marker_expression_is_suffix_idempotent(title, expected):
    assert _evaluate(_tab_marker.expression("research-7f3a"), title, applications=2) == [
        expected,
        expected,
    ]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Example | 🐴 [research-7f3a]", "Example"),
        ("🐴 Legacy", "Legacy"),
        ("🐴 [research-7f3a]", ""),
    ],
)
def test_unmarker_expression_removes_suffix_and_legacy_prefix(title, expected):
    assert _evaluate(_tab_marker.unmarker_expression(), title) == [expected]
