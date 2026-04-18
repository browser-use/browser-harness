---
name: bu
description: Direct browser control via CDP. Use when the user wants to automate, scrape, test, or interact with web pages. Connects to the user's already-running Chrome.
allowed-tools: Bash, Read, Edit, Write
---

# bu

Project: `/Users/greg/Documents/browser-use/hackathons/bu/`

**Read `helpers.py` first.** ~260 lines, one tool call. The code is the doc.

## Tool call shape

```bash
cd /Users/greg/Documents/browser-use/hackathons/bu && uv run run.py <<'PY'
# any python. helpers pre-imported. daemon auto-starts.
PY
```

`run.py` calls `ensure_daemon()` before `exec` — you never start/stop manually unless you want to.

## Setup

`uv sync`. Enable `chrome://inspect/#remote-debugging`. Remote browsers: `cp .env.example .env` + fill `BROWSER_USE_API_KEY`.

**First local daemon start may hang** on Chrome's "Allow debugging" dialog. Give ~15s, then retry.

## Parallel / remote

`BU_NAME` picks the daemon (default `default`). Each name = independent socket `/tmp/bu-<NAME>.sock`, independent daemon. Remote:

```bash
uv run python -c "from helpers import start_remote_daemon; print(start_remote_daemon('work'))"
BU_NAME=work uv run run.py <<'PY' ... PY
uv run python -c "from helpers import kill_daemon; kill_daemon('work')"  # stops cloud browser too
```

Leaving a remote daemon running bills until the session timeout.

## Post-task ritual (self-improving harness)

After every browser task, extract ONE generalizable friction point from the interaction (a failed selector strategy, a slow pattern, a missing helper, a confusing result) and make the **simplest possible** improvement:
- a 2-line helper in `helpers.py`, OR
- a one-line gotcha in `AGENTS.md`, OR
- a correction to a wrong recipe here.

Commit with the task. The skill gets sharper every use. Skip only if nothing was surprising.

## What actually works

- **Form fields**: `fill(selector, value)` — focuses the element, bulk-inserts via `Input.insertText`, then Tabs to blur. Fires native beforeinput/input/change/blur so framework-controlled inputs (React, Vue, Angular, Formik) all register the value. Prefer over `type_text()` (which doesn't fire keyboard DOM events). Doesn't reliably work on `<input type="date">` — those parse keystrokes segment-by-segment and reject bulk text.
- **Understanding a page cheaply** (alternative to `screenshot()` + Read for verification):
  - `clickables()` → indexed interactive elements `[{i, tag, type, id, name, role, text}]`. Override the default selector via `clickables(selector='[data-cy]')` for site-specific patterns.
  - `field_info(selector)` → validation attrs + format hint for date/time + live `valid`/`error`. **Call before typing into a field you don't know — saves turns on wrong-format retries.** `format_hints={...}` overrides for custom widgets (e.g. jQuery datepicker `mm/dd/yyyy`).
- **Scraping**: `js("...custom query...")`. Bespoke selectors beat generic DOM helpers.
- **Clicking**: `screenshot()` → look → `click(x, y)`. Passes through iframes/shadow/cross-origin at the compositor level.
- **Bulk HTTP**: `http_get(url)` + `ThreadPoolExecutor`. No browser for static pages (249 Netflix pages in 2.8s).
- **After goto**: `wait_for_load()`.
- **Wrong/stale tab**: `ensure_real_tab()`. Daemon also auto-recovers from stale sessions on next call.
- **Iframe sites** (Azure blades, Salesforce): `click(x, y)` passes through; for DOM use `js(expr, target_id=iframe_target("sandbox"))`. Iframe rects are iframe-local — add the host iframe's offset for page coords.
- **Auth wall**: redirected to login → stop and ask the user. Don't type credentials from screenshots.
- **Raw CDP** for anything helpers don't cover: `cdp("Domain.method", **params)`.

## Gotchas (field-tested)

- **React / controlled inputs ignore `el.value=...`.** Use the native setter to make React see the change:
  `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,v); el.dispatchEvent(new Event('input',{bubbles:true}))`.
- **Radio/checkbox via React**: prefer `el.click()` over `el.checked=true` — React listens to the click event to drive state.
- **UI-library buttons (MUI Select, dropdown overlays)**: JS `.click()` on `[role=button]` often does NOT fire the library's handler. Screenshot → `click(x,y)` via CDP instead.
- **Keyboard listeners checking `e.key==='Enter'` on `keypress`**: CDP's `char` event doesn't always fire DOM `keypress` for special keys. Use `dispatch_key(selector, 'Enter')`.
- **`alert()`/`confirm()` block the page thread.** Call `capture_dialogs()` BEFORE the action, read via `dialogs()` after.
- **Same-origin nested iframes** don't show up as CDP targets — walk `document.querySelector('iframe').contentDocument` (or `contentWindow`) recursively. Cross-origin iframes DO appear as targets; use `iframe_target("...")`.
- **Shadow DOM**: `document.querySelector` doesn't pierce shadow roots. Walk via `element.shadowRoot.querySelectorAll` (and recurse).
- **Submitting forms**: the "Submit" button isn't always the first `button[type=submit]` — on React Native Web etc. contact-method buttons share that type. Prefer the button whose text matches `/submit/i`, fall back to `form.requestSubmit()`.
- **Form success signals vary**: visible `#success-message`, captured `alert()` text, console log, or body text change. Check all sources — don't assume one convention.
- **Text beats screenshots for verification.** After an action, `js("document.body.innerText")` or a scoped `element.textContent` is cheaper than a screenshot and easier to pattern-match. Save screenshots for what genuinely needs pixels (coordinate clicks, visual layout, CAPTCHA).
- **Library widgets keep state outside `.value`.** `field_info()` and `el.value` only see native DOM state. jQuery datepicker, Select2, MUI pickers etc. store the selected value in library-internal objects — they'll report `value: ''` even when the widget visually shows a value. If you see that mismatch, fall back to the library's API: `$('#x').datepicker('setDate', ...)`, `$('#x').val(v).trigger('change')`, or component-specific calls.
