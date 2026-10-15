# Experimental Safari adapter

`safari-harness` controls normal Safari tabs through macOS Apple Events, including
existing sessions. It is a separate Python package with familiar helper names.
Safari does not implement Chrome CDP; the existing `browser-harness` runtime and
skill are unchanged.

## Install

Requires macOS, Safari, Python 3.12, and uv. From the repository root:

```sh
uv tool install --python 3.12 --editable ./adapters/safari
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/safari-harness"
safari-harness skill > "${CODEX_HOME:-$HOME/.codex}/skills/safari-harness/SKILL.md"
safari-harness doctor
```

macOS may request Automation permission to control Safari. Page JavaScript requires
**Allow JavaScript from Apple Events** in Safari's developer settings. The adapter
reports permission failures and does not change either setting. `doctor` checks
the Apple Events connection only; it does not verify page JavaScript.

## Use

```sh
safari-harness <<'PY'
tabs = list_tabs()
matches = [t for t in tabs if t['url'] == 'https://example.com/']
if len(matches) != 1:
    raise RuntimeError('Expected one uniquely matching tab')
switch_tab(matches[0])
print(page_info())
print(get_page_content())
PY
```

Helpers: `list_tabs`, `switch_tab`, `current_tab`, `page_info`, `new_tab`,
`goto_url`, `js`, `get_page_content`, `click`, `fill`, and `scroll`.
Selection lasts for one CLI invocation. `new_tab(url)` opens a normal window and
may change focus. Failed `switch_tab()` or `new_tab()` calls clear the selection,
including invalid arguments; explicitly select again before another page action.

## Limits

- References contain window ID, tab index, URL, and title. Changed references and
  identical tabs within one window are rejected. Re-list and select after navigation
  or title changes. Safari does not expose a stable tab/document ID through this API.
- Page JS checks the exact URL immediately before evaluating the requested
  expression. This does not distinguish replacement documents with the same URL,
  opaque origins sharing a URL, or protect native navigation from concurrent changes.
  Consequential unattended writes remain outside the verified scope.
- Navigation is asynchronous. Clicks and input events are synthetic; verify the
  resulting page state. Sites requiring trusted input may reject these events.
- No CDP, screenshots, recordings, native file uploads, network interception,
  cross-origin frame traversal, Promise results, or native dialog control.

## Development and verification

From `adapters/safari`, run the deterministic checks without a browser:

```sh
uv run --python 3.12 python -m unittest discover -s tests -v
node --test tests/bridge.test.cjs
```

The opt-in live fixture requires macOS and Safari permissions. It serves a
synthetic page on loopback, opens one window, and leaves it open. The server stops
when the check exits. Optimized Python execution is rejected so assertions cannot
silently disappear.

```sh
uv run --python 3.12 python scripts/smoke_safari.py
```

See [verification.md](verification.md) for the observed results and open gaps.
No recordings, telemetry, cookies, or personal page-content logs are collected.
