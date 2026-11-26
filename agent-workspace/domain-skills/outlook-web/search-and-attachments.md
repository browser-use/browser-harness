# Outlook on the web — search, open a message, download an attachment

Companion to mail-list.md (which covers scraping a folder). This covers finding one message and pulling its PDF.

## Search (the reliable way)
- `#topSearchInput` exists but typing into it via JS `.value=` does nothing — OWA ignores it and stays on the inbox.
- Works: `click_at_xy` on the search box (top bar, centre-left), `type_text(query)`, `press_key("Enter")`, wait ~5 s.
- Query syntax that works: `from:Gett`, plain subject words (`Receipt from le gaz`), `received>=2026-09-15`. Scope defaults to **All folders**, so results carry a folder tag (Inbox / Invoices / Deleted Items).
- A suggestions dropdown covers the top ~170 px of the page after Enter. Do **not** press Escape — Escape exits search mode entirely and drops you back on the inbox. The first result row sits below the dropdown; click it by coordinates (first row centre ≈ x 450, y 240 in a 1512-wide viewport).
- Result rows in search mode are **not** reliably `[role=option]` — `document.querySelectorAll("[role=option]")` returned nothing while rows were visible. Use screenshot + coordinates.
- `Meta+a` in the search box does not select-all; text appends. To run a second query click the **Close search** button (`button` whose text matches /close search/i) first, then click the box and type fresh.

## Opening = marking read
Clicking a row marks it read immediately. To "mark as read" without a separate UI step, just open it. Verify from the folder list: the row's aria-label starts with `Unread ` only while unread.

## Reading pane
- Body: `[aria-label="Message body"]` innerText.
- Attachment chip: `[role=option][aria-label^="<filename>"]` inside the reading pane (aria-label = `"<file> Open <size> "`). Its only button is `aria-label="More actions"` (the chevron on the chip's right). Click it → menu items Preview / Save to OneDrive / Copy / Download. Menu items are not `[role=menuitem]` on this build — click Download by coordinates (menu drops directly under the chip, Download is the last item).
- After download the chip's subtitle changes from the size to **"Downloaded"** — that's the success signal.

## Where the download lands
`Browser.setDownloadBehavior` via `cdp()` fails on this harness ("Message may have string 'sessionId' property"). Chrome uses the profile's own download dir, and the profile's *save-as* dir can differ from `~/Downloads`. Read it from the profile Preferences before hunting:

```python
import json, glob
for p in glob.glob('~/Library/Application Support/Google/Chrome/*/Preferences'):
    d = json.load(open(os.path.expanduser(p)))
    print(p.split('/')[-2], d['download'].get('default_directory'), d['savefile'].get('default_directory'))
```

Then `ls -t <dir> | head`. Rename to the folder's convention afterwards (e.g. `Gett - Home to TLV Airport - 2026-09-26 - ILS 191.00.pdf`).

## Inbox list quirk (adds to mail-list.md)
Only ~5 rows are rendered at any scroll position. A "find row by text" that doesn't scroll will report NOT FOUND for anything off-screen; step `scrollTop` in 400 px increments from 0 and re-query each step. Scrolling *up* from an unknown position resets you to the top and loses rows.

## Attachment downloads open a native Save As sheet (field note 2026-10-09)
- If the Chrome profile has `savefile.default_directory` set, both the chip menu **Download** and the reading-pane **Download all** open a macOS Save As sheet. CDP cannot see or press it, `osascript` needs an Accessibility grant the shell usually lacks, and the chip subtitle flips to "Downloaded" while the sheet is still open, so that text is **not** a success signal.
- Ask the user up front to press **Save** once per file (Download all = one zip). Files land in that `savefile.default_directory`, not `~/Downloads`. Confirm with `find <dir> -mmin -5`.
- `Download all` zip name = the mail subject with underscores; it duplicates the single PDFs, delete it after unzipping.
- Do **not** `new_tab("chrome://downloads/")` to check progress: on this harness it hangs `Runtime.evaluate` for the attached session. Recover with `list_tabs()` → `switch_tab(tid)` → `cdp("Target.activateTarget", targetId=tid)` (kwargs form; a params dict fails to deserialize).

## Coordinate scale
`capture_screenshot()` returns an image wider than the viewport (2000 px for a 1512 px window). Multiply image coordinates by `viewport_w / image_w` before `click_at_xy`, or read the target's rect with `js()` and click that.

## Searching for a thread that may not exist
Search box is at the top bar centre-left (viewport ≈ x 440, y 24 at 1512 wide). An invoice number as the only term searches all folders including Sent and Drafts; "We didn't find anything." is reliable and cheap, use it before assuming a draft was sent.
