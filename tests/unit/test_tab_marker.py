import json
import os
import shutil
import subprocess

import pytest

from browser_harness import _tab_marker

# Any JS runtime works; node is the common one, bun is accepted too.
JS_RUNTIME = shutil.which("node") or shutil.which("bun")
requires_js = pytest.mark.skipif(JS_RUNTIME is None, reason="node or bun is required to execute marker JavaScript")

_SCRIPT = """
globalThis.document = {title: process.env.TITLE};
const results = [];
for (let i = 0; i < Number(process.env.APPLICATIONS); i++) {
  eval(process.env.EXPRESSION);
  results.push(document.title);
}
console.log(JSON.stringify(results));
"""


def _evaluate(expression, title, applications=1):
    env = {**os.environ, "APPLICATIONS": str(applications), "EXPRESSION": expression, "TITLE": title}
    result = subprocess.run([JS_RUNTIME, "-e", _SCRIPT], env=env, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_default_daemon_keeps_bare_horse():
    assert _tab_marker.marker("default") == "🐴"


def test_named_daemon_marker_is_a_prefix_tag():
    assert _tab_marker.marker("research-7f3a") == "🐴 [research-7f3a]"


@requires_js
@pytest.mark.parametrize(
    ("name", "title", "expected"),
    [
        ("research-7f3a", "Example Domain", "🐴 [research-7f3a] Example Domain"),
        ("research-7f3a", "", "🐴 [research-7f3a] "),
        ("research-7f3a", "🐴 [research-7f3a] Example", "🐴 [research-7f3a] Example"),
        ("research-7f3a", "🐴 [other] Example", "🐴 [research-7f3a] Example"),
        ("research-7f3a", "🐴 Example", "🐴 [research-7f3a] Example"),
        ("default", "Example Domain", "🐴 Example Domain"),
        ("default", "🐴 Example", "🐴 Example"),
        ("default", "🐴 [other] Example", "🐴 Example"),
    ],
)
def test_marker_expression_is_prefix_and_idempotent(name, title, expected):
    assert _evaluate(_tab_marker.expression(name), title, applications=2) == [expected, expected]


@requires_js
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("🐴 [research-7f3a] Example", "Example"),
        ("🐴 Example", "Example"),
        ("🐴 [research-7f3a] ", ""),
        ("Example 🐴 [x]", "Example 🐴 [x]"),
    ],
)
def test_unmark_expression_removes_any_harness_prefix(title, expected):
    assert _evaluate(_tab_marker.unmark_expression(), title) == [expected]
