# Google Sheets — typing values into cells without corrupting them

Field-tested against docs.google.com/spreadsheets on 2026-08-29.

## The trap: autocomplete silently commits a value you never typed

Sheets autocompletes a **text** entry from other values already present in the same column. The
suggested remainder is appended to the cell as *selected* text, and **`Tab` and `Enter` commit the
suggestion, not what you typed.**

Concretely: a column already contains `Mem0 (YC S24)`. You type `Mem0` into another cell in that
column and press Tab. The cell ends up holding **`Mem0 (YC S24)`**.

Nothing errors. The keystrokes all succeed, the write "works", and the wrong value is only visible
if you read the sheet back. In a five-run series this corrupted exactly one cell per run while every
run reported clean.

## Fix: press Delete before committing

```python
type_text(value)
press("Delete")      # discards any pending autocomplete suggestion
press("Tab")
```

`Delete` removes the selected suggestion. When there is no suggestion it is a **no-op** — the caret
sits at the end of the typed text with nothing after it — so it is safe to apply unconditionally
rather than trying to detect when autocomplete fired.

Only text triggers this. Numbers, URLs, and dates are unaffected, but applying `Delete` everywhere
costs nothing and means you don't have to reason about which columns are at risk.

## Always read the sheet back

The failure mode above is invisible from the writing side, so verify from the reading side. The CSV
export is the cheapest way and needs no extra auth beyond the session you already have:

```
https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=<gid>
```

Diff it against what you intended to write, cell by cell, and raise on mismatch. A script that
writes data should not be able to report success without checking the data — "no exception" is not
"correct output".

## Navigating to a cell: use the Name Box, not pixel clicks

Clicking a grid cell by coordinate is fragile (scroll position, frozen rows, zoom). The Name Box is
stable:

```python
click("#t-name-box")
fill("#t-name-box", "A2")
press("Enter")
```

Then type across the row with `Tab` between cells and `Enter` to end the row.

## Auth note: Google session cookies rotate fast

If you drive Sheets with exported-and-injected Chrome cookies, re-export them immediately before the
run. Google rotates `__Secure-1PSIDTS` within hours. A stale export does **not** present as a login
error — you land on the account chooser, which renders every account as "Signed out" while returning
**HTTP 200**, so it reads as a working page. The failure surfaces much later as a bare `401` from
the CSV export endpoint.

Cookies for other sites in the same export (LinkedIn, X) stay valid for days, so "the export works"
is not evidence that the Google half of it does.
