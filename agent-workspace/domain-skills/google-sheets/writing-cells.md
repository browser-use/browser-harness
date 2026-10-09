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
press_key("Delete")
press_key("Tab")
```

`Delete` removes the selected autocomplete suffix. Without a suggestion, forward Delete does nothing when the caret follows the entered text. Use this sequence only while editing the cell at that position. Do not send Delete after committing the cell: it can clear the selected cell.

The observed failure involved text entries. Verify every written value, including numbers, dates, and URLs.

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
fill_input("#t-name-box", "A2")
press_key("Enter")
```

Use `press_key("Delete")` before each `Tab` or `Enter` commit after typing a text value. This removes any selected autocomplete suffix. Verify the resulting cells through the export.

## Authentication and export failures

Use the existing authorized browser session for the sheet and its CSV export. Do not export session cookies for this workflow.

An HTTP 200 response can contain an account chooser instead of spreadsheet data. Check the response type and contents before comparing cells. If the export returns a login page or HTTP 401, restore authentication in the browser and retry the export.

Do not print session cookies or include them in scripts, logs, or reusable skills.
