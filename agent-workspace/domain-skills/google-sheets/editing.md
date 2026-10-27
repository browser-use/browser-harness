# Google Sheets — editing cells via CDP

The grid is canvas-rendered: no DOM scraping, no selectors for cells.

## Read data — CSV export via in-page fetch

Same-origin fetch inside the docs.google.com tab carries login cookies:

```python
r = js("""
(async () => {
  const r = await fetch("https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>");
  return await r.text();
})()
""")
```

10× faster than any UI scraping. Works for private sheets the logged-in user can see.

## Navigate — name box

Click the name box (top-left, ~x=55,y=127 at 1920w), `type_text("Q2")`, `press_key("Enter")`. The name box is a real `<input>`, so `Input.insertText` works there.

## Write cells — synthetic paste event (the only reliable way)

**Traps — these do NOT work on the grid:**
- `type_text()` (`Input.insertText`) is ignored by the grid.
- `press_key()` per char is dangerous: chars can land doubled (keyDown text + char event both insert) and may target whatever cell had a lingering editor — we corrupted an unrelated header cell this way.
- F2 does not open the cell editor via CDP key events.

**What works:** select the cell, then dispatch a `ClipboardEvent("paste")` on `document.activeElement` (which is Sheets' hidden `.cell-input` contenteditable):

```python
js("""
(() => {
  const dt = new DataTransfer();
  dt.setData("text/plain", %s);
  (document.activeElement || document.body).dispatchEvent(
    new ClipboardEvent("paste", {clipboardData: dt, bubbles: true, cancelable: true}));
})()
""" % json.dumps(text))
```

- Text starting with `=` pastes as a live formula (ARRAYFORMULA works — one paste fills a whole column).
- Multi-cell: use `\t` between columns, `\n` between rows in the text/plain payload.
- Verify every write by re-fetching the CSV export — silent failures are common.

## Sheets Tables (green "Table1" chip)

- New columns typed adjacent to a table get absorbed as a table column, but formulas do NOT auto-fill down like Excel — use ARRAYFORMULA in row 2 instead.
- Table header row is row 1; filter views over a table show `Range: Table1`.

## Filter views

Data menu → "Create filter view" → click a header's filter icon → "Filter by values" → uncheck values → OK → "Save view" button (top-right of the green bar) → a "Name this view?" dialog appears with a real `<input>` (so `type_text` works there) → Save.

Renaming via the green-bar name label did not respond to clicks/typing; the save dialog is the reliable place to name it.

## Other traps

- A spellcheck popup ("Change X to:") can appear over the grid after edits and will "fix" your header if you click Change — dismiss with its X.
- CSV export reflects saved state within ~1s of an edit; if a write doesn't show up there, it didn't happen.
