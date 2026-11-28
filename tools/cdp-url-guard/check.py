#!/usr/bin/env python3
"""Fail when code outside the CDP URL helper joins text to make a CDP URL."""
import re, subprocess, sys

HELPERS = {"src/browser_harness/cdp_urls.py", "tools/cdp-url-guard/check.py"}
ALLOWED = [
    # The daemon uses this label only in logs.
    ("src/browser_harness/daemon.py", 'return f"{parsed.scheme}://{host}{port}"'),
    # The daemon uses this key only to match endpoints for ping.
    ("src/browser_harness/daemon.py", 'bare = f"{scheme}://{host}:{u.port or {\'ws\': 80, \'wss\': 443}.get(scheme, \'\')}"'),
]
CODE = re.compile(r"\.(py|js|mjs|cjs|ts|sh|html)$")
TEST = re.compile(r"((^|/)test_[^/]*\.py|_test\.py|\.test\.\w+|\.spec\.\w+)$|(^|/)(tests?|__tests__|testdata|fixtures)/")
RULES = [
    ("our CDP domain", re.compile(r"\.cdp\.(browser-use|eu\.browser-use|fuego)"), False),
    ("driver port joined to a URL", re.compile(r":6969\b|USE_BROWSER_API_PORT(?!\s*(:\s*)?(\w+\s*)?:?=[^=])"), False),
    ("/json path joined to a URL", re.compile(r"""(\+\s*["'`]|\}|%s|%v)/json/(version|list)|(new URL\(\s*["'`]|urljoin\(.*["'])/?json/(version|list)"""), False),
    ("URL built from a host read", re.compile(r"""//[^"'`\n]*(\{[^}]*|(%s|\{\})[^"'`\n]*["'`]\s*(,|%|\.format\()[^\n]*)\b(Host|host|hostname|Hostname|netloc|origin)\b"""), True),
]


def main() -> int:
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split("\n")
    failures = []
    for path in files:
        if not CODE.search(path) or TEST.search(path) or path in HELPERS:
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        mentions_cdp = "cdp" in text.lower()
        for number, line in enumerate(text.split("\n"), 1):
            for name, pattern, needs_cdp in RULES:
                if needs_cdp and not mentions_cdp or not pattern.search(line):
                    continue
                if (path, line.strip()) in ALLOWED:
                    continue
                failures.append(f"{path}:{number}: {name}: {line.strip()[:160]}")
    for failure in failures:
        print(failure)
    if failures:
        print("\nBuild CDP URLs with cdp_path() from src/browser_harness/cdp_urls.py, so the ?token= query stays.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
