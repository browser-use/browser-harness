# Dialogs

Browser dialogs (`alert`, `confirm`, `prompt`, `beforeunload`) freeze the JS thread. Two approaches depending on timing.

## Reactive: dismiss via CDP (preferred)

Works even when JS is frozen. Handles all dialog types including `beforeunload`.

```python
# Dismiss and read the message
cdp("Page.handleJavaScriptDialog", accept=True)   # accept / click OK
cdp("Page.handleJavaScriptDialog", accept=False)  # cancel / click Cancel

# Read what the dialog said (from buffered CDP events)
events = drain_events()
for e in events:
    if e["method"] == "Page.javascriptDialogOpening":
        print(e["params"]["type"])     # "alert", "confirm", "prompt", "beforeunload"
        print(e["params"]["message"])  # the dialog text
```

Undetectable by antibot — no JS injected into the page.

## Proactive: stub via JS

Prevents dialogs from ever appearing. Good when you expect multiple `alert()`/`confirm()` calls in sequence.

```python
capture_dialogs()       # replaces window.alert/confirm/prompt with stubs
# ... do actions that trigger dialogs ...
msgs = dialogs()        # read captured messages
```

Tradeoffs:
- Stubs are lost on page navigation — must re-call `capture_dialogs()`
- `confirm()` always returns `true` (auto-approves)
- Detectable by antibot (`window.alert.toString()` reveals non-native code)
- Does NOT handle `beforeunload`

## beforeunload specifically

Fires when navigating away from a page with unsaved changes (forms, editors, upload pages). The page freezes until the user clicks Leave/Stay.

```python
# Option A: dismiss after navigating (CDP-level, safe)
goto("https://new-url.com")
try:
    cdp("Page.handleJavaScriptDialog", accept=True)  # click "Leave"
except:
    pass  # no dialog — normal

# Option B: prevent before navigating (JS injection, detectable)
js("window.onbeforeunload=null")
goto("https://new-url.com")
```
