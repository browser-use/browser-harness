---
name: safari-harness
description: Control existing Safari tabs on macOS using the local safari-harness Python CLI. Use for Safari navigation, page reading, DOM inspection, clicking, and form entry; it does not provide Chrome CDP or WebDriver isolation.
---

# Safari Harness

Use `safari-harness` with Python on stdin. Helpers are pre-imported:

```bash
safari-harness <<'PY'
tabs = list_tabs()
print(tabs)
# Select a known tab using its fresh dictionary, never assume the first is intended.
PY
```

`switch_tab(tab_dict)` selects a fresh `list_tabs()` result without activating it.
`new_tab(url)` opens a normal Safari window; this can move focus. It shares normal
Safari browsing context, subject to Safari profile and site settings.
`page_info()`, `current_tab()`, `goto_url(url)`, `get_page_content()`,
`js(expression)`, `click(css_selector)`, `fill(css_selector, text)`, and
`scroll(x=0, y=600)` act on the explicitly selected tab.
Selection lasts only within one CLI invocation. Select again in subsequent calls.

References include window, index, URL, and title. If a tab moves, navigates, or changes
title, the adapter rejects the old reference. Re-list and identify the intended tab
before selecting again. Identical tabs in the same window are rejected because
Safari's scripting API cannot distinguish them reliably. Concurrent rearrangement
can still race a command; avoid consequential unattended actions with this prototype.
Navigation is asynchronous. After navigation or an action that changes URL/title,
re-list tabs, verify the destination, and select the fresh result. Do not retry a
mutation merely because subsequent verification encountered a stale reference.

DOM clicks and input events are synthetic. Verify the resulting page state;
sites requiring trusted input may reject them. `js()` takes a synchronous expression;
wrap statements in an IIFE. Promises, raw CDP, screenshots, native file uploads,
network interception, browser dialogs, and cross-origin frame access are unsupported.
Do not claim these helpers provide those features. Use an appropriate supported tool
if the task requires them; preserve the user's choice of Safari.

Run `safari-harness doctor` to check the Apple Events connection; it does not prove
page JavaScript works. macOS may ask for Automation permission to control Safari.
JavaScript requires Safari > Develop > Allow JavaScript from Apple Events (location
may vary by Safari version). Report the permission requirement if blocked; do not
change security preferences through defaults or bypass the OS permission system.

No recordings are collected, and this adapter does not alter browser-harness's
recording preference. Do not install beta Safari or replace the default browser as
an implicit workaround.
