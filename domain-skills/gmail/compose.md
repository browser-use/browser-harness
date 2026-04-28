# Gmail — Compose and send

URL: `https://mail.google.com`

## Prerequisites

- Logged into Gmail in the attached Chrome profile.
- Keyboard shortcuts enabled (Gmail default for most accounts).

## Open compose

```python
press_key("c")   # Gmail shortcut — opens a new compose dialog with the "To" field focused
wait(1)
```

## Multiple compose dialogs stack — pick the visible one

Gmail keeps minimized drafts as dialogs at the bottom of the page. `document.querySelectorAll('div[role="dialog"]')` returns **all** of them (minimized *and* open). The minimized ones have small bounding rects (~`h ≤ 40`) and their inner inputs report `offsetParent === null`.

Always pick the visible dialog by size, not index:

```python
idx = js("""(() => {
  const ds = [...document.querySelectorAll('div[role="dialog"]')];
  return ds.findIndex(d => d.getBoundingClientRect().height > 200);
})()""")
```

…and scope every subsequent query to `dialogs[idx]`. Using index 1 blindly works *sometimes* but breaks the moment the user has a second minimized draft already sitting at the bottom.

## Trap: Tab inserts a literal `\t` into the "To" field

After `press_key("c")`, focus is on `[aria-label="To recipients"]`. `press_key("Tab")` does **not** advance focus — it inserts a tab character into the input. Confirmed by reading back `value` and finding `"\t"`.

Either click the next field directly, or commit the recipient as a chip first (e.g. by typing a valid address; Gmail chips it automatically once the input loses focus or you type a separator).

The recipient does become a chip once you click away. Read chips from `[role="dialog"] [data-hovercard-id]` — **not** from the input's `value`.

## Fill the fields

```python
# After press_key("c"), "To" is focused
type_text("someone@example.com")

# Don't Tab — click subject directly
sub = js("""(() => {
  const d = [...document.querySelectorAll('div[role="dialog"]')].find(d => d.getBoundingClientRect().height > 200);
  const s = d.querySelector('input[name="subjectbox"]');
  const r = s.getBoundingClientRect();
  return {x: r.x + r.width/2, y: r.y + r.height/2};
})()""")
click(sub["x"], sub["y"])
type_text("Subject here")

body = js("""(() => {
  const d = [...document.querySelectorAll('div[role="dialog"]')].find(d => d.getBoundingClientRect().height > 200);
  const b = d.querySelector('div[aria-label="Message Body"], div[role="textbox"]');
  const r = b.getBoundingClientRect();
  return {x: r.x + 40, y: r.y + 30};
})()""")
click(body["x"], body["y"])
type_text("Body text goes here.")
```

## Attachments — use `DOM.setFileInputFiles` on the *visible* compose's input

The paperclip button opens a native file picker that browser-harness can't drive. Instead, set files directly on Gmail's hidden file input.

**Gotcha:** there is one `input[type="file"][name="Filedata"]` per compose dialog. If you use `upload_file('input[type="file"][name="Filedata"]', ...)`, the default `DOM.querySelector` returns the *first* match — usually belongs to a stale/minimized compose, and Gmail ignores it. Always target the input scoped to the **visible** compose:

```python
doc = cdp("DOM.getDocument", depth=-1)
ids = cdp("DOM.querySelectorAll", nodeId=doc["root"]["nodeId"],
          selector='input[type="file"][name="Filedata"]')["nodeIds"]
# Pick the one whose ancestor dialog has height > 200
# (quickest: the last one is usually the newest compose)
cdp("DOM.setFileInputFiles", files=["/abs/path.png"], nodeId=ids[-1])
wait(3)
```

After upload, `input.files` reads back as empty — Gmail consumes the FileList immediately. Don't treat that as failure. Instead, verify by screenshot or by searching the compose for the filename chip:

```python
ok = js("""(() => {
  const d = [...document.querySelectorAll('div[role="dialog"]')].find(d => d.getBoundingClientRect().height > 200);
  return [...d.querySelectorAll('*')].some(e => /\\.\\w+ \\(\\d+[KMG]?\\)/.test(e.textContent || ''));
})()""")
```

The attachment chip format is `filename.ext (61K)` — size appears only once Gmail has finished ingesting the file.

## Send

```python
send = js("""(() => {
  const d = [...document.querySelectorAll('div[role="dialog"]')].find(d => d.getBoundingClientRect().height > 200);
  const b = [...d.querySelectorAll('[role="button"]')].find(b => (b.getAttribute('aria-label')||'').startsWith('Send'));
  const r = b.getBoundingClientRect();
  return {x: r.x + r.width/2, y: r.y + r.height/2};
})()""")
click(send["x"], send["y"])
wait(2)
```

Verify by looking for the "Message sent" toast at the bottom-left, or by checking that the visible compose dialog's height has collapsed. `⌘+Enter` also sends but requires keyboard-shortcut support in the current account.

## Stable selectors

- To field: `[aria-label="To recipients"]`
- Subject: `input[name="subjectbox"]`
- Body: `div[aria-label="Message Body"]` (also matches `div[role="textbox"]` inside the dialog)
- Send button: `[role="dialog"] [role="button"][aria-label^="Send"]`
- Attach file input: `input[type="file"][name="Filedata"]` (one per dialog)
- Recipient chip: `[data-hovercard-id]` inside the dialog

## Traps

- Tab in the "To" field inserts `\t` — never Tab between fields, click them.
- `input.files` is cleared by Gmail after `setFileInputFiles` — don't use it as a success check.
- The first match of `input[type="file"]` can belong to a stale/minimized compose; pick by dialog, not by index.
- `press_key("c")` only works if keyboard shortcuts are enabled in the account. If it no-ops, fall back to clicking the left-rail Compose pencil.
