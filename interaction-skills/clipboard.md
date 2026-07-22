# Clipboard paste into browser spreadsheets

Use this when a browser spreadsheet has the correct range selected but ignores
synthetic Cmd+V. Google Sheets accepted this path reliably in Jul 2026.

## Select the destination range

Google Sheets exposes its name box as `input.waffle-name-box`.

```python
name_box = query_deep("input.waffle-name-box")
if not name_box:
    raise RuntimeError("name box not found")

click(name_box["x"], name_box["y"])
press_key("a", modifiers=4)  # Cmd+A on macOS
type_text("G2:H64")
press_key("Enter")
wait(0.5)
```

## Grant clipboard access and perform a user-gesture paste

`Input.dispatchKeyEvent` for Cmd+V may do nothing even when the system
clipboard and selection are correct. `Browser.setPermission` also rejects the
permission name `clipboardReadWrite` on current Chrome. Use
`Browser.grantPermissions`, write the TSV through `navigator.clipboard`, then
invoke paste with `userGesture=True`.

```python
import json

tsv = "Sent\t2026-07-14\nSent\t2026-07-14"

cdp(
    "Browser.grantPermissions",
    permissions=["clipboardReadWrite", "clipboardSanitizedWrite"],
    origin="https://docs.google.com",
)
js("navigator.clipboard.writeText(" + json.dumps(tsv) + ")")

result = cdp(
    "Runtime.evaluate",
    expression="document.execCommand('paste')",
    returnByValue=True,
    userGesture=True,
)
if result.get("result", {}).get("value") is not True:
    raise RuntimeError(f"paste was not accepted: {result}")
```

TSV fills rows and columns; newline-only text fills one column.

## Verification

The name box continuing to display the selected range does not prove the paste
worked. Re-read the destination with the relevant spreadsheet connector or API
and count the expected values. A screenshot is useful for layout, not for a
63-row content assertion.

